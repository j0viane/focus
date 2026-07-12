"""Plain-English explanations for changed symbols (deterministic, graph-backed)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

import networkx as nx

from focus.hud.classify import (
    _format_path_list,
    is_danger_path,
    list_importers,
    shared_hub_reason,
)
from focus.models import (
    ChangedSymbolInfo,
    EvidenceItem,
    ExplanationClause,
    HunkDetail,
    Import,
    ModuleFacts,
    RiskTier,
    SymbolExplanation,
)

MAX_EXPLANATION_CHARS = 260
MAX_SUMMARY_CHARS = 110
MAX_CALL_EVIDENCE_PER_FILE = 2


@dataclass(frozen=True)
class ExplainContext:
    """Graph + facts needed to explain changed symbols with evidence."""

    symbols: list[ChangedSymbolInfo]
    graph: nx.DiGraph
    seeds: list[str]
    danger_paths: set[str]
    downstream_count: int
    risk: RiskTier
    facts_by_path: dict[str, ModuleFacts]


def explain_symbols(context: ExplainContext) -> list[SymbolExplanation]:
    """Build a traced explanation for every changed symbol in the audit context."""
    return [explain_symbol_with_evidence(sym, context=context) for sym in context.symbols]


def explain_symbol_with_evidence(
    symbol: ChangedSymbolInfo,
    *,
    context: ExplainContext,
) -> SymbolExplanation:
    """Explain one symbol and record proven vs heuristic evidence for each clause."""
    facts = context.facts_by_path.get(symbol.path)
    purpose_text, purpose_evidence = _symbol_purpose_with_evidence(symbol, symbol.path, facts)
    impact_text, impact_evidence = _impact_clause_with_evidence(
        symbol,
        symbol.path,
        graph=context.graph,
        seeds=context.seeds,
        danger_paths=context.danger_paths,
        downstream_count=context.downstream_count,
        risk=context.risk,
        facts_by_path=context.facts_by_path,
    )

    overlap = EvidenceItem(
        confidence="proven",
        kind="diff_overlap",
        location=f"{symbol.path}:{symbol.line}",
        fact=(
            f"git diff touches {symbol.kind} `{symbol.name}` "
            f"on line(s) {_format_changed_lines(symbol)}"
        ),
    )

    clauses: list[ExplanationClause] = [
        ExplanationClause(
            role="purpose",
            text=purpose_text,
            evidence=[overlap, *purpose_evidence],
        ),
    ]
    if impact_text:
        clauses.append(
            ExplanationClause(role="impact", text=impact_text, evidence=impact_evidence),
        )

    purpose_inline = _scrub_self_file_noise(purpose_text, symbol.path)
    # Impact first in full text; summary is high-level only (IDE header above `def`).
    display_parts = [impact_text, purpose_inline] if impact_text else [purpose_inline]
    text = expand_acronyms_for_juniors(" ".join(display_parts))
    if len(text) > MAX_EXPLANATION_CHARS:
        text = text[: MAX_EXPLANATION_CHARS - 1].rstrip() + "…"
    summary = expand_acronyms_for_juniors(
        _inline_summary(
            symbol,
            impact_text,
            downstream_count=context.downstream_count,
            risk=context.risk,
            seeds=context.seeds,
        )
    )
    hunk_details = _build_hunk_details(symbol, facts, purpose_inline)
    detail = (
        hunk_details[0].detail
        if hunk_details
        else expand_acronyms_for_juniors(_inline_detail(purpose_inline))
    )

    return SymbolExplanation(
        symbol=symbol.model_copy(
            update={
                "explanation": text,
                "summary": summary,
                "detail": detail,
                "hunk_details": hunk_details,
            }
        ),
        text=text,
        clauses=clauses,
    )


def explain_changed_symbol(
    symbol: ChangedSymbolInfo,
    *,
    graph: nx.DiGraph,
    seeds: list[str],
    danger_paths: set[str],
    downstream_count: int,
    risk: RiskTier,
    facts_by_path: dict[str, ModuleFacts] | None = None,
) -> str:
    """One or two sentences a junior can read inline in the diff."""
    context = ExplainContext(
        symbols=[symbol],
        graph=graph,
        seeds=seeds,
        danger_paths=danger_paths,
        downstream_count=downstream_count,
        risk=risk,
        facts_by_path=facts_by_path or {},
    )
    return explain_symbol_with_evidence(symbol, context=context).text


def split_explanation_for_inline(text: str, *, max_len: int = 110) -> list[str]:
    """Break explanation into CodeLens-sized lines."""
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if len(candidate) > max_len and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _inline_summary(
    symbol: ChangedSymbolInfo,
    impact_text: str,
    *,
    downstream_count: int,
    risk: RiskTier,
    seeds: list[str],
) -> str:
    """Short IDE header above `def` — symbol-specific impact or blast-radius tier only.

    Module import lists belong in the HUD Mermaid map, not inline.
    """
    if impact_text and _impact_belongs_inline(impact_text):
        return impact_text
    if downstream_count > 0 and symbol.path in seeds:
        file_word = "file" if downstream_count == 1 else "files"
        return (
            f"Part of a {risk} blast radius — {downstream_count} downstream "
            f"{file_word} may be affected."
        )
    return ""


def _impact_belongs_inline(impact_text: str) -> bool:
    """File-level import chatter is HUD-only; keep proven symbol edges inline."""
    lower = impact_text.lower()
    hud_only = (
        "module imported by",
        "imports this file",
        "only invoked inside this file",
        "no proven direct callers",
    )
    return not any(marker in lower for marker in hud_only)


def _inline_detail(purpose_text: str) -> str:
    """Purpose-only text at the primary edit site (full text; extension word-wraps)."""
    return purpose_text


# Spelled out on first use in any junior-facing explainer (extension + CLI).
# Editor-agnostic: VS Code and Cursor both consume this from the Focus backend.
_JUNIOR_ACRONYMS: tuple[tuple[str, str], ...] = (
    ("AST", "Abstract Syntax Tree"),
    ("BFS", "breadth-first search"),
    ("DFS", "depth-first search"),
    ("HUD", "heads-up display"),
    ("CLI", "command-line interface"),
)


def expand_acronyms_for_juniors(text: str) -> str:
    """Expand the first bare use of each known acronym: AST → AST (Abstract Syntax Tree).

    Skips acronyms already written as ``ACRONYM (Full Name)``. Safe to run on every
    summary/detail/explanation string so VS Code and Cursor users get the same copy.
    """
    if not text:
        return text
    out = text
    for acronym, expansion in _JUNIOR_ACRONYMS:
        already = f"{acronym} ({expansion})"
        if already in out:
            continue
        pattern = re.compile(rf"\b{re.escape(acronym)}\b(?!\s*\()")
        out, _count = pattern.subn(already, out, count=1)
    return out


_BUILTIN_CALLS = frozenset(
    {
        "isinstance",
        "len",
        "str",
        "int",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "range",
        "sorted",
        "max",
        "min",
        "any",
        "all",
        "super",
        "print",
        "type",
        "getattr",
        "setattr",
        "hasattr",
        "return",
        "yield",
        "raise",
    },
)


def _contiguous_line_runs(lines: list[int]) -> list[list[int]]:
    if not lines:
        return []
    ordered = sorted(set(lines))
    runs: list[list[int]] = [[ordered[0]]]
    for line in ordered[1:]:
        if line == runs[-1][-1] + 1:
            runs[-1].append(line)
        else:
            runs.append([line])
    return runs


def _source_lines(facts: ModuleFacts | None) -> list[str] | None:
    if facts is None or not facts.path.is_file():
        return None
    try:
        return facts.path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def _detail_without_symbol_name(text: str, name: str) -> str:
    """Drop the enclosing symbol name — the IDE header already shows it."""
    if not text:
        return ""
    esc = re.escape(name)
    out = re.sub(rf"^`{esc}`\s*—\s*", "", text)
    out = re.sub(rf"^`{esc}`\s+", "", out)
    out = re.sub(rf"^{esc}\s+", "", out)
    if out and out[0].islower():
        out = out[0].upper() + out[1:]
    return out.strip()


def _detail_for_hunk(
    lines: list[str],
    *,
    symbol_name: str,
    fallback: str,
) -> str:
    if not lines:
        return _detail_without_symbol_name(fallback, symbol_name)

    blob = "\n".join(lines)
    compact = re.sub(r"\s+", "", blob.lower())

    if re.search(r"isinstance\s*\([^)]*classdef", blob, re.IGNORECASE):
        return "Saves this class (name, line, docstring) into `definitions` from the AST."
    if re.search(r"isinstance\s*\([^)]*functiondef", blob, re.IGNORECASE):
        return "Saves this function (name, line, docstring) into `definitions` from the AST."

    if re.search(r"""kind\s*=\s*['"]class['"]""", blob):
        return "Records this as a class in the AST."
    if re.search(r"""kind\s*=\s*['"]function['"]""", blob):
        return "Records this as a function in the AST."

    if re.search(r"name\s*=\s*node\.name", blob):
        return "Uses the node's name as the definition name."

    if re.search(r"docstring\s*=\s*_first_docstring_line", blob):
        return "Keeps the first line of the docstring for later explanations."

    append_m = re.search(r"(\w+)\.append\s*\(", blob)
    if append_m:
        var = append_m.group(1)
        kind_m = re.search(r"""kind\s*=\s*['"](\w+)['"]""", blob)
        if kind_m:
            return f"Adds this `{kind_m.group(1)}` to `{var}` so the file's inventory includes it."
        if "Definition(" in blob:
            return f"Adds this definition to `{var}` so the file's inventory includes it."
        return f"Adds a new item to `{var}`."

    if any(re.search(r"^\s*return\b", line) for line in lines):
        return "Changes what this function returns."

    calls = re.findall(r"(?<!\.)([a-z_][\w]*)\s*\(", blob, re.IGNORECASE)
    for callee in reversed(calls):
        if callee.lower() not in _BUILTIN_CALLS and callee != symbol_name:
            return f"Calls `{callee}(…)` here."

    assign_m = re.match(r"\s*(\w+)\s*=", lines[0])
    if assign_m and assign_m.group(1) not in ("if", "elif", "for", "while"):
        return f"Updates `{assign_m.group(1)}` here."

    if "classdef" in compact and "functiondef" not in compact:
        return "Records this as a class in the AST."
    if "functiondef" in compact or "asyncfunctiondef" in compact:
        return "Records this as a function in the AST."

    return _detail_without_symbol_name(fallback, symbol_name)


