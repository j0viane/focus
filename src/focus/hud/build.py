"""Assemble a FocusHUD from a seed file and its blast-radius rings."""

from __future__ import annotations

import networkx as nx

from focus.hud.classify import (
    DEFAULT_CAVEAT,
    classify_impacts,
    score_risk,
)
from focus.hud.mermaid import render_mermaid, validate_mermaid_edges
from focus.models import FocusHUD


def build_hud(graph: nx.DiGraph, seed: str, rings: list[tuple[int, list[str]]]) -> FocusHUD:
    """Build the HUD payload for one seed file.

    Empty blast radius → pass-through (summary only). Non-empty → full HUD
    with Mermaid. Smart triggers (skip diagram for boring changes) land in
    Phase 2; until then, any downstream impact gets the full HUD.
    """
    total = sum(len(paths) for _, paths in rings)
    if total == 0:
        return FocusHUD(
            mode="pass_through",
            seed=seed,
            summary=(
                f"**Focus:** No scanned file imports `{seed}` — changing it "
                f"touches nothing downstream. **LOW** risk."
            ),
            risk_tier="LOW",
            isolated=[seed],
            caveat=None,
        )

    danger, downstream = classify_impacts(rings)
    max_hops = max(hops for hops, _ in rings)
    risk = score_risk(
        downstream_count=total,
        max_hops=max_hops,
        danger_count=len(danger),
    )
    mermaid = render_mermaid(graph, seed, rings)
    invalid = validate_mermaid_edges(graph, mermaid)
    if invalid:
        raise ValueError(f"Mermaid edges not in graph: {invalid}")

    summary = _summary(seed, risk, total, max_hops, danger)
    return FocusHUD(
        mode="full",
        seed=seed,
        summary=summary,
        risk_tier=risk,
        mermaid=mermaid,
        danger_zones=danger,
        downstream=downstream,
        isolated=[],
        caveat=DEFAULT_CAVEAT,
    )


def _summary(
    seed: str,
    risk: str,
    total: int,
    max_hops: int,
    danger: list,
) -> str:
    file_word = "file" if total == 1 else "files"
    hop_word = "hop" if max_hops == 1 else "hops"
    danger_bit = ""
    if danger:
        names = ", ".join(f"`{n.path}`" for n in danger[:3])
        danger_bit = f" Danger Zones: {names}."
    return (
        f"Traced `{seed}`. **{risk}** risk — {total} downstream {file_word}, "
        f"up to {max_hops} {hop_word} away.{danger_bit}"
    )
