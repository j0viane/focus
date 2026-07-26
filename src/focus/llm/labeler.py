"""Orchestrate pack → provider → validate for every caption when opt-in."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from focus.llm.clients import LabelClient, build_client
from focus.llm.pack import (
    build_evidence_pack,
    build_orphan_evidence_pack,
    pack_as_prompt_json,
    pack_contains_secrets,
)
from focus.llm.settings import load_llm_settings
from focus.llm.validate import validate_label
from focus.models import (
    ChangedSymbolInfo,
    EvidenceItem,
    LineExplanation,
    ModuleFacts,
    RiskTier,
    SymbolExplanation,
)

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

    from focus.llm.cache import get_cached_caption, pack_fingerprint, put_cached_caption
    from focus.llm.clients import (
        DEFAULT_ANTHROPIC_MODEL,
        DEFAULT_OLLAMA_MODEL,
        DEFAULT_OPENAI_MODEL,
    )

    # Injected clients (tests / custom) skip the shared cache so prior hits
    # cannot mask fail-closed validate behavior.
    use_cache = client is None
    if settings.model:
        model = settings.model
    elif settings.provider == "ollama":
        model = DEFAULT_OLLAMA_MODEL
    elif settings.provider == "anthropic":
        model = DEFAULT_ANTHROPIC_MODEL
    else:
        model = DEFAULT_OPENAI_MODEL
    key = pack_fingerprint(pack, model=model) if use_cache else None
    if key is not None:
        cached = get_cached_caption(key)
        if cached is not None:
            return cached

    raw = active.label(pack_as_prompt_json(pack))
    if raw is None:
        return None
    labeled = validate_label(raw, pack)
    if labeled and key is not None:
        put_cached_caption(key, labeled)
    return labeled


def apply_llm_captions(
    explanations: list[SymbolExplanation],
    *,
    context: ExplainContext,
    client: LabelClient | None = None,
    path_filter: set[str] | None = None,
) -> list[SymbolExplanation]:
    """Label every non-test symbol caption (opt-in; never on live overlay).

    When ``path_filter`` is set, only those relative paths are labeled (visible-
    file-first). Fail-closed validate keeps the deterministic caption when
    ungrounded. Labels run in parallel (``FOCUS_LLM_CONCURRENCY``, default 8).
    """
    if not explanations:
        return []
    settings = load_llm_settings()
    active = client or build_client(settings)
    workers = 1 if active is None else max(1, min(16, int(settings.concurrency)))

    def _one(explanation: SymbolExplanation) -> SymbolExplanation:
        if path_filter is not None and explanation.symbol.path not in path_filter:
            return explanation
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
    # Test fixtures / fakes: silence beats LLM name-soup (ROA).
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


def apply_llm_line_captions(
    line_explanations: list[LineExplanation],
    *,
    risk: RiskTier,
    facts_by_path: dict[str, ModuleFacts],
    overlay_texts: dict[str, str] | None = None,
    client: LabelClient | None = None,
    path_filter: set[str] | None = None,
) -> list[LineExplanation]:
    """Label every non-test orphan caption (opt-in only).

    Module-assign orphans include Phase 4d readers/importers when known.
    Other orphans still get a pack from edit lines + deterministic caption.
    When ``path_filter`` is set, only those paths are labeled.
    Fail-closed: any validation failure keeps the deterministic caption.
    """
    if not line_explanations:
        return []
    settings = load_llm_settings()
    active = client or build_client(settings)
    if active is None:
        return line_explanations
    overlay_texts = overlay_texts or {}

    def _one(item: LineExplanation) -> LineExplanation:
        if path_filter is not None and item.path not in path_filter:
            return item
        return _maybe_label_line(
            item,
            risk=risk,
            facts_by_path=facts_by_path,
            overlay_texts=overlay_texts,
            client=active,
        )

    workers = max(1, min(16, int(settings.concurrency)))
    if workers == 1 or len(line_explanations) == 1:
        return [_one(item) for item in line_explanations]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, line_explanations))


def _maybe_label_line(
    item: LineExplanation,
    *,
    risk: RiskTier,
    facts_by_path: dict[str, ModuleFacts],
    overlay_texts: dict[str, str],
    client: LabelClient,
) -> LineExplanation:
    from focus.hud.edit_facts import (
        importers_of_name,
        module_level_assignments,
        same_file_readers,
    )

    if _is_test_path(item.path):
        return item
    if not (item.detail or "").strip():
        return item
    facts = facts_by_path.get(item.path)
    source = _source_for_pack(facts, overlay_texts.get(item.path))
    if not source:
        return item
    source_text = "\n".join(source)

    run = sorted(item.changed_lines or [item.line])
    run_set = set(run)
    assigns = [
        a
        for a in module_level_assignments(source_text)
        if any(a.line <= line <= a.end_line for line in run_set)
    ]
    readers: list[str] = []
    importers: list[str] = []
    reader_doc = ""
    name = ""
    if assigns:
        assign = min(assigns, key=lambda a: (a.line, a.name))
        name = assign.name
        for reader in same_file_readers(assign.name, source_text):
            if reader.name not in readers:
                readers.append(reader.name)
        importers = importers_of_name(assign.name, item.path, facts_by_path)
        if readers and facts is not None:
            for definition in facts.definitions:
                if definition.name == readers[0] and definition.docstring:
                    reader_doc = definition.docstring
                    break
    else:
        name = PurePosixPath(item.path).stem or "edit"

    pack = build_orphan_evidence_pack(
        path=item.path,
        name=name or "edit",
        risk=risk,
        run_lines=run,
        source_lines=source,
        deterministic_caption=item.detail,
        readers=readers,
        importers=importers,
        reader_doc=reader_doc,
    )
    labeled = label_caption(pack, client=client)
    if not labeled:
        return item
    return item.model_copy(update={"detail": labeled})


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