def _build_hunk_details(
    symbol: ChangedSymbolInfo,
    facts: ModuleFacts | None,
    purpose_fallback: str,
) -> list[HunkDetail]:
    """One site-specific detail per contiguous edit block (no parent symbol name)."""
    fallback = expand_acronyms_for_juniors(
        _detail_without_symbol_name(purpose_fallback, symbol.name)
    )
    if not symbol.changed_lines:
        anchor = symbol.line
        return [HunkDetail(line=anchor, changed_lines=[anchor], detail=fallback)]

    source = _source_lines(facts)
    runs = _contiguous_line_runs(symbol.changed_lines)[:6]
    out: list[HunkDetail] = []
    for run in runs:
        anchor = run[0]
        if source:
            run_text = [source[line - 1] for line in run if 0 < line <= len(source)]
        else:
            run_text = []
        detail = _detail_for_hunk(run_text, symbol_name=symbol.name, fallback=purpose_fallback)
        detail = expand_acronyms_for_juniors(detail)
        out.append(HunkDetail(line=anchor, changed_lines=run, detail=detail))
    return out


def _scrub_self_file_noise(text: str, path: str) -> str:
    """Drop self-file path clutter — the reader is already in this file."""
    if not text:
        return text
    filename = PurePosixPath(path).name
    candidates = {path, filename}
    if path.startswith("src/"):
        candidates.add(path[4:])
    out = text
    for candidate in sorted(candidates, key=len, reverse=True):
        if not candidate:
            continue
        esc = re.escape(candidate)
        out = re.sub(rf"\s+in `{esc}`", "", out, flags=re.IGNORECASE)
        out = re.sub(rf"\s+lives in `{esc}`", "", out, flags=re.IGNORECASE)
        out = re.sub(rf"\s+for `{esc}`", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r" — — ", " — ", out)
    out = re.sub(r"` — is defined here\.?$", "` — see implementation.", out)
    return out


