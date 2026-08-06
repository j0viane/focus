"""Proven symbol usage for blast-radius filtering (shared with explain)."""

from __future__ import annotations

from pathlib import PurePosixPath

import networkx as nx

from focus.models import ChangedSymbolInfo, EvidenceItem, Import, ModuleFacts

MAX_CALL_EVIDENCE_PER_FILE = 2


def import_references_symbol(imp: Import, symbol_name: str, seed_stem: str) -> bool:
    """True when an import statement plausibly binds ``symbol_name`` from the seed module."""
    if symbol_name not in imp.symbols and "*" not in imp.symbols:
        return False
    module = imp.module.replace("/", ".").strip(".")
    if not module:
        return True
    return seed_stem in module.split(".") or module.endswith(seed_stem)


def users_with_evidence(
    symbol_name: str,
    seed_path: str,
    importers: list[str],
    facts_by_path: dict[str, ModuleFacts],
    *,
    kind: str,
) -> tuple[list[str], list[EvidenceItem]]:
    """Importers with proven import + call (or construct for classes) of ``symbol_name``."""
    users: list[str] = []
    evidence: list[EvidenceItem] = []
    seed_stem = PurePosixPath(seed_path).stem
    use_verb = "constructs" if kind == "class" else "calls"

    for importer in importers:
        facts = facts_by_path.get(importer)
        if not facts:
            continue
        matching_imports = [
            imp
            for imp in facts.imports
            if import_references_symbol(imp, symbol_name, seed_stem)
        ]
        matching_calls = [
            call
            for call in facts.calls
            if call.callee == symbol_name or call.callee.endswith(f".{symbol_name}")
        ]
        uses_symbol = bool(matching_imports) and (
            bool(matching_calls) or kind == "class"
        )
        if not uses_symbol:
            continue

        users.append(importer)
        evidence.append(
            EvidenceItem(
                confidence="proven",
                kind="graph_importer",
                location="graph",
                fact=f"`{importer}` → `{seed_path}`",
            ),
        )
        for imp in matching_imports[:1]:
            syms = ", ".join(imp.symbols) if imp.symbols else "(module)"
            evidence.append(
                EvidenceItem(
                    confidence="proven",
                    kind="import",
                    location=f"{importer}:{imp.line}",
                    fact=f"from {imp.module} import {syms}",
                ),
            )
        shown_calls = matching_calls[:MAX_CALL_EVIDENCE_PER_FILE]
        for call in shown_calls:
            evidence.append(
                EvidenceItem(
                    confidence="proven",
                    kind="call",
                    location=f"{importer}:{call.line}",
                    fact=f"{use_verb} `{call.callee}`",
                ),
            )
        if len(matching_calls) > MAX_CALL_EVIDENCE_PER_FILE:
            extra = len(matching_calls) - MAX_CALL_EVIDENCE_PER_FILE
            lines = ", ".join(
                str(call.line) for call in matching_calls[MAX_CALL_EVIDENCE_PER_FILE :]
            )
            evidence.append(
                EvidenceItem(
                    confidence="proven",
                    kind="call",
                    location=importer,
                    fact=f"+{extra} more {use_verb} at lines {lines}",
                ),
            )
    return users, evidence


def filter_rings_by_symbols(
    rings: list[tuple[int, list[str]]],
    graph: nx.DiGraph,
    seeds: list[str],
    symbols: list[ChangedSymbolInfo],
    facts_by_path: dict[str, ModuleFacts],
) -> list[tuple[int, list[str]]]:
    """Keep downstream files only when they use a changed symbol (or lead to one).

    Hop-1 files need proven import/call evidence for a changed symbol in a seed they
    import. Higher hops stay when there is a file-level import path to a kept hop-(n-1).
    When ``symbols`` is empty, returns ``rings`` unchanged (file-level blast radius).
    """
    if not symbols:
        return rings

    seed_set = set(seeds)
    kept_by_hop: dict[int, list[str]] = {}

    for hops, paths in sorted(rings, key=lambda item: item[0]):
        if hops == 1:
            kept = [
                path
                for path in paths
                if _hop1_uses_changed_symbols(
                    path, seed_set, symbols, graph, facts_by_path
                )
            ]
        else:
            prev_kept = set(kept_by_hop.get(hops - 1, []))
            if not prev_kept:
                kept = []
            else:
                kept = [
                    path
                    for path in paths
                    if _has_import_path_to_any(graph, path, prev_kept)
                ]
        if kept:
            kept_by_hop[hops] = sorted(kept)

    return [(hops, kept_by_hop[hops]) for hops in sorted(kept_by_hop)]


def _hop1_uses_changed_symbols(
    importer: str,
    seeds: set[str],
    symbols: list[ChangedSymbolInfo],
    graph: nx.DiGraph,
    facts_by_path: dict[str, ModuleFacts],
) -> bool:
    imported_seeds = [seed for seed in graph.successors(importer) if seed in seeds]
    if not imported_seeds:
        return False
    for seed in imported_seeds:
        for symbol in symbols:
            if symbol.path != seed:
                continue
            users, _ = users_with_evidence(
                symbol.name,
                seed,
                [importer],
                facts_by_path,
                kind=symbol.kind,
            )
            if users:
                return True
    return False


def _has_import_path_to_any(
    graph: nx.DiGraph,
    source: str,
    targets: set[str],
) -> bool:
    if source not in graph:
        return False
    reachable = nx.descendants(graph, source)
    return bool(targets & reachable)
