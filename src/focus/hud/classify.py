"""Heuristics that classify blast-radius files for the HUD.

These are path-based and hop-based only — no LLM, no invented edges.
Danger Zone paths mirror the Phase 0 trigger table (API / schema / routes).
"""

from __future__ import annotations

from pathlib import PurePosixPath

from focus.models import ImpactNode, RiskTier

# Path fragments that mark a file as a Danger Zone when it appears downstream.
_DANGER_FRAGMENTS = (
    "/api/",
    "/routes/",
    "/routers/",
    "/migrations/",
)
_DANGER_NAMES = frozenset({"models.py", "schema.prisma", "settings.py", "config.py"})

DEFAULT_CAVEAT = (
    "**Caveat:** Static analysis only. Runtime imports, dynamic dispatch, "
    "and cross-repo dependencies may not appear in this graph."
)


def is_danger_zone(path: str) -> bool:
    """True when this file path looks like an API/schema/config surface."""
    posix = PurePosixPath(path)
    name = posix.name
    if name in _DANGER_NAMES:
        return True
    padded = f"/{path}" if not path.startswith("/") else path
    return any(fragment in padded for fragment in _DANGER_FRAGMENTS)


def classify_impacts(
    rings: list[tuple[int, list[str]]],
) -> tuple[list[ImpactNode], list[ImpactNode]]:
    """Split ring files into Danger Zones vs ordinary downstream."""
    danger: list[ImpactNode] = []
    downstream: list[ImpactNode] = []
    for hops, paths in rings:
        for path in paths:
            if is_danger_zone(path):
                danger.append(
                    ImpactNode(
                        path=path,
                        hops=hops,
                        reason=_danger_reason(path, hops),
                    )
                )
            else:
                downstream.append(
                    ImpactNode(
                        path=path,
                        hops=hops,
                        reason=_downstream_reason(hops),
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
    if downstream_count == 0:
        return "LOW"
    if danger_count > 0 and (downstream_count >= 3 or max_hops >= 2):
        return "CRITICAL"
    if danger_count > 0 or downstream_count >= 3 or max_hops >= 2:
        return "HIGH"
    return "MEDIUM"


def _danger_reason(path: str, hops: int) -> str:
    kind = "API/schema surface"
    padded = f"/{path}"
    if "/api/" in padded or "/routes/" in padded or "/routers/" in padded:
        kind = "API route surface"
    elif PurePosixPath(path).name in {"models.py", "schema.prisma"}:
        kind = "data model surface"
    elif PurePosixPath(path).name in {"settings.py", "config.py"}:
        kind = "config surface"
    hop_word = "hop" if hops == 1 else "hops"
    return f"{kind} in blast radius ({hops} {hop_word} from seed)"


def _downstream_reason(hops: int) -> str:
    if hops == 1:
        return "imports the seed directly"
    return f"{hops} imports away from seed"