def _format_changed_lines(symbol: ChangedSymbolInfo) -> str:
    if symbol.changed_lines:
        return ", ".join(str(line) for line in symbol.changed_lines)
    return str(symbol.line)


def enrich_changed_symbols(
    symbols: list[ChangedSymbolInfo],
    *,
    graph: nx.DiGraph,
    seeds: list[str],
    danger_paths: set[str],
    downstream_count: int,
    risk: RiskTier,
    facts_by_path: dict[str, ModuleFacts] | None = None,
) -> list[ChangedSymbolInfo]:
    """Attach inline explanations to each changed symbol."""
    if not symbols:
        return []
    context = ExplainContext(
        symbols=symbols,
        graph=graph,
        seeds=seeds,
        danger_paths=danger_paths,
        downstream_count=downstream_count,
        risk=risk,
        facts_by_path=facts_by_path or {},
    )
    return [explain_symbol_with_evidence(sym, context=context).symbol for sym in symbols]


def _symbol_purpose_with_evidence(
    symbol: ChangedSymbolInfo,
    path: str,
    facts: ModuleFacts | None,
) -> tuple[str, list[EvidenceItem]]:
    doc = _definition_docstring(facts, symbol)
    if doc and _docstring_adds_value(symbol.name, doc):
        line = _definition_line(facts, symbol)
        return (
            _purpose_from_docstring(symbol.name, doc),
            [
                EvidenceItem(
                    confidence="proven",
                    kind="docstring",
                    location=f"{path}:{line}" if line else path,
                    fact=f'docstring: "{doc}"',
                ),
            ],
        )

    name = symbol.name
    lower = name.lower()
    snake = _snake_name(name)
    snake_core = snake.lstrip("_")
    padded = f"/{path}"
    posix = PurePosixPath(path)

    for key in (lower, snake):
        exact = _EXACT_SYMBOL_PURPOSE.get(key)
        if exact:
            return (
                exact.format(name=name, path=path),
                [
                    EvidenceItem(
                        confidence="heuristic",
                        kind="symbol_registry",
                        location=path,
                        fact=f'matched built-in symbol rule "{key}"',
                    ),
                ],
            )

    if symbol.kind == "class":
        text = _class_purpose(name, lower, snake, path, padded)
        return text, _heuristic_name_evidence(name, "class name / suffix pattern")

    if (
        snake.startswith("test_")
        or lower.startswith("test")
        or "/tests/" in padded
        or posix.name.startswith("test_")
    ):
        subject = _humanize_name(snake.removeprefix("test_"))
        return (
            f"`{name}` is an automated test that {subject} still works.",
            [
                EvidenceItem(
                    confidence="proven",
                    kind="test_module",
                    location=path,
                    fact="test file path or test_ function name",
                ),
            ],
        )

    for prefix, template in _VERB_PREFIX_PURPOSE:
        if snake_core.startswith(prefix):
            rest = _humanize_name(snake_core[len(prefix) :])
            return (
                template.format(name=name, rest=rest, path=path),
                _heuristic_name_evidence(name, f'name prefix "{prefix}"'),
            )

    for suffix, template in _SUFFIX_PURPOSE:
        if snake_core.endswith(suffix) or snake.endswith(suffix):
            stem = _humanize_name(snake[: -len(suffix)])
            return (
                template.format(name=name, stem=stem, path=path),
                _heuristic_name_evidence(name, f'name suffix "{suffix}"'),
            )

    if name.startswith("_") or snake.startswith("_"):
        return (
            f"`{name}` — on the call path to other modules; check callers before merging.",
            _heuristic_name_evidence(name, "leading underscore (internal)"),
        )

    file_hint = _file_purpose_hint(path, padded, posix.name)
    if file_hint:
        return (
            f"`{name}` {file_hint}",
            [
                EvidenceItem(
                    confidence="heuristic",
                    kind="heuristic_path",
                    location=path,
                    fact=f"file path pattern for `{posix.name}`",
                ),
            ],
        )

    return (
        f"`{name}` — other code may call or import this {symbol.kind}.",
        _heuristic_name_evidence(name, "generic fallback (no docstring or name rule)"),
    )


