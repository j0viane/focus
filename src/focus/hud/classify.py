"""Heuristics that classify blast-radius files for the HUD.

Danger Zones come from two evidence sources — never from an LLM:
1. Path patterns (API / schema / config surfaces)
2. High fan-out in the computed graph (many files import this one)
"""

from __future__ import annotations

from pathlib import PurePosixPath

import networkx as nx

from focus.models import ImpactNode, RiskTier

# Path fragments that mark a file as a Danger Zone when it appears downstream.
_DANGER_FRAGMENTS = (
    "/api/",
    "/routes/",
    "/routers/",
    "/migrations/",
    "/models/",
)
_DANGER_NAMES = frozenset({"models.py", "schema.prisma", "settings.py", "config.py"})

# Direct importers (predecessors) at or above this count → shared / high fan-out.
DEFAULT_FAN_OUT_THRESHOLD = 3

# How many importer paths to name in Danger Zone reasons before "and N more".
_IMPORTER_NAME_CAP = 3

DEFAULT_CAVEAT = (
    "**Caveat:** Static analysis only. Runtime imports, dynamic dispatch, "
    "and cross-repo dependencies may not appear in this graph."
)


def importer_count(graph: nx.DiGraph, path: str) -> int:
    """How many scanned files import `path` (direct predecessors)."""
    if path not in graph:
        return 0
    return graph.in_degree(path)


def list_importers(graph: nx.DiGraph, path: str) -> list[str]:
    """Sorted paths of files that import `path` directly."""
    if path not in graph:
        return []
    return sorted(graph.predecessors(path))


def is_danger_zone(
    path: str,
    graph: nx.DiGraph | None = None,
    *,
    fan_out_threshold: int = DEFAULT_FAN_OUT_THRESHOLD,
) -> bool:
    """True for API/schema/config paths or high-fan-out shared modules."""
    if is_danger_path(path):
        return True
    if graph is None:
        return False
    if _is_package_init(path):
        return False
    return importer_count(graph, path) >= fan_out_threshold


def is_danger_path(path: str) -> bool:
    """True when the file path alone looks like an API/schema/config surface."""
    posix = PurePosixPath(path)
    if posix.name in _DANGER_NAMES:
        return True
    padded = f"/{path}" if not path.startswith("/") else path
    return any(fragment in padded for fragment in _DANGER_FRAGMENTS)


def classify_impacts(
    rings: list[tuple[int, list[str]]],
    graph: nx.DiGraph | None = None,
    *,
    fan_out_threshold: int = DEFAULT_FAN_OUT_THRESHOLD,
    seeds: list[str] | None = None,
) -> tuple[list[ImpactNode], list[ImpactNode]]:
    """Split ring files into Danger Zones vs ordinary downstream."""
    seed_list = seeds or []
    danger: list[ImpactNode] = []
    downstream: list[ImpactNode] = []
    for hops, paths in rings:
        for path in paths:
            if is_danger_zone(path, graph, fan_out_threshold=fan_out_threshold):
                danger.append(
                    ImpactNode(
                        path=path,
                        hops=hops,
                        reason=_danger_reason(path, hops, graph),
                    )
                )
            else:
                downstream.append(
                    ImpactNode(
                        path=path,
                        hops=hops,
                        reason=_downstream_reason(path, hops, graph, seed_list),
                    )
                )
    return danger, downstream


def score_risk(
    *,
    downstream_count: int,
    max_hops: int,
    danger_count: int,
) -> RiskTier:
    """Deterministic risk tier from blast-radius size and Danger Zones."""
    if downstream_count == 0 and danger_count == 0:
        return "LOW"
    if danger_count > 0 and (downstream_count >= 3 or max_hops >= 2):
        return "CRITICAL"
    if danger_count > 0 or downstream_count >= 3 or max_hops >= 2:
        return "HIGH"
    if downstream_count == 0 and danger_count > 0:
        return "HIGH"
    return "MEDIUM"


def shared_hub_reason(
    graph: nx.DiGraph | None,
    path: str,
    *,
    changed: bool = False,
    hops: int | None = None,
) -> str:
    """Plain-English reason naming who imports a shared hub."""
    importers = list_importers(graph, path) if graph is not None else []
    named = _format_path_list(importers)
    distance = _distance_phrase(hops) if hops is not None else ""
    if changed:
        if named:
            return f"You changed a shared hub — imported directly by {named}."
        return "You changed a shared hub."
    if named:
        return f"Shared hub — imported directly by {named}{distance}."
    count = len(importers)
    return f"Shared hub — {count} other files import it directly{distance}."


def _danger_reason(path: str, hops: int, graph: nx.DiGraph | None) -> str:
    distance = _distance_phrase(hops)

    if is_danger_path(path):
        kind = "API, schema, or config code"
        padded = f"/{path}"
        if "/api/" in padded or "/routes/" in padded or "/routers/" in padded:
            kind = "an API route file"
        elif PurePosixPath(path).name in {"models.py", "schema.prisma"} or "/models/" in padded:
            kind = "a data-model file"
        elif PurePosixPath(path).name in {"settings.py", "config.py"}:
            kind = "a config file"
        elif "/migrations/" in padded:
            kind = "a migration file"
        return f"This is {kind}{distance}."

    return shared_hub_reason(graph, path, hops=hops)


def _downstream_reason(
    path: str,
    hops: int,
    graph: nx.DiGraph | None,
    seeds: list[str],
) -> str:
    if hops == 1:
        if graph is not None and seeds:
            # Edge A -> B means A imports B; hop-1 dependents import a seed.
            hit = sorted(s for s in seeds if graph.has_edge(path, s))
            if hit:
                return f"Directly imports {_format_path_list(hit)}."
        return "Directly imports a file you changed."
    return f"Depends on a file you changed through {hops} import steps (not a direct import)."


def _distance_phrase(hops: int) -> str:
    if hops <= 0:
        return " (this is one of the files you changed)"
    if hops == 1:
        return " — it directly imports a file you changed"
    return f" — {hops} import steps away from a file you changed"


def _format_path_list(paths: list[str]) -> str:
    """Format paths as `a`, `b`, and `c` (cap then 'and N more')."""
    if not paths:
        return ""
    if len(paths) <= _IMPORTER_NAME_CAP:
        if len(paths) == 1:
            return f"`{paths[0]}`"
        if len(paths) == 2:
            return f"`{paths[0]}` and `{paths[1]}`"
        return f"`{paths[0]}`, `{paths[1]}`, and `{paths[2]}`"
    shown = paths[:_IMPORTER_NAME_CAP]
    more = len(paths) - _IMPORTER_NAME_CAP
    head = ", ".join(f"`{p}`" for p in shown)
    return f"{head}, and {more} more"


def _is_package_init(path: str) -> bool:
    return PurePosixPath(path).name == "__init__.py"
