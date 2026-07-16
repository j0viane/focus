"""Validate model caption output against the evidence pack."""

from __future__ import annotations

import re

from focus.llm.pack import CaptionEvidencePack

MAX_LABEL_CHARS = 110

_HOP_RE = re.compile(r"\b\d+\s*hops?\b", re.IGNORECASE)
_RISK_WORDS = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
_BACKTICK_RE = re.compile(r"`([^`]+)`")
# snake_case or CamelCase — English lowercase words are not treated as entities.
_SNAKE_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_CAMEL_RE = re.compile(r"\b[A-Z][a-z0-9]*(?:[A-Z][a-z0-9]*)+\b")
_SCOPE_RE = re.compile(
    r"\b(callers?|downstream|depends?|dependents?)\b|\bimports?\s+from\b",
    re.IGNORECASE,
)


def validate_label(detail: str, pack: CaptionEvidencePack) -> str | None:
    """Return a safe caption or ``None`` to keep the deterministic one.

    Fail closed: hops, wrong risk, ungrounded identifiers, and scope claims
    that the evidence pack does not support are rejected entirely.
    """
    if not detail or not str(detail).strip():
        return None
    text = " ".join(str(detail).split())
    if _HOP_RE.search(text):
        return None
    upper = text.upper()
    for tier in _RISK_WORDS:
        if tier in upper and tier != pack.risk_tier:
            return None

    corpus = _pack_support_corpus(pack)
    if _has_unknown_backtick_tokens(text, corpus):
        return None
    if _has_ungrounded_identifiers(text, corpus):
        return None
    if _has_ungrounded_scope_claims(text, pack, corpus):
        return None

    if len(text) > MAX_LABEL_CHARS:
        text = text[: MAX_LABEL_CHARS - 1].rstrip() + "…"
    return text


def _pack_support_corpus(pack: CaptionEvidencePack) -> set[str]:
    """Lowercased tokens / fragments the label may legitimately mention."""
    parts: list[str] = [
        pack.path,
        pack.symbol_name,
        pack.deterministic_caption,
        pack.purpose_hint,
        pack.implication_who,
        pack.implication_what,
        pack.risk_tier,
    ]
    for line in pack.edit_lines:
        parts.append(line.text)
    measured = pack.measured
    if measured.return_expr:
        parts.append(measured.return_expr)
    if measured.assign:
        parts.append(measured.assign)
    parts.extend(measured.callees)
    parts.extend(measured.import_modules)
    parts.extend(pack.allowed_tokens)

    corpus: set[str] = set()
    for part in parts:
        raw = (part or "").strip()
        if not raw:
            continue
        corpus.add(raw.lower())
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", raw):
            bare = token.split(".")[-1].lower()
            if bare:
                corpus.add(bare)
            corpus.add(token.lower())
    return corpus


def _backtick_bares(text: str) -> list[str]:
    out: list[str] = []
    for raw in _BACKTICK_RE.findall(text):
        bare = raw.split("(")[0].strip()
        if bare:
            out.append(bare)
    return out


def _token_supported(token: str, corpus: set[str]) -> bool:
    lower = token.lower()
    if lower in corpus:
        return True
    # Expression fragments (e.g. helper from helper()) already in measured slots.
    return any(
        lower in entry or entry in lower
        for entry in corpus
        if len(entry) > 2 and len(lower) > 2
    )


def _has_unknown_backtick_tokens(text: str, corpus: set[str]) -> bool:
    return any(not _token_supported(bare, corpus) for bare in _backtick_bares(text))


def _has_ungrounded_identifiers(text: str, corpus: set[str]) -> bool:
    """Reject CamelCase / snake_case names that never appear in the pack."""
    # Drop backticks so we don't double-count; backticks already validated.
    plain = _BACKTICK_RE.sub(" ", text)
    candidates = [*_SNAKE_RE.findall(plain), *_CAMEL_RE.findall(plain)]
    return any(not _token_supported(name, corpus) for name in candidates)


def _has_ungrounded_scope_claims(
    text: str,
    pack: CaptionEvidencePack,
    corpus: set[str],
) -> bool:
    """Reject caller/downstream/depends claims unless the pack already said so."""
    match = _SCOPE_RE.search(text)
    if not match:
        return False
    who = (pack.implication_who or "").lower()
    what = (pack.implication_what or "").lower()
    hint = (pack.purpose_hint or "").lower()
    det = (pack.deterministic_caption or "").lower()
    support_blob = f"{who} {what} {hint} {det}"
    phrase = match.group(0).lower()
    if phrase in support_blob:
        return False
    # Stem: "callers" / "caller", "depends" / "dependents"
    stem = re.sub(r"s$", "", phrase.split()[0])
    if stem and stem in support_blob:
        return False
    if any(stem in entry or phrase in entry for entry in corpus if len(entry) > 2):
        return False
    return True