def _impact_clause_with_evidence(
    symbol: ChangedSymbolInfo,
    path: str,
    *,
    graph: nx.DiGraph,
    seeds: list[str],
    danger_paths: set[str],
    downstream_count: int,
    risk: RiskTier,
    facts_by_path: dict[str, ModuleFacts],
) -> tuple[str, list[EvidenceItem]]:
    evidence: list[EvidenceItem] = []
    if _is_test_path(path):
        return _test_only_impact(path)

    if path in graph and path in seeds:
        importers = list_importers(graph, path)
        if importers:
            callers, caller_evidence = _users_with_evidence(
                symbol.name,
                path,
                importers,
                facts_by_path,
                kind=symbol.kind,
            )
            evidence.extend(caller_evidence)
            if callers:
                impact_text = _format_user_impact(symbol, callers)
                if len(callers) == 1:
                    tail = _caller_consequence(callers[0])
                    if tail:
                        evidence.append(
                            EvidenceItem(
                                confidence="heuristic",
                                kind="heuristic_path",
                                location=callers[0],
                                fact=f'caller path label "{tail.strip()}"',
                            ),
                        )
                return impact_text, evidence
            for importer in importers:
                evidence.append(
                    EvidenceItem(
                        confidence="proven",
                        kind="graph_importer",
                        location="graph",
                        fact=f"`{importer}` → `{path}` (file imports file)",
                    ),
                )
            if _has_internal_calls(symbol.name, path, facts_by_path):
                return (
                    f"`{symbol.name}` is only invoked inside this file; "
                    f"the module is imported by {_format_path_list(importers)}."
                ), evidence
            if len(importers) == 1:
                role = _importer_role(importers[0])
                if role.startswith(" and ") or role.startswith(" for "):
                    evidence.append(
                        EvidenceItem(
                            confidence="heuristic",
                            kind="heuristic_path",
                            location=importers[0],
                            fact=f"importer role label: {role.strip()}",
                        ),
                    )
                return f"`{importers[0]}` imports this file{role}.", evidence
            return (
                f"Module imported by {_format_path_list(importers)} — "
                f"no proven direct callers of `{symbol.name}` in those files."
            ), evidence
        if path in danger_paths and is_danger_path(path):
            return (
                "This file is an API, schema, or config surface — "
                "external callers may depend on it.",
                [
                    EvidenceItem(
                        confidence="proven",
                        kind="danger_path",
                        location=path,
                        fact="path matches API / schema / config Danger Zone rules",
                    ),
                ],
            )
        if path in danger_paths:
            reason = shared_hub_reason(graph, path, changed=True).rstrip(".")
            return reason + ".", [
                EvidenceItem(
                    confidence="proven",
                    kind="shared_hub",
                    location=path,
                    fact=reason,
                ),
            ]
    if downstream_count > 0 and path in seeds:
        file_word = "file" if downstream_count == 1 else "files"
        return (
            f"Part of a {risk} blast radius — {downstream_count} downstream "
            f"{file_word} may be affected.",
            [
                EvidenceItem(
                    confidence="proven",
                    kind="downstream_count",
                    location="graph",
                    fact=f"{downstream_count} downstream {file_word} from changed seeds",
                ),
            ],
        )
    return "", evidence


