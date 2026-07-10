"""Render a FocusHUD to markdown for CLI stdout (and later PR comments)."""

from __future__ import annotations

from focus.models import FocusHUD, ImpactNode


def render_hud(hud: FocusHUD) -> str:
    """Markdown string matching the docs/HUD.md block contract."""
    if hud.mode == "pass_through":
        return hud.summary

    parts = [
        "## Focus",
        "",
        hud.summary,
        "",
        "### Architecture impact",
        "",
        "Legend: each box is a **file**; an arrow means **change flows to** "
        "(that file imports / depends on the previous one).",
        "",
        "```mermaid",
        hud.mermaid or "",
        "```",
        "",
        "### Blast radius",
        "",
        "🔴 **Danger Zones**",
        *_bullets(hud.danger_zones),
        "",
        "🟡 **Impacted Downstream**",
        *_bullets(hud.downstream),
        "",
        "🟢 **Isolated / Low Risk**",
        *_isolated(hud.isolated),
    ]
    if hud.caveat:
        parts.extend(["", hud.caveat])
    return "\n".join(parts)


def _bullets(nodes: list[ImpactNode]) -> list[str]:
    if not nodes:
        return ["- (none for this change)"]
    return [f"- `{node.path}` — {node.reason}" for node in nodes]


def _isolated(paths: list[str]) -> list[str]:
    if not paths:
        return ["- (none for this change)"]
    return [f"- `{path}`" for path in paths]
