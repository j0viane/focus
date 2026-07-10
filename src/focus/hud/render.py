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
    ]
    if hud.changed_symbols:
        parts.extend(
            [
                "### Changed symbols",
                "",
                *(
                    f"- `{s.path}` → `{s.name}` ({s.kind}, line {s.line})"
                    for s in hud.changed_symbols
                ),
                "",
            ]
        )
    parts.extend(
        [
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
            "🔴 **Danger Zones** *(risky if wrong — shared or API/schema/config)*",
            *_bullets(hud.danger_zones),
            "",
            "🟡 **Also affected** *(these files depend on what you changed)*",
            *_bullets(hud.downstream),
            "",
            "🟢 **Not pulled in** *(no dependents found for this change)*",
            *_isolated(hud.isolated),
        ]
    )
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