def _has_internal_calls(
    symbol_name: str,
    path: str,
    facts_by_path: dict[str, ModuleFacts],
) -> bool:
    facts = facts_by_path.get(path)
    if not facts:
        return False
    return any(
        call.callee == symbol_name or call.callee.endswith(f".{symbol_name}")
        for call in facts.calls
    )


def _test_only_impact(path: str) -> tuple[str, list[EvidenceItem]]:
    return (
        "Test-only — validates behavior in CI; does not run in production.",
        [
            EvidenceItem(
                confidence="proven",
                kind="test_module",
                location=path,
                fact="changed file is a test module (tests/ or test_*.py)",
            ),
        ],
    )


def _users_with_evidence(
    symbol_name: str,
    seed_path: str,
    importers: list[str],
    facts_by_path: dict[str, ModuleFacts],
    *,
    kind: str,
) -> tuple[list[str], list[EvidenceItem]]:
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
            if _import_references_symbol(imp, symbol_name, seed_stem)
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
            lines = ", ".join(str(call.line) for call in matching_calls[MAX_CALL_EVIDENCE_PER_FILE :])
            evidence.append(
                EvidenceItem(
                    confidence="proven",
                    kind="call",
                    location=importer,
                    fact=f"+{extra} more {use_verb} at lines {lines}",
                ),
            )
    return users, evidence


def _split_prod_test(paths: list[str]) -> tuple[list[str], list[str]]:
    prod = [p for p in paths if not _is_test_path(p)]
    test = [p for p in paths if _is_test_path(p)]
    return prod, test


def _is_test_path(path: str) -> bool:
    return "/tests/" in f"/{path}" or PurePosixPath(path).name.startswith("test_")


def _format_user_impact(symbol: ChangedSymbolInfo, users: list[str]) -> str:
    name = symbol.name
    if len(users) == 1:
        verb = "constructs" if symbol.kind == "class" else "calls"
        tail = _caller_consequence(users[0])
        return f"`{users[0]}` {verb} `{name}`{tail}."

    prod, test = _split_prod_test(users)
    if symbol.kind == "class":
        if prod and test:
            return (
                f"`{name}` is constructed in {_format_path_list(prod)} "
                f"(also referenced in tests)."
            )
        if prod:
            return (
                f"`{name}` is constructed in {_format_path_list(prod)} — "
                f"regressions surface in those flows first."
            )
        return f"`{name}` is referenced in {_format_path_list(test)} in tests."

    if prod and test:
        return (
            f"`{name}` is called from {_format_path_list(prod)} "
            f"(also covered in tests)."
        )
    if prod:
        return (
            f"`{name}` is called from {_format_path_list(prod)} — "
            f"regressions surface in those flows first."
        )
    return f"`{name}` is called from {_format_path_list(test)} in tests."


def _callers_with_evidence(
    symbol_name: str,
    seed_path: str,
    importers: list[str],
    facts_by_path: dict[str, ModuleFacts],
) -> tuple[list[str], list[EvidenceItem]]:
    return _users_with_evidence(
        symbol_name, seed_path, importers, facts_by_path, kind="function",
    )


def _heuristic_name_evidence(name: str, rule: str) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            confidence="heuristic",
            kind="heuristic_name",
            location=name,
            fact=rule,
        ),
    ]


