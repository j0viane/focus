"""Render a FocusHUD to markdown for CLI stdout and PR comments."""

from __future__ import annotations

from focus.models import ChangedSymbolInfo, FocusHUD, ImpactNode

# ROA — PR / CLI markdown must stay scannable (PR #25 was unbounded).
MAX_PR_SYMBOLS = 8
MAX_PR_BLAST_BULLETS = 8
MAX_PR_BULLET_CHARS = 110


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
        parts.extend(["### Your changes", ""])
        parts.extend(_your_changes_bullets(hud))
        parts.append("")
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
            *_bullets(hud.danger_zones, cap=None),
            "",
            "🟡 **Also affected** *(these files depend on what you changed)*",
            *_bullets(hud.downstream, cap=MAX_PR_BLAST_BULLETS),
            "",
            "🟢 **Not pulled in** *(no dependents found for this change)*",
            *_isolated(hud.isolated, cap=MAX_PR_BLAST_BULLETS),
        ]
    )
    if hud.caveat:
        parts.extend(["", hud.caveat])
    return "\n".join(parts)


def _your_changes_bullets(hud: FocusHUD) -> list[str]:
    danger_paths = {node.path for node in hud.danger_zones}
    ordered = sorted(
        hud.changed_symbols,
        key=lambda s: _symbol_sort_key(s, danger_paths),
    )
    shown = ordered[:MAX_PR_SYMBOLS]
    lines = [_format_symbol_bullet(s) for s in shown]
    extra = len(ordered) - len(shown)
    if extra > 0:
        lines.append(
            f"- …and {extra} more changed symbols "
            "(see IDE CodeLens or `focus audit --format json`)"
        )
    return lines


def _symbol_sort_key(
    symbol: ChangedSymbolInfo,
    danger_paths: set[str],
) -> tuple[int, int, str, str]:
    """Danger-zone paths and public names first; private helpers last."""
    in_danger = 0 if symbol.path in danger_paths else 1
    private = 1 if symbol.name.startswith("_") else 0
    return (in_danger, private, symbol.path, symbol.name)


def _format_symbol_bullet(symbol: ChangedSymbolInfo) -> str:
    head = f"- `{symbol.path}` → **`{symbol.name}`** ({symbol.kind}, line {symbol.line})"
    blurb = _symbol_blurb(symbol)
    if not blurb:
        return head
    return f"{head} — {blurb}"


def _symbol_blurb(symbol: ChangedSymbolInfo) -> str:
    """One short idea per bullet — prefer detail/summary over long explanation."""
    for candidate in (
        symbol.detail.strip(),
        symbol.summary.strip(),
        symbol.explanation.strip(),
    ):
        if candidate:
            return _clip_bullet(candidate)
    return ""


def _clip_bullet(text: str) -> str:
    plain = " ".join(text.split())
    if len(plain) <= MAX_PR_BULLET_CHARS:
        return plain
    return plain[: MAX_PR_BULLET_CHARS - 1].rstrip() + "…"


def _bullets(nodes: list[ImpactNode], *, cap: int | None) -> list[str]:
    if not nodes:
        return ["- (none for this change)"]
    if cap is None or len(nodes) <= cap:
        return [f"- `{node.path}` — {node.reason}" for node in nodes]
    shown = nodes[:cap]
    extra = len(nodes) - cap
    lines = [f"- `{node.path}` — {node.reason}" for node in shown]
    lines.append(f"- …and {extra} more")
    return lines


def _isolated(paths: list[str], *, cap: int | None = None) -> list[str]:
    if not paths:
        return ["- (none for this change)"]
    if cap is None or len(paths) <= cap:
        return [f"- `{path}`" for path in paths]
    shown = paths[:cap]
    extra = len(paths) - cap
    lines = [f"- `{path}`" for path in shown]
    lines.append(f"- …and {extra} more")
    return lines
