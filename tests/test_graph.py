"""Graph construction is verified against glass_box, where every edge
is known by reading the fixture files, plus synthetic facts for import
shapes the fixture doesn't contain."""

from pathlib import Path

from focus.graph import build_graph, downstream_rings
from focus.scan import discover_python_files, parse_module, parse_source


def _glass_box_graph(glass_box_path: Path):
    facts = [parse_module(f) for f in discover_python_files(glass_box_path)]
    return build_graph(facts, glass_box_path)


def test_glass_box_edges_are_exact(glass_box_path: Path):
    graph = _glass_box_graph(glass_box_path)
    assert set(graph.edges()) == {
        ("billing/service.py", "auth_utils.py"),
        ("dashboard/views.py", "auth_utils.py"),
        ("jobs/worker.py", "auth_utils.py"),
        ("api/routes.py", "billing/service.py"),
    }
    assert set(graph.nodes()) == {
        "api/routes.py",
        "auth_utils.py",
        "billing/service.py",
        "dashboard/views.py",
        "jobs/worker.py",
    }


def test_blast_radius_rings_for_auth_utils(glass_box_path: Path):
    graph = _glass_box_graph(glass_box_path)
    assert downstream_rings(graph, "auth_utils.py") == [
        (1, ["billing/service.py", "dashboard/views.py", "jobs/worker.py"]),
        (2, ["api/routes.py"]),
    ]


def test_leaf_file_has_empty_blast_radius(glass_box_path: Path):
    graph = _glass_box_graph(glass_box_path)
    assert downstream_rings(graph, "api/routes.py") == []


def test_external_imports_create_no_edges():
    facts = [parse_source(b"import os\nfrom pathlib import Path\n", Path("solo.py"))]
    graph = build_graph(facts, Path("."))
    assert list(graph.nodes()) == ["solo.py"]
    assert list(graph.edges()) == []


def test_relative_import_resolves_within_package():
    facts = [
        parse_source(b"from . import helper\n", Path("pkg/mod.py")),
        parse_source(b"", Path("pkg/helper.py")),
    ]
    graph = build_graph(facts, Path("."))
    assert set(graph.edges()) == {("pkg/mod.py", "pkg/helper.py")}


def test_relative_import_climbing_to_parent_package():
    facts = [
        parse_source(b"from ..shared import util\n", Path("app/sub/mod.py")),
        parse_source(b"", Path("app/shared/util.py")),
    ]
    graph = build_graph(facts, Path("."))
    assert set(graph.edges()) == {("app/sub/mod.py", "app/shared/util.py")}


def test_from_package_import_submodule():
    facts = [
        parse_source(b"from pkg import helper\n", Path("app.py")),
        parse_source(b"", Path("pkg/helper.py")),
    ]
    graph = build_graph(facts, Path("."))
    assert set(graph.edges()) == {("app.py", "pkg/helper.py")}


def test_src_layout_files_answer_without_src_prefix():
    facts = [
        parse_source(b"from focus.models import Import\n", Path("src/focus/cli.py")),
        parse_source(b"", Path("src/focus/models.py")),
    ]
    graph = build_graph(facts, Path("."))
    assert set(graph.edges()) == {("src/focus/cli.py", "src/focus/models.py")}


def test_package_init_answers_to_package_name():
    facts = [
        parse_source(b"import pkg\n", Path("app.py")),
        parse_source(b"", Path("pkg/__init__.py")),
    ]
    graph = build_graph(facts, Path("."))
    assert set(graph.edges()) == {("app.py", "pkg/__init__.py")}