def _definition_line(facts: ModuleFacts | None, symbol: ChangedSymbolInfo) -> int | None:
    if not facts:
        return symbol.line
    for definition in facts.definitions:
        if (
            definition.name == symbol.name
            and definition.kind == symbol.kind
            and definition.line == symbol.line
        ):
            return definition.line
    return symbol.line


def _class_purpose(name: str, lower: str, snake: str, path: str, padded: str) -> str:
    if "codelens" in lower.replace("_", ""):
        return f"`{name}` shows Focus hints inline above changed lines in the editor."
    for suffix, template in _CLASS_SUFFIX_PURPOSE:
        if lower.endswith(suffix.lower()) or snake.endswith(_snake_name(suffix)):
            stem = _humanize_name(snake[: -len(_snake_name(suffix))])
            return template.format(name=name, stem=stem, path=path)
    if "provider" in lower:
        return f"`{name}` wires editor features (CodeLens, gutters, panels)."
    return f"`{name}` — other modules instantiate or subclass this class."


def _snake_name(name: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def _definition_docstring(
    facts: ModuleFacts | None,
    symbol: ChangedSymbolInfo,
) -> str | None:
    if not facts:
        return None
    for definition in facts.definitions:
        if (
            definition.name == symbol.name
            and definition.kind == symbol.kind
            and definition.line == symbol.line
        ):
            return definition.docstring
    for definition in facts.definitions:
        if definition.name == symbol.name and definition.docstring:
            return definition.docstring
    return None


def _purpose_from_docstring(name: str, doc: str) -> str:
    first = doc.strip().rstrip(".")
    if not first:
        return f"`{name}` is defined here."
    if first[0].islower():
        first = first[0].upper() + first[1:]
    return f"`{name}` — {first}."


_DOCSTRING_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "to",
        "for",
        "of",
        "in",
        "into",
        "from",
        "with",
        "and",
        "or",
        "is",
        "are",
        "this",
        "that",
        "each",
        "every",
        "when",
        "if",
        "by",
        "on",
        "at",
        "as",
        "be",
        "it",
        "all",
        "any",
        "not",
    },
)

_GENERIC_DOC_VERBS = frozenset(
    {
        "attach",
        "add",
        "append",
        "apply",
        "break",
        "split",
        "wrap",
        "build",
        "create",
        "make",
        "format",
        "return",
        "get",
        "set",
        "load",
        "save",
        "run",
        "handle",
        "process",
        "compute",
        "calculate",
        "convert",
        "transform",
        "generate",
        "produce",
        "enrich",
        "explain",
        "render",
        "parse",
        "extract",
        "register",
        "update",
        "write",
        "read",
        "fetch",
    },
)


def _docstring_adds_value(name: str, doc: str) -> bool:
    """Skip one-line docstrings that only restate the symbol name or its verb stem."""
    text = doc.strip().rstrip(".")
    if not text:
        return False

    lower = text.lower()
    if len(text) > 120:
        return True
    if re.search(r"\b(when|unless|returns?|raises?|never|must|should|only)\b", lower):
        return True
    if re.search(r'["\'`]|\d|::|->', text):
        return True

    name_tokens = _name_token_set(name)
    doc_tokens = {_stem_token(w) for w in re.findall(r"[a-z0-9]+", lower)}
    doc_content = doc_tokens - _DOCSTRING_STOP_WORDS - _GENERIC_DOC_VERBS - _GENERIC_SURFACE_WORDS

    if not doc_content:
        return False

    novel = _novel_doc_tokens(doc_content, name_tokens)
    if not novel:
        return False

    overlap = len(doc_tokens & name_tokens) / max(len(doc_tokens - _DOCSTRING_STOP_WORDS), 1)
    if overlap >= 0.45 and len(text) < 95:
        return False

    return True


def _stem_token(word: str) -> str:
    w = word.lower()
    if w.endswith("s") and len(w) > 3:
        w = w[:-1]
    return w


def _name_token_set(name: str) -> set[str]:
    words = {_stem_token(w) for w in _humanize_name(name).split()}
    expanded = set(words)
    for w in list(words):
        expanded |= _VERB_SYNONYMS.get(w, set())
        expanded |= _OBJECT_SYNONYMS.get(w, set())
    return expanded


def _novel_doc_tokens(doc_content: set[str], name_tokens: set[str]) -> set[str]:
    novel = set(doc_content - name_tokens)
    for token in list(novel):
        inferable_from = _INFERABLE_OBJECT.get(token, set())
        if inferable_from & name_tokens:
            novel.discard(token)
    return novel


