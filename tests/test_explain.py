"""Deterministic inline explanations for changed symbols."""

from pathlib import Path

import networkx as nx

from focus.hud.explain import (
    ExplainContext,
    _compact_evidence_for_inline,
    enrich_changed_symbols,
    explain_changed_symbol,
    explain_symbol_with_evidence,
    split_explanation_for_inline,
)
from focus.models import (
    CallSite,
    ChangedSymbolInfo,
    Definition,
    EvidenceItem,
    Import,
    ModuleFacts,
)
from focus.scan.parser import parse_module


def test_parse_module_extracts_docstring(tmp_path: Path):
    path = tmp_path / "sample.py"
    path.write_text(
        'def validate_token(token: str) -> bool:\n'
        '    """Return True when the token matches the secret."""\n'
        "    return True\n"
    )
    facts = parse_module(path)
    assert facts.definitions[0].docstring == "Return True when the token matches the secret."


def test_explain_prefers_docstring_over_heuristics():
    facts = ModuleFacts(
        path=Path("auth_utils.py"),
        definitions=[
            Definition(
                name="validate_token",
                kind="function",
                line=6,
                docstring="Return True when the token matches the fixture secret.",
            ),
        ],
    )
    text = explain_changed_symbol(
        ChangedSymbolInfo(path="auth_utils.py", name="validate_token", kind="function", line=6),
        graph=nx.DiGraph(),
        seeds=["auth_utils.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={"auth_utils.py": facts},
    )
    assert "fixture secret" in text
    assert "decides whether an incoming token" not in text


def test_explain_names_callers_that_invoke_symbol():
    graph = nx.DiGraph()
    graph.add_edge("billing/service.py", "auth_utils.py")
    facts = {
        "auth_utils.py": ModuleFacts(
            path=Path("auth_utils.py"),
            definitions=[
                Definition(name="validate_token", kind="function", line=6),
            ],
        ),
        "billing/service.py": ModuleFacts(
            path=Path("billing/service.py"),
            imports=[Import(module="auth_utils", symbols=["validate_token"], line=3)],
            calls=[CallSite(callee="validate_token", line=8)],
        ),
    }
    text = explain_changed_symbol(
        ChangedSymbolInfo(path="auth_utils.py", name="validate_token", kind="function", line=6),
        graph=graph,
        seeds=["auth_utils.py"],
        danger_paths={"auth_utils.py"},
        downstream_count=3,
        risk="CRITICAL",
        facts_by_path=facts,
    )
    assert "billing/service.py" in text
    assert "calls `validate_token`" in text
    assert "charging" in text.lower()


def test_explain_class_uses_construct_not_call():
    graph = nx.DiGraph()
    graph.add_edge("src/focus/audit.py", "src/focus/hud/explain.py")
    facts = {
        "src/focus/hud/explain.py": ModuleFacts(
            path=Path("src/focus/hud/explain.py"),
            definitions=[
                Definition(
                    name="ExplainContext",
                    kind="class",
                    line=31,
                    docstring="Graph + facts needed to explain changed symbols with evidence.",
                ),
            ],
        ),
        "src/focus/audit.py": ModuleFacts(
            path=Path("src/focus/audit.py"),
            imports=[
                Import(
                    module="focus.hud.explain",
                    symbols=["ExplainContext"],
                    line=19,
                ),
            ],
            calls=[CallSite(callee="ExplainContext", line=71)],
        ),
        "tests/test_explain_cli.py": ModuleFacts(
            path=Path("tests/test_explain_cli.py"),
            imports=[
                Import(
                    module="focus.hud.explain",
                    symbols=["ExplainContext"],
                    line=10,
                ),
            ],
            calls=[CallSite(callee="ExplainContext", line=50)],
        ),
    }
    text = explain_changed_symbol(
        ChangedSymbolInfo(
            path="src/focus/hud/explain.py",
            name="ExplainContext",
            kind="class",
            line=31,
        ),
        graph=graph,
        seeds=["src/focus/hud/explain.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path=facts,
    )
    assert "constructs `ExplainContext`" in text
    assert "calls `ExplainContext`" not in text

    graph.add_edge("src/focus/cli.py", "src/focus/hud/explain.py")
    graph.add_edge("tests/test_explain_cli.py", "src/focus/hud/explain.py")
    facts["src/focus/cli.py"] = ModuleFacts(
        path=Path("src/focus/cli.py"),
        imports=[Import(module="focus.hud.explain", symbols=["ExplainContext"], line=16)],
        calls=[CallSite(callee="ExplainContext", line=221)],
    )
    multi = explain_changed_symbol(
        ChangedSymbolInfo(
            path="src/focus/hud/explain.py",
            name="ExplainContext",
            kind="class",
            line=31,
        ),
        graph=graph,
        seeds=["src/focus/hud/explain.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path=facts,
    )
    assert "constructed in" in multi
    assert "also referenced in tests" in multi


def test_explain_camel_case_extension_symbols():
    text = explain_changed_symbol(
        ChangedSymbolInfo(
            path="extensions/vscode-focus/src/codeLens.ts",
            name="symbolLenses",
            kind="function",
            line=57,
        ),
        graph=nx.DiGraph(),
        seeds=[],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
    )
    assert "CodeLens" in text
    assert "You changed" not in text


def test_split_explanation_wraps_long_lines():
    text = " ".join(["word"] * 40)
    lines = split_explanation_for_inline(text, max_len=50)
    assert len(lines) > 1
    assert all(len(line) <= 50 for line in lines[:-1])


def test_explain_test_symbol_skips_blast_radius():
    text = explain_changed_symbol(
        ChangedSymbolInfo(
            path="tests/test_explain_cli.py",
            name="test_explain_cli_json",
            kind="function",
            line=95,
        ),
        graph=nx.DiGraph(),
        seeds=["tests/test_explain_cli.py"],
        danger_paths=set(),
        downstream_count=25,
        risk="CRITICAL",
        facts_by_path={},
    )
    assert "Test-only" in text
    assert "25 downstream" not in text
    assert "CRITICAL" not in text


def test_private_enrich_prefix_beats_underscore_fallback():
    text = explain_changed_symbol(
        ChangedSymbolInfo(
            path="src/focus/audit.py",
            name="_enrich_symbols",
            kind="function",
            line=358,
        ),
        graph=nx.DiGraph(),
        seeds=["src/focus/audit.py"],
        danger_paths=set(),
        downstream_count=17,
        risk="CRITICAL",
        facts_by_path={},
    )
    assert "wraps `enrich_changed_symbols`" in text
    assert "on the call path to other modules" not in text


def test_internal_symbol_summary_is_honest_about_module_imports():
    graph = nx.DiGraph()
    graph.add_edge("src/focus/cli.py", "src/focus/audit.py")
    facts = {
        "src/focus/audit.py": ModuleFacts(
            path=Path("src/focus/audit.py"),
            definitions=[Definition(name="_full_audit_hud", kind="function", line=258)],
            calls=[CallSite(callee="_full_audit_hud", line=248)],
        ),
        "src/focus/cli.py": ModuleFacts(
            path=Path("src/focus/cli.py"),
            imports=[Import(module="focus.audit", symbols=["audit_local"], line=13)],
        ),
    }
    text = explain_changed_symbol(
        ChangedSymbolInfo(
            path="src/focus/audit.py",
            name="_full_audit_hud",
            kind="function",
            line=258,
        ),
        graph=graph,
        seeds=["src/focus/audit.py"],
        danger_paths=set(),
        downstream_count=17,
        risk="CRITICAL",
        facts_by_path=facts,
    )
    assert "only invoked inside this file" in text
    assert "a bug here can break those callers" not in text

    summary_only = explain_symbol_with_evidence(
        ChangedSymbolInfo(
            path="src/focus/audit.py",
            name="_full_audit_hud",
            kind="function",
            line=258,
        ),
        context=ExplainContext(
            symbols=[],
            graph=graph,
            seeds=["src/focus/audit.py"],
            danger_paths=set(),
            downstream_count=17,
            risk="CRITICAL",
            facts_by_path=facts,
        ),
    ).symbol.summary
    assert "imported by" not in summary_only.lower()


def test_explain_omits_self_file_path_from_inline_purpose():
    text = explain_changed_symbol(
        ChangedSymbolInfo(
            path="src/focus/hud/explain_render.py",
            name="_render_why",
            kind="function",
            line=44,
        ),
        graph=nx.DiGraph(),
        seeds=["src/focus/hud/explain_render.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
    )
    assert "explain_render.py" not in text
    assert "renders why" in text.lower()


def test_explain_skips_tautological_docstring_for_name_heuristics():
    facts = ModuleFacts(
        path=Path("src/focus/hud/explain.py"),
        definitions=[
            Definition(
                name="enrich_changed_symbols",
                kind="function",
                line=145,
                docstring="Attach inline explanations to each changed symbol.",
            ),
            Definition(
                name="split_explanation_for_inline",
                kind="function",
                line=126,
                docstring="Break explanation into CodeLens-sized lines.",
            ),
        ],
    )
    enrich = explain_changed_symbol(
        ChangedSymbolInfo(
            path="src/focus/hud/explain.py",
            name="enrich_changed_symbols",
            kind="function",
            line=145,
        ),
        graph=nx.DiGraph(),
        seeds=["src/focus/hud/explain.py"],
        danger_paths=set(),
        downstream_count=18,
        risk="CRITICAL",
        facts_by_path={"src/focus/hud/explain.py": facts},
    )
    assert "Attach inline explanations" not in enrich
    assert "audit hook" in enrich
    assert "18 downstream" in enrich

    split = explain_changed_symbol(
        ChangedSymbolInfo(
            path="src/focus/hud/explain.py",
            name="split_explanation_for_inline",
            kind="function",
            line=126,
        ),
        graph=nx.DiGraph(),
        seeds=["src/focus/hud/explain.py"],
        danger_paths=set(),
        downstream_count=18,
        risk="CRITICAL",
        facts_by_path={"src/focus/hud/explain.py": facts},
    )
    assert "CodeLens-sized lines" not in split
    assert "word-wraps" in split


def test_enrich_sets_summary_and_explanation_separately():
    sym = ChangedSymbolInfo(
        path="src/focus/hud/explain.py",
        name="enrich_changed_symbols",
        kind="function",
        line=145,
        changed_lines=[180, 181],
    )
    enriched = enrich_changed_symbols(
        [sym],
        graph=nx.DiGraph(),
        seeds=["src/focus/hud/explain.py"],
        danger_paths=set(),
        downstream_count=18,
        risk="CRITICAL",
        facts_by_path={
            "src/focus/hud/explain.py": ModuleFacts(
                path=Path("src/focus/hud/explain.py"),
                definitions=[
                    Definition(
                        name="enrich_changed_symbols",
                        kind="function",
                        line=145,
                        docstring="Attach inline explanations to each changed symbol.",
                    ),
                ],
            ),
        },
    )[0]
    assert "CRITICAL" in enriched.implication
    assert "focus audit" in enriched.implication.lower() or "caption" in enriched.implication.lower()
    assert "18 downstream" not in enriched.implication
    assert "Shared hub" not in enriched.implication
    assert enriched.summary == enriched.implication
    # Full explanation keeps blast-radius impact prose; implication is IDE rail only.
    assert "18 downstream" in enriched.explanation
    assert enriched.hunk_details
    assert "audit hook" in enriched.explanation or "Attach inline" in enriched.explanation or "caption" in enriched.detail.lower()
    assert "18 downstream" not in enriched.detail
    assert enriched.changed_lines == [180, 181]
    assert enriched.evidence
    assert any(e.confidence == "proven" for e in enriched.evidence)


def test_enrich_changed_symbols_attaches_explanation():
    symbols = [
        ChangedSymbolInfo(path="cli.py", name="version", kind="function", line=33),
    ]
    facts = {
        "cli.py": ModuleFacts(
            path=Path("cli.py"),
            definitions=[
                Definition(
                    name="version",
                    kind="function",
                    line=33,
                    docstring="Print the installed Focus version.",
                ),
            ],
        ),
    }
    enriched = enrich_changed_symbols(
        symbols,
        graph=nx.DiGraph(),
        seeds=["cli.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path=facts,
    )
    assert enriched[0].explanation
    assert enriched[0].summary == ""
    assert enriched[0].implication == ""
    assert "Print the installed Focus version" in enriched[0].explanation


def test_hunk_details_differ_for_similar_blocks_without_parent_name(tmp_path: Path):
    path = tmp_path / "parser.py"
    path.write_text(
        "import ast\n"
        "\n"
        "def _extract_definitions(tree):\n"
        "    definitions = []\n"
        "    for node in ast.walk(tree):\n"
        "        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):\n"
        "            definitions.append(\n"
        "                Definition(name=node.name, kind='function', line=node.lineno)\n"
        "            )\n"
        "        elif isinstance(node, ast.ClassDef):\n"
        "            definitions.append(\n"
        "                Definition(name=node.name, kind='class', line=node.lineno)\n"
        "            )\n"
        "    return definitions\n"
    )
    facts = parse_module(path)
    sym = ChangedSymbolInfo(
        path="parser.py",
        name="_extract_definitions",
        kind="function",
        line=3,
        changed_lines=[7, 8, 9, 12, 13, 14],
    )
    enriched = enrich_changed_symbols(
        [sym],
        graph=nx.DiGraph(),
        seeds=["parser.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={"parser.py": facts},
    )[0]

    assert len(enriched.hunk_details) == 2
    fn_detail = enriched.hunk_details[0].detail
    class_detail = enriched.hunk_details[1].detail
    assert fn_detail != class_detail
    assert "_extract_definitions" not in fn_detail
    assert "_extract_definitions" not in class_detail
    assert "function" in fn_detail.lower()
    assert "class" in class_detail.lower()
    assert "AST (Abstract Syntax Tree)" in fn_detail
    assert "AST (Abstract Syntax Tree)" in class_detail
    assert "record being built" not in fn_detail.lower()
    assert "record being built" not in class_detail.lower()


def test_hunk_details_prefer_proven_call_site_over_enclosing_name(tmp_path: Path):
    """Phase 4b hybrid: CallSite on the hunk line beats parent-function purpose text."""
    path = tmp_path / "audit.py"
    path.write_text(
        "def run_audit():\n"
        "    seeds = []\n"
        "    return enrich_changed_symbols(seeds)\n"
    )
    facts = parse_module(path)
    # Parser should have recorded enrich_changed_symbols on line 3.
    assert any(c.callee.endswith("enrich_changed_symbols") for c in facts.calls)

    sym = ChangedSymbolInfo(
        path="audit.py",
        name="run_audit",
        kind="function",
        line=1,
        changed_lines=[3],
    )
    enriched = enrich_changed_symbols(
        [sym],
        graph=nx.DiGraph(),
        seeds=["audit.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={"audit.py": facts},
    )[0]

    assert len(enriched.hunk_details) == 1
    detail = enriched.hunk_details[0].detail
    assert "enrich_changed_symbols" in detail
    assert "run_audit" not in detail


def test_structural_cues_ignore_kind_mentions_in_docstrings(tmp_path: Path):
    """Prose in a docstring must not fake a class/function recording edit."""
    path = tmp_path / "notes.py"
    path.write_text(
        "def annotate():\n"
        '    """Docs mention kind=\\"class\\" and ClassDef for juniors."""\n'
        "    return True\n"
    )
    facts = parse_module(path)
    sym = ChangedSymbolInfo(
        path="notes.py",
        name="annotate",
        kind="function",
        line=1,
        changed_lines=[2],
    )
    enriched = enrich_changed_symbols(
        [sym],
        graph=nx.DiGraph(),
        seeds=["notes.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={"notes.py": facts},
    )[0]

    detail = enriched.hunk_details[0].detail.lower()
    assert "records this as a class" not in detail
    assert "records this as a function" not in detail


def test_proven_detail_prefers_project_call_over_plumbing(tmp_path: Path):
    """rsplit/split plumbing must not beat the real callee on the same hunk."""
    path = tmp_path / "wire.py"
    path.write_text(
        "def wire_up(path):\n"
        "    bare = path.rsplit('.', 1)[-1]\n"
        "    return enrich_changed_symbols(bare)\n"
    )
    facts = parse_module(path)
    assert any(c.callee.endswith("rsplit") for c in facts.calls)
    assert any(c.callee.endswith("enrich_changed_symbols") for c in facts.calls)

    sym = ChangedSymbolInfo(
        path="wire.py",
        name="wire_up",
        kind="function",
        line=1,
        changed_lines=[2, 3],
    )
    enriched = enrich_changed_symbols(
        [sym],
        graph=nx.DiGraph(),
        seeds=["wire.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={"wire.py": facts},
    )[0]

    detail = enriched.hunk_details[0].detail
    assert "enrich_changed_symbols" in detail
    assert "rsplit" not in detail


def test_implication_quiet_when_low():
    enriched = enrich_changed_symbols(
        [
            ChangedSymbolInfo(
                path="cli.py",
                name="version",
                kind="function",
                line=1,
                changed_lines=[2],
            )
        ],
        graph=nx.DiGraph(),
        seeds=["cli.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={},
    )[0]
    assert enriched.implication == ""
    assert enriched.summary == ""


def test_implication_uses_who_what_formula_not_file_counts():
    enriched = enrich_changed_symbols(
        [
            ChangedSymbolInfo(
                path="auth_utils.py",
                name="validate_token",
                kind="function",
                line=1,
                changed_lines=[2],
            )
        ],
        graph=nx.DiGraph(),
        seeds=["auth_utils.py"],
        danger_paths=set(),
        downstream_count=6,
        risk="CRITICAL",
        facts_by_path={},
    )[0]
    assert enriched.implication.startswith("🔴 CRITICAL —")
    assert " — " in enriched.implication[len("🔴 CRITICAL — ") :]
    assert "downstream files" not in enriched.implication.lower()
    assert "blast radius" not in enriched.implication.lower()
    assert "validate_token" not in enriched.implication


def test_collapse_identical_hunk_purpose_to_one(tmp_path: Path):
    """Same purpose on two hunks → one ℹ️ (item 3)."""
    path = tmp_path / "same.py"
    path.write_text(
        "def twin():\n"
        "    enrich_changed_symbols(a)\n"
        "    x = 1\n"
        "    enrich_changed_symbols(b)\n"
    )
    facts = parse_module(path)
    sym = ChangedSymbolInfo(
        path="same.py",
        name="twin",
        kind="function",
        line=1,
        changed_lines=[2, 4],
    )
    enriched = enrich_changed_symbols(
        [sym],
        graph=nx.DiGraph(),
        seeds=["same.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={"same.py": facts},
    )[0]
    assert len(enriched.hunk_details) == 1
    assert "enrich_changed_symbols" in enriched.hunk_details[0].detail


def test_multi_hunk_collapses_to_symbol_outcome_when_purpose_strong(tmp_path: Path):
    """Mixed call + docstring fallback hunks → one outcome ℹ️, not five."""
    path = tmp_path / "wire.py"
    path.write_text(
        "def explain_symbol_with_evidence(symbol):\n"
        '    """Attach implication, purpose, and evidence for the IDE."""\n'
        "    implication = _implication_for_symbol(symbol)\n"
        "    text = 'x'\n"
        "    evidence = _dedupe_evidence([])\n"
        "    return SymbolExplanation(\n"
        "        symbol=symbol.model_copy(update={'implication': implication, 'evidence': evidence}),\n"
        "        text=text,\n"
        "    )\n"
    )
    facts = parse_module(path)
    sym = ChangedSymbolInfo(
        path="wire.py",
        name="explain_symbol_with_evidence",
        kind="function",
        line=1,
        changed_lines=[3, 5, 7],
    )
    enriched = enrich_changed_symbols(
        [sym],
        graph=nx.DiGraph(),
        seeds=["wire.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path={"wire.py": facts},
    )[0]
    assert len(enriched.hunk_details) == 1
    detail = enriched.hunk_details[0].detail
    assert "implication" in detail.lower() or "evidence" in detail.lower()
    assert "names the function" not in detail.lower()
    # Must not spam the docstring on every edit block.
    assert detail.lower().count("attach implication") <= 1


def test_private_helper_skips_shared_hub_implication():
    """Private symbols without a named victim stay quiet — no Shared hub spam."""
    enriched = enrich_changed_symbols(
        [
            ChangedSymbolInfo(
                path="src/focus/hud/explain.py",
                name="_pad_label",
                kind="function",
                line=10,
                changed_lines=[11],
            )
        ],
        graph=nx.DiGraph([("src/focus/hud/explain.py", "src/focus/cli.py")]),
        seeds=["src/focus/hud/explain.py"],
        danger_paths={"src/focus/hud/explain.py"},
        downstream_count=8,
        risk="CRITICAL",
        facts_by_path={},
    )[0]
    assert enriched.implication == ""
    assert "Shared hub" not in enriched.implication


def test_registry_implication_and_purpose_for_build_hunk_details(tmp_path: Path):
    path = tmp_path / "explain.py"
    path.write_text(
        "def _build_hunk_details(symbol):\n"
        '    """Phase 4b: hybrid CallSite → structural cues for hunk_details."""\n'
        "    return []\n"
    )
    facts = parse_module(path)
    enriched = enrich_changed_symbols(
        [
            ChangedSymbolInfo(
                path="explain.py",
                name="_build_hunk_details",
                kind="function",
                line=1,
                changed_lines=[3],
            )
        ],
        graph=nx.DiGraph(),
        seeds=["explain.py"],
        danger_paths={"explain.py"},
        downstream_count=4,
        risk="CRITICAL",
        facts_by_path={"explain.py": facts},
    )[0]
    assert enriched.implication.startswith("🔴 CRITICAL —")
    assert "IDE captions" in enriched.implication or "focus audit" in enriched.implication
    assert "Shared hub" not in enriched.implication
    detail = enriched.hunk_details[0].detail.lower()
    assert "caption" in detail
    assert "phase 4b" not in detail
    assert "callsite" not in detail


def test_same_file_caller_feeds_implication(tmp_path: Path):
    path = tmp_path / "local.py"
    path.write_text(
        "def parent():\n"
        "    return helper()\n"
        "\n"
        "def helper():\n"
        "    return 1\n"
    )
    facts = parse_module(path)
    enriched = enrich_changed_symbols(
        [
            ChangedSymbolInfo(
                path="local.py",
                name="helper",
                kind="function",
                line=4,
                changed_lines=[5],
            )
        ],
        graph=nx.DiGraph(),
        seeds=["local.py"],
        danger_paths=set(),
        downstream_count=2,
        risk="HIGH",
        facts_by_path={"local.py": facts},
    )[0]
    assert "`parent`" in enriched.implication
    assert "Shared hub" not in enriched.implication


def test_expand_acronyms_for_juniors_first_use_only():
    from focus.hud.explain import expand_acronyms_for_juniors

    once = expand_acronyms_for_juniors("Walk the AST then keep the AST.")
    assert once == "Walk the AST (Abstract Syntax Tree) then keep the AST."
    already = expand_acronyms_for_juniors(
        "Uses the AST (Abstract Syntax Tree) for parsing."
    )
    assert already == "Uses the AST (Abstract Syntax Tree) for parsing."
    multi = expand_acronyms_for_juniors("BFS from the HUD seed.")
    assert "BFS (breadth-first search)" in multi
    assert "HUD (heads-up display)" in multi


def test_compact_evidence_for_inline_caps_and_collapses_importers():
    items = [
        EvidenceItem(
            confidence="proven",
            kind="diff_overlap",
            location="a.py:1",
            fact="git diff touches function `foo` on line(s) 10",
        ),
        EvidenceItem(
            confidence="heuristic",
            kind="symbol_registry",
            location="a.py",
            fact='matched built-in symbol rule "foo"',
        ),
        EvidenceItem(
            confidence="proven",
            kind="graph_importer",
            location="graph",
            fact="`b.py` → `a.py` (file imports file)",
        ),
        EvidenceItem(
            confidence="proven",
            kind="graph_importer",
            location="graph",
            fact="`c.py` → `a.py` (file imports file)",
        ),
        EvidenceItem(
            confidence="proven",
            kind="graph_importer",
            location="graph",
            fact="`d.py` → `a.py` (file imports file)",
        ),
    ]
    compact = _compact_evidence_for_inline(items)
    assert len(compact) == 2
    assert compact[0].kind == "diff_overlap"
    assert compact[1].kind == "symbol_registry"
    # Importers collapsed/dropped when trust slots already filled.
    assert not any("→" in e.fact and "file imports file" in e.fact for e in compact)


def test_compact_evidence_summarizes_importers_when_slots_remain():
    items = [
        EvidenceItem(
            confidence="proven",
            kind="diff_overlap",
            location="a.py:1",
            fact="git diff touches function `foo` on line(s) 10",
        ),
        EvidenceItem(
            confidence="proven",
            kind="graph_importer",
            location="graph",
            fact="`b.py` → `a.py` (file imports file)",
        ),
        EvidenceItem(
            confidence="proven",
            kind="graph_importer",
            location="graph",
            fact="`c.py` → `a.py` (file imports file)",
        ),
    ]
    compact = _compact_evidence_for_inline(items)
    assert len(compact) == 2
    assert compact[0].kind == "diff_overlap"
    assert "2 files import this module" in compact[1].fact
    assert "HUD" in compact[1].fact


def test_symbol_evidence_on_enrich_is_inline_compact(tmp_path: Path):
    """HUD/IDE evidence is capped; full trail stays on explain --why clauses."""
    path = "src/focus/hud/explain.py"
    graph = nx.DiGraph()
    graph.add_edge("src/focus/audit.py", path)
    graph.add_edge("src/focus/cli.py", path)
    graph.add_edge("tests/test_explain.py", path)
    graph.add_edge("tests/test_explain_cli.py", path)
    symbol = ChangedSymbolInfo(
        path=path,
        name="_build_hunk_details",
        kind="function",
        line=748,
        changed_lines=[764, 765],
    )
    facts = {
        path: ModuleFacts(
            path=Path(path),
            definitions=[
                Definition(
                    name="_build_hunk_details",
                    kind="function",
                    line=748,
                    docstring="Build info rows for each edit.",
                ),
            ],
        ),
    }
    explained = explain_symbol_with_evidence(
        symbol,
        context=ExplainContext(
            graph=graph,
            seeds=[path],
            danger_paths={path},
            downstream_count=8,
            risk="CRITICAL",
            symbols=[symbol],
            facts_by_path=facts,
        ),
    )
    assert len(explained.symbol.evidence) <= 2
    importer_facts = [e for e in explained.symbol.evidence if e.kind == "graph_importer"]
    assert len(importer_facts) <= 1
    if importer_facts:
        assert "file imports file" not in importer_facts[0].fact or "1 files" in importer_facts[0].fact
    # Full trail still available on clauses for --why.
    clause_facts = [e for c in explained.clauses for e in c.evidence]
    assert len(clause_facts) >= len(explained.symbol.evidence)
