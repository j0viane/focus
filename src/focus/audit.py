"""Assemble a Focus HUD for a local audit (diff seeds → blast radius)."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

from focus.graph import build_graph, downstream_rings
from focus.hud.classify import (
    DEFAULT_CAVEAT,
    classify_impacts,
    is_danger_path,
    is_danger_zone,
    score_risk,
)
from focus.hud.mermaid import render_mermaid, validate_mermaid_edges
from focus.ingest import changed_files, changed_python_files
from focus.models import FocusHUD, ImpactNode
from focus.scan import discover_python_files, parse_module
from focus.triggers import should_emit_diagram


def audit_local(root: Path, base: str = "main") -> FocusHUD:
    """Build a HUD for working-tree changes vs `base`."""
    root = root.resolve()
    all_changed = changed_files(root, base)
    py_changed = changed_python_files(root, base)

    if not all_changed:
        return FocusHUD(
            mode="pass_through",
            seed="(none)",
            summary=(f"**Focus:** No changes vs `{base}` — nothing to audit. **LOW** risk."),
            risk_tier="LOW",
        )

    if not py_changed:
        sample = ", ".join(f"`{p}`" for p in all_changed[:5])
        more = "" if len(all_changed) <= 5 else f" (+{len(all_changed) - 5} more)"
        return FocusHUD(
            mode="pass_through",
            seed="(non-python)",
            summary=(
                f"**Focus:** Changed non-Python paths only ({sample}{more}) — "
                f"no executable dependency graph for this diff. **LOW** risk."
            ),
            risk_tier="LOW",
        )

    facts = [parse_module(path) for path in discover_python_files(root)]
    graph = build_graph(facts, root)
    seeds = [path for path in py_changed if path in graph]
    missing = [path for path in py_changed if path not in graph]

    if not seeds:
        detail = ", ".join(f"`{p}`" for p in py_changed[:5])
        return FocusHUD(
            mode="pass_through",
            seed="(unscanned)",
            summary=(
                f"**Focus:** Python changes ({detail}) were not in the scanned "
                f"graph (deleted or ignored). **LOW** risk."
            ),
            risk_tier="LOW",
            caveat=DEFAULT_CAVEAT if missing else None,
        )

    rings = _merge_rings(graph, seeds)
    # Downstream must not list the seeds themselves.
    seed_set = set(seeds)
    rings = [(hops, [p for p in paths if p not in seed_set]) for hops, paths in rings]
    rings = [(hops, paths) for hops, paths in rings if paths]

    has_downstream = bool(rings)
    downstream_file_count = sum(len(paths) for _, paths in rings)
    if not should_emit_diagram(
        changed_paths=all_changed,
        python_seeds=seeds,
        has_downstream=has_downstream,
        downstream_file_count=downstream_file_count,
        graph=graph,
    ):
        label = ", ".join(f"`{s}`" for s in seeds)
        return FocusHUD(
            mode="pass_through",
            seed=", ".join(seeds),
            summary=(
                f"**Focus:** Changed {label} — no downstream dependents and "
                f"no Danger Zone seed. **LOW** risk."
            ),
            risk_tier="LOW",
            isolated=seeds,
        )

    return _full_audit_hud(graph, seeds, rings)


def _full_audit_hud(
    graph: nx.DiGraph,
    seeds: list[str],
    rings: list[tuple[int, list[str]]],
) -> FocusHUD:
    danger, downstream = classify_impacts(rings, graph)
    for seed in seeds:
        if is_danger_zone(seed, graph):
            fans = graph.in_degree(seed) if seed in graph else 0
            if is_danger_path(seed):
                reason = "changed API/schema/config surface (seed itself)"
            else:
                reason = f"changed high fan-out shared module ({fans} direct importers)"
            danger.insert(
                0,
                ImpactNode(
                    path=seed,
                    hops=0,
                    reason=reason,
                ),
            )

    total = sum(len(paths) for _, paths in rings)
    max_hops = max((hops for hops, _ in rings), default=0)
    risk = score_risk(
        downstream_count=max(total, 1 if danger else 0),
        max_hops=max(max_hops, 1 if danger else 0),
        danger_count=len(danger),
    )
    # Isolated seeds: changed Python with no downstream and not already danger-listed.
    danger_paths = {n.path for n in danger}
    isolated = [s for s in seeds if s not in danger_paths and total == 0]

    mermaid = render_mermaid(graph, seeds, rings)
    invalid = validate_mermaid_edges(graph, mermaid)
    if invalid:
        raise ValueError(f"Mermaid edges not in graph: {invalid}")

    seed_label = ", ".join(f"`{s}`" for s in seeds)
    file_word = "file" if total == 1 else "files"
    hop_bit = f", up to {max_hops} {'hop' if max_hops == 1 else 'hops'} away" if max_hops else ""
    danger_bit = ""
    if danger:
        names = ", ".join(f"`{n.path}`" for n in danger[:3])
        danger_bit = f" Danger Zones: {names}."

    return FocusHUD(
        mode="full",
        seed=", ".join(seeds),
        summary=(
            f"Audited local changes to {seed_label}. **{risk}** risk — "
            f"{total} downstream {file_word}{hop_bit}.{danger_bit}"
        ),
        risk_tier=risk,
        mermaid=mermaid,
        danger_zones=danger,
        downstream=downstream,
        isolated=isolated,
        caveat=DEFAULT_CAVEAT,
    )


def _merge_rings(
    graph: nx.DiGraph,
    seeds: list[str],
) -> list[tuple[int, list[str]]]:
    best: dict[str, int] = {}
    for seed in seeds:
        for hops, paths in downstream_rings(graph, seed):
            for path in paths:
                if path not in best or hops < best[path]:
                    best[path] = hops
    rings: dict[int, list[str]] = {}
    for path, hops in best.items():
        rings.setdefault(hops, []).append(path)
    return [(hops, sorted(paths)) for hops, paths in sorted(rings.items())]