_VERB_SYNONYMS: dict[str, set[str]] = {
    "enrich": {"attach", "add", "append", "inject"},
    "split": {"break", "wrap", "chunk", "partition"},
    "attach": {"enrich", "add", "append"},
    "break": {"split", "wrap", "chunk"},
    "wrap": {"split", "break", "format"},
    "explain": {"describe", "summarize"},
}

_OBJECT_SYNONYMS: dict[str, set[str]] = {
    "symbol": {"symbols", "function", "method", "class"},
    "symbols": {"symbol", "function", "method", "class"},
    "explanation": {"explanations", "summary", "caption", "context"},
    "explanations": {"explanation", "summary", "caption", "context"},
}

_INFERABLE_OBJECT: dict[str, set[str]] = {
    "explanation": {"enrich", "explain", "describe", "summarize"},
    "explanations": {"enrich", "explain", "describe", "summarize"},
    "line": {"split", "wrap", "format", "break"},
    "lines": {"split", "wrap", "format", "break"},
    "codelen": {"split", "wrap", "format", "render"},
    "codelens": {"split", "wrap", "format", "render"},
    "field": {"enrich", "build", "make", "append"},
    "fields": {"enrich", "build", "make", "append"},
}

_GENERIC_SURFACE_WORDS = frozenset(
    {
        "inline",
        "codelens",
        "codelen",
        "sized",
        "lens",
        "lenses",
        "line",
        "lines",
        "sized",
        "row",
        "rows",
        "each",
        "every",
        "short",
        "long",
        "text",
        "string",
        "word",
        "words",
        "code",
    },
)


def _import_references_symbol(imp: Import, symbol_name: str, seed_stem: str) -> bool:
    if symbol_name not in imp.symbols and "*" not in imp.symbols:
        return False
    module = imp.module.replace("/", ".").strip(".")
    if not module:
        return True
    return seed_stem in module.split(".") or module.endswith(seed_stem)


def _caller_consequence(caller_path: str) -> str:
    padded = f"/{caller_path}"
    if "/billing/" in padded or "charge" in caller_path:
        return " before charging users"
    if "/jobs/" in padded or "worker" in caller_path:
        return " from background jobs"
    if "/api/" in padded or "/routes/" in padded:
        return " on incoming HTTP requests"
    if "/tests/" in padded:
        return " in tests"
    if "extension" in caller_path:
        return " when the extension starts"
    if caller_path.endswith("cli.py"):
        return " from CLI commands"
    return ""


def _importer_role(importer_path: str) -> str:
    name = PurePosixPath(importer_path).name
    if name == "cli.py":
        return " and exposes it through CLI commands"
    if name == "extension.ts":
        return " and wires it when the extension loads"
    if "/tests/" in f"/{importer_path}":
        return " for test coverage"
    return " — that's the first place to check if this misbehaves"


def _humanize_name(name: str) -> str:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    spaced = spaced.replace("_", " ").strip()
    return spaced.lower() if spaced else "this behavior"


def _file_purpose_hint(path: str, padded: str, filename: str) -> str:
    if filename in {"cli.py", "main.py", "__main__.py"}:
        return "is wired into the CLI — users and scripts invoke it from the terminal."
    if "/api/" in padded or "/routes/" in padded or "/routers/" in padded:
        return "is part of the HTTP API — requests from outside the repo may hit this code."
    if filename in {"settings.py", "config.py"}:
        return "reads or applies configuration that other modules load at startup."
    if filename in {"models.py", "schema.prisma"} or "/models/" in padded:
        return "defines a data shape that other modules read and write."
    if filename == "__init__.py":
        return "controls what this package exports to importers."
    if is_danger_path(path) and "/billing/" in padded:
        return "handles billing or payment logic — mistakes here affect money paths."
    if is_danger_path(path) and "auth" in padded:
        return "handles authentication — callers trust its result to allow or deny access."
    return ""


