"""Symbol-level blast-radius filtering (proven import/call evidence)."""

from pathlib import Path

from focus.graph import build_graph, downstream_rings
from focus.hud.symbol_filter import filter_rings_by_symbols
from focus.models import ChangedSymbolInfo
from focus.scan import discover_python_files, parse_module


def _glass_box_graph_and_facts(glass_box_path: Path):
    facts = [parse_module(f) for f in discover_python_files(glass_box_path)]
    facts_by_path = {
        f.path.resolve().relative_to(glass_box_path.resolve()).as_posix(): f
        for f in facts
    }
    graph = build_graph(facts, glass_box_path)
    return graph, facts_by_path


def _unfiltered_rings(graph, seed: str) -> list[tuple[int, list[str]]]:
    seed_set = {seed}
    rings = []
    for hops, paths in downstream_rings(graph, seed):
        kept = sorted(p for p in paths if p not in seed_set)
        if kept:
            rings.append((hops, kept))
    return rings


def test_filter_isolated_helper_drops_file_importers(glass_box_path: Path) -> None:
    graph, facts_by_path = _glass_box_graph_and_facts(glass_box_path)
    rings = _unfiltered_rings(graph, "auth_utils.py")
    assert rings == [
        (1, ["billing/service.py", "dashboard/views.py", "jobs/worker.py"]),
        (2, ["api/routes.py"]),
    ]

    symbols = [
        ChangedSymbolInfo(
            path="auth_utils.py",
            name="hash_password",
            kind="function",
            line=11,
            changed_lines=[13],
        )
    ]
    filtered = filter_rings_by_symbols(
        rings, graph, ["auth_utils.py"], symbols, facts_by_path
    )
    assert filtered == []


def test_filter_hub_symbol_keeps_real_callers(glass_box_path: Path) -> None:
    graph, facts_by_path = _glass_box_graph_and_facts(glass_box_path)
    rings = _unfiltered_rings(graph, "auth_utils.py")
    symbols = [
        ChangedSymbolInfo(
            path="auth_utils.py",
            name="validate_token",
            kind="function",
            line=6,
            changed_lines=[8],
        )
    ]
    filtered = filter_rings_by_symbols(
        rings, graph, ["auth_utils.py"], symbols, facts_by_path
    )
    assert filtered == [
        (1, ["billing/service.py", "dashboard/views.py", "jobs/worker.py"]),
        (2, ["api/routes.py"]),
    ]


def test_filter_empty_symbols_is_unfiltered(glass_box_path: Path) -> None:
    graph, facts_by_path = _glass_box_graph_and_facts(glass_box_path)
    rings = _unfiltered_rings(graph, "auth_utils.py")
    filtered = filter_rings_by_symbols(
        rings, graph, ["auth_utils.py"], [], facts_by_path
    )
    assert filtered == rings
