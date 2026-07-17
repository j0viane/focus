"""Orchestrate pack → provider → validate for every caption when opt-in."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from focus.llm.clients import LabelClient, build_client
from focus.llm.pack import (
    build_evidence_pack,
    pack_as_prompt_json,
    pack_contains_secrets,
)
from focus.llm.settings import load_llm_settings
from focus.llm.validate import validate_label
from focus.models import ChangedSymbolInfo, EvidenceItem, ModuleFacts, SymbolExplanation

if TYPE_CHECKING:
    from focus.hud.explain import ExplainContext

log = logging.getLogger("focus.llm")


def _is_test_path(path: str) -> bool:
    return "/tests/" in f"/{path}" or path.rsplit("/", 1)[-1].startswith("test_")


def label_caption(
    pack,
    *,
    client: LabelClient | None = None,
) -> str | None:
    """Call the provider and validate. Returns None on any failure."""
    if pack_contains_secrets(pack):
        log.debug("Skipping LLM label: secret-like text in edit lines")
        return None
    settings = load_llm_settings()
    active = client or build_client(settings)
    if active is None:
        return None
    raw = active.label(pack_as_prompt_json(pack))
    if raw is None:
        return None
    return validate_label(raw, pack)


def apply_llm_captions(
    explanations: list[SymbolExplanation],
    *,
    context: ExplainContext,
    client: LabelClient | None = None,
) -> list[SymbolExplanation]:
    """Replace every symbol ``detail`` / hunk caption when labeling succeeds.

    Opt-in only (never on live overlay). Fail-closed validate keeps the
    deterministic caption when the model is ungrounded or unavailable.
    Labels run in parallel (``FOCUS_LLM_CONCURRENCY``, default 4).
    """
    if not explanations:
        return []
    settings = load_llm_settings()
    active = client or build_client(settings)
    workers = 1 if active is None else max(1, min(16, int(settings.concurrency)))

    def _one(explanation: SymbolExplanation) -> SymbolExplanation:
        return _maybe_label_one(explanation, context=context, client=active)

    if workers == 1 or len(explanations) == 1:
        return [_one(item) for item in explanations]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, explanations))


def _maybe_label_one(
    explanation: SymbolExplanation,
    *,
    context: ExplainContext,
    client: LabelClient | None,
) -> SymbolExplanation:
    symbol = explanation.symbol
    # Test fixtures / fakes: silence beats LLM name-soup (ROA). Edit-shaped
    # deterministic captions still show; we just don't rewrite them via the model.
    if _is_test_path(symbol.path):
        return explanation

    facts: ModuleFacts | None = context.facts_by_path.get(symbol.path)
    source = _source_for_pack(facts, context.overlay_texts.get(symbol.path))
    purpose_hint = ""
    for clause in explanation.clauses:
        if clause.role == "purpose":
            purpose_hint = clause.text
            break

    pack = build_evidence_pack(
        symbol,
        risk=context.risk,
        implication=symbol.implication,
        purpose_hint=purpose_hint,
        facts=facts,
        source_lines=source,
    )
    labeled = label_caption(pack, client=client)
    if not labeled:
        return explanation

    hunk_details = list(symbol.hunk_details)
    if hunk_details:
        first = hunk_details[0]
        hunk_details[0] = first.model_copy(update={"detail": labeled})
    else:
        from focus.models import HunkDetail

        hunk_details = [
            HunkDetail(
                line=symbol.line,
                changed_lines=symbol.changed_lines or [symbol.line],
                detail=labeled,
            )
        ]

    evidence = list(symbol.evidence)
    evidence.append(
        EvidenceItem(
            confidence="heuristic",
            kind="llm_label",
            location=f"{symbol.path}:{symbol.line}",
            fact="caption labeled from evidence pack (opt-in LLM)",
        )
    )
    # Keep hover budget — llm_label is the trust cue when present.
    evidence = evidence[-2:] if len(evidence) > 2 else evidence

    updated = symbol.model_copy(
        update={
            "detail": labeled,
            "hunk_details": hunk_details,
            "evidence": evidence,
        }
    )
    return explanation.model_copy(update={"symbol": updated})


def _source_for_pack(
    facts: ModuleFacts | None,
    overlay_text: str | None,
) -> list[str] | None:
    if overlay_text is not None:
        return overlay_text.splitlines()
    if facts is None:
        return None
    try:
        return facts.path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def enrich_symbols_with_llm(
    symbols: list[ChangedSymbolInfo],
    *,
    context: ExplainContext,
    client: LabelClient | None = None,
) -> list[ChangedSymbolInfo]:
    """Apply labeler to already-explained symbols (detail already set)."""
    from focus.models import SymbolExplanation

    wrapped = [SymbolExplanation(symbol=s, text=s.explanation or s.detail or "") for s in symbols]
    labeled = apply_llm_captions(wrapped, context=context, client=client)
    return [item.symbol for item in labeled]
