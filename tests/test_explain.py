"""Deterministic inline explanations for changed symbols."""

from pathlib import Path

import networkx as nx

from focus.hud.explain import (
    ExplainContext,
    enrich_changed_symbols,
    explain_changed_symbol,
    explain_symbol_with_evidence,
    split_explanation_for_inline,
)
from focus.models import CallSite, ChangedSymbolInfo, Definition, Import, ModuleFacts
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
    assert "18 downstream" in enriched.summary
    assert enriched.summary in enriched.explanation
    assert enriched.hunk_details
    assert "audit hook" in enriched.explanation
    assert "18 downstream" not in enriched.detail
    assert enriched.changed_lines == [180, 181]


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