_EXACT_SYMBOL_PURPOSE: dict[str, str] = {
    "version": "`{name}` prints the installed Focus version when someone runs `focus --version`.",
    "main": "`{name}` is the program entrypoint — execution starts here when the module runs.",
    "activate": (
        "`{name}` runs when the Cursor/VS Code extension loads — "
        "it registers commands, CodeLens, and the status bar."
    ),
    "deactivate": "`{name}` runs when the extension unloads and should release resources.",
    "run_audit": (
        "`{name}` turns your git diff into a Focus HUD (risk, diagram, blast radius) — "
        "the `audit` CLI command calls this."
    ),
    "audit_local": "`{name}` is the local working-tree audit entrypoint the CLI uses.",
    "audit_pr": "`{name}` is the PR-range audit entrypoint the CLI uses.",
    "validate_token": (
        "`{name}` decides whether an incoming token is trusted — "
        "API routes rely on this before running protected logic."
    ),
    "charge": "`{name}` is the HTTP charge endpoint — it forwards requests into billing.",
    "build_html": "`{name}` renders the Focus HUD webview HTML shown beside your editor.",
    "symbol_lenses": (
        "`{name}` builds the stacked CodeLens above each changed symbol "
        "(risk badge plus inline explanation lines)."
    ),
    "split_explanation": "`{name}` wraps long explanation text into short CodeLens lines.",
    "split_explanation_for_inline": (
        "`{name}` word-wraps audit explanations for stacked CodeLens rows in the IDE."
    ),
    "enrich_changed_symbols": (
        "`{name}` is the audit hook that attaches graph-backed explanations to changed symbols."
    ),
    "_enrich_symbols": "`{name}` wraps `enrich_changed_symbols` for audit HUD assembly.",
    "_full_audit_hud": (
        "`{name}` builds the full Focus HUD (diagram, danger zones, blast radius) for CLI output."
    ),
    "explain_symbols": "`{name}` builds traced explanations for every changed symbol in an audit.",
    "explain_symbol_with_evidence": (
        "`{name}` explains one changed symbol and records proven vs heuristic evidence."
    ),
}

_VERB_PREFIX_PURPOSE: list[tuple[str, str]] = [
    ("validate_", "`{name}` checks whether {rest} is valid — callers trust this result."),
    ("is_valid_", "`{name}` returns whether {rest} is valid."),
    ("check_", "`{name}` verifies {rest} before other code continues."),
    ("authenticate_", "`{name}` authenticates {rest}."),
    ("authorize_", "`{name}` decides whether {rest} is allowed."),
    ("get_", "`{name}` reads or returns {rest}."),
    ("fetch_", "`{name}` fetches {rest} from somewhere else."),
    ("load_", "`{name}` loads {rest} into memory or scope."),
    ("read_", "`{name}` reads {rest}."),
    ("set_", "`{name}` sets or updates {rest}."),
    ("update_", "`{name}` updates {rest}."),
    ("save_", "`{name}` persists {rest}."),
    ("write_", "`{name}` writes {rest}."),
    ("create_", "`{name}` creates {rest}."),
    ("add_", "`{name}` adds {rest}."),
    ("insert_", "`{name}` inserts {rest}."),
    ("register_", "`{name}` registers {rest} with the runtime or framework."),
    ("delete_", "`{name}` deletes {rest}."),
    ("remove_", "`{name}` removes {rest}."),
    ("parse_", "`{name}` parses {rest} from raw input."),
    ("extract_", "`{name}` extracts {rest} from surrounding data."),
    ("render_", "`{name}` renders {rest} for display or output."),
    ("build_", "`{name}` builds {rest} from inputs."),
    ("format_", "`{name}` formats {rest} for humans or downstream code."),
    ("make_", "`{name}` constructs {rest}."),
    ("enrich_", "`{name}` adds derived fields (like explanations) to {rest}."),
    ("explain_", "`{name}` generates plain-English context for {rest}."),
    ("classify_", "`{name}` sorts {rest} into risk or impact buckets."),
    ("score_", "`{name}` scores {rest} for risk or severity."),
    ("list_", "`{name}` lists {rest}."),
    ("handle_", "`{name}` handles {rest} events or requests."),
    ("on_", "`{name}` runs when {rest} happens."),
    ("run_", "`{name}` runs {rest} — often a top-level workflow step."),
    ("trace_", "`{name}` traces {rest} through the dependency graph."),
    ("audit_", "`{name}` audits {rest} for blast-radius impact."),
]

_SUFFIX_PURPOSE: list[tuple[str, str]] = [
    ("_handler", "`{name}` handles {stem} requests or callbacks."),
    ("_service", "`{name}` encapsulates {stem} business logic."),
    ("_client", "`{name}` talks to an external {stem} API or service."),
    ("_panel", "`{name}` renders the {stem} UI panel in the editor."),
    ("_lenses", "`{name}` builds CodeLens lines for {stem}."),
    ("_lens", "`{name}` builds a CodeLens line for {stem}."),
]

_CLASS_SUFFIX_PURPOSE: list[tuple[str, str]] = [
    ("Provider", "`{name}` supplies {stem} behavior to the editor (CodeLens, UI hooks, etc.)."),
    ("Service", "`{name}` groups {stem} logic that other modules call into."),
    ("Client", "`{name}` is a client for talking to {stem}."),
    ("Controller", "`{name}` coordinates {stem} requests and responses."),
    ("Router", "`{name}` maps incoming routes to {stem} handlers."),
    ("Panel", "`{name}` is the webview/panel UI for {stem}."),
]
