"""CaptionEvidencePack — structured facts only; never full files."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from focus.models import ChangedSymbolInfo, ModuleFacts, RiskTier

MAX_EDIT_LINES = 20
MAX_EDIT_CHARS = 1500
MAX_IMPLICATION_PART = 80


class EditLine(BaseModel):
    line: int
    text: str


class MeasuredSlots(BaseModel):
    return_expr: str | None = None
    assign: str | None = None
    callees: list[str] = Field(default_factory=list)
    import_modules: list[str] = Field(default_factory=list)
    blank_count: int | None = None


class CaptionEvidencePack(BaseModel):
    """JSON payload sent to the labeler — capped edit lines + measured slots."""

    path: str
    symbol_name: str
    symbol_kind: str
    risk_tier: RiskTier
    implication_who: str = ""
    implication_what: str = ""
    edit_lines: list[EditLine] = Field(default_factory=list)
    measured: MeasuredSlots = Field(default_factory=MeasuredSlots)
    deterministic_caption: str = ""
    purpose_hint: str = ""
    allowed_tokens: list[str] = Field(default_factory=list)


def build_evidence_pack(
    symbol: ChangedSymbolInfo,
    *,
    risk: RiskTier,
    implication: str = "",
    purpose_hint: str = "",
    facts: ModuleFacts | None = None,
    source_lines: list[str] | None = None,
) -> CaptionEvidencePack:
    """Build a pack from facts Focus already computed (no full-file dump)."""
    who, what = _split_implication(implication)
    edit_lines = _capped_edit_lines(symbol, source_lines)
    measured = _measure(edit_lines, facts=facts, hunk_lines=symbol.changed_lines or [symbol.line])
    allowed = _allowed_tokens(symbol, measured, facts)
    return CaptionEvidencePack(
        path=symbol.path,
        symbol_name=symbol.name,
        symbol_kind=symbol.kind,
        risk_tier=risk,
        implication_who=who,
        implication_what=what,
        edit_lines=edit_lines,
        measured=measured,
        deterministic_caption=(symbol.detail or "").strip(),
        purpose_hint=(purpose_hint or "").strip()[:200],
        allowed_tokens=sorted(allowed),
    )


def pack_contains_secrets(pack: CaptionEvidencePack) -> bool:
    """Abort LLM when high-entropy secret-like strings appear in edit lines."""
    blob = "\n".join(line.text for line in pack.edit_lines)
    return _looks_like_secret(blob)


def _split_implication(implication: str) -> tuple[str, str]:
    # "{emoji} {RISK} — {who} — {what}"
    parts = [p.strip() for p in (implication or "").split("—")]
    if len(parts) >= 3:
        who = parts[1][:MAX_IMPLICATION_PART]
        what = parts[2][:MAX_IMPLICATION_PART]
        return who, what
    return "", ""


def _capped_edit_lines(
    symbol: ChangedSymbolInfo,
    source_lines: list[str] | None,
) -> list[EditLine]:
    if not source_lines:
        return []
    line_nos = symbol.changed_lines or [symbol.line]
    out: list[EditLine] = []
    chars = 0
    for line_no in line_nos[:MAX_EDIT_LINES]:
        if line_no < 1 or line_no > len(source_lines):
            continue
        text = source_lines[line_no - 1].rstrip("\n")
        if chars + len(text) > MAX_EDIT_CHARS:
            break
        out.append(EditLine(line=line_no, text=text))
        chars += len(text)
    return out


def _measure(
    edit_lines: list[EditLine],
    *,
    facts: ModuleFacts | None,
    hunk_lines: list[int],
) -> MeasuredSlots:
    texts = [e.text for e in edit_lines]
    blob = "\n".join(texts)
    blank_count = sum(1 for t in texts if not t.strip()) or None
    return_expr = None
    for text in texts:
        m = re.match(r"\s*return\s+(.+)$", text)
        if m:
            return_expr = m.group(1).strip().rstrip(";")[:80]
    assign = None
    for text in texts:
        m = re.match(r"\s*(\w+)\s*=\s*(.+)$", text)
        if m and m.group(1) not in ("if", "elif", "for", "while"):
            assign = f"{m.group(1)}={m.group(2).strip()[:60]}"
            break
    import_modules: list[str] = []
    for text in texts:
        m = re.match(r"\s*(?:from\s+([\w.]+)\s+)?import\s+", text)
        if m and m.group(1):
            import_modules.append(m.group(1))
        elif text.strip().startswith("import "):
            rest = text.strip()[len("import ") :].split(",")[0].strip().split(" as ")[0]
            if rest:
                import_modules.append(rest)
    callees: list[str] = []
    if facts:
        hunk = set(hunk_lines)
        for call in facts.calls:
            if call.line in hunk:
                bare = call.callee.split(".")[-1]
                if bare and bare not in callees:
                    callees.append(bare)
    if not callees:
        for name in re.findall(r"(?<!\.)([a-z_][\w]*)\s*\(", blob, re.IGNORECASE):
            if name not in {"if", "elif", "for", "while", "with", "return"} and name not in callees:
                callees.append(name)
    return MeasuredSlots(
        return_expr=return_expr,
        assign=assign,
        callees=callees[:8],
        import_modules=import_modules[:8],
        blank_count=blank_count if blank_count else None,
    )


def _allowed_tokens(
    symbol: ChangedSymbolInfo,
    measured: MeasuredSlots,
    facts: ModuleFacts | None,
) -> set[str]:
    tokens: set[str] = {symbol.name, symbol.path}
    tokens.add(symbol.path.split("/")[-1])
    for c in measured.callees:
        tokens.add(c)
    for mod in measured.import_modules:
        tokens.add(mod)
        tokens.add(mod.split(".")[-1])
    if measured.assign and "=" in measured.assign:
        tokens.add(measured.assign.split("=", 1)[0])
    if facts:
        for definition in facts.definitions:
            tokens.add(definition.name)
        for call in facts.calls:
            tokens.add(call.callee.split(".")[-1])
    return {t for t in tokens if t}


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|authorization)\s*[:=]\s*['\"][^'\"]{8,}"),
    re.compile(r"(?i)bearer\s+[a-z0-9\-._~+/]+=*"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)sk-[a-z0-9]{20,}"),
)


def _looks_like_secret(text: str) -> bool:
    return any(p.search(text) for p in _SECRET_PATTERNS)


def pack_as_prompt_json(pack: CaptionEvidencePack) -> dict[str, Any]:
    return pack.model_dump(mode="json")
