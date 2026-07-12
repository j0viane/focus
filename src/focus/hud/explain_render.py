"""Render symbol explanations for the CLI (`focus explain`)."""

from __future__ import annotations

import json

from focus.models import EvidenceItem, SymbolExplanation


def render_explanations_markdown(
    explanations: list[SymbolExplanation],
    *,
    show_why: bool,
) -> str:
    if not explanations:
        return "No changed symbols to explain."

    parts: list[str] = ["## Focus explanations", ""]
    for item in explanations:
        sym = item.symbol
        parts.append(f"### `{sym.name}` — `{sym.path}:{sym.line}` ({sym.kind})")
        parts.append("")
        parts.append(item.text)
        parts.append("")
        if show_why:
            parts.extend(_render_why(item))
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def render_explanations_json(explanations: list[SymbolExplanation], *, show_why: bool) -> str:
    payload = [
        item.model_dump(mode="json")
        if show_why
        else {
            "symbol": item.symbol.model_dump(mode="json"),
            "text": item.text,
        }
        for item in explanations
    ]
    return json.dumps(payload, indent=2) + "\n"


def _render_why(item: SymbolExplanation) -> list[str]:
    lines = ["#### Why this text", ""]
    overlap = [
        e
        for clause in item.clauses
        for e in clause.evidence
        if e.kind == "diff_overlap"
    ]
    if overlap:
        lines.append("**Changed symbol** *(proven)*")
        lines.extend(_bullet_lines(overlap))
        lines.append("")

    for clause in item.clauses:
        proven = [e for e in clause.evidence if e.confidence == "proven" and e.kind != "diff_overlap"]
        heuristic = [e for e in clause.evidence if e.confidence == "heuristic"]
        title = "Purpose" if clause.role == "purpose" else "Impact"
        if proven:
            lines.append(f"**{title}** *(proven)*")
            lines.extend(_bullet_lines(proven))
            lines.append("")
        if heuristic:
            lines.append(f"**{title} label** *(heuristic — verify in code)*")
            lines.extend(_bullet_lines(heuristic))
            lines.append("")
    return lines


def _bullet_lines(items: list[EvidenceItem]) -> list[str]:
    return [f"- `{item.location}` — {item.fact}" for item in items]
