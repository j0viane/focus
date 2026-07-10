"""Config and symbol-diff polish tests."""

import shutil
import subprocess
from pathlib import Path

from focus.config import load_config
from focus.graph import build_graph
from focus.hud.classify import is_danger_zone
from focus.ingest.symbols import changed_symbols
from focus.scan import discover_python_files, parse_module


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_load_config_defaults(tmp_path: Path):
    assert load_config(tmp_path).fan_out_threshold == 3


def test_load_config_override(tmp_path: Path):
    (tmp_path / ".focus.toml").write_text("[focus]\nfan_out_threshold = 5\n")
    assert load_config(tmp_path).fan_out_threshold == 5


def test_fan_out_threshold_from_config(glass_box_path: Path, tmp_path: Path):
    facts = [parse_module(f) for f in discover_python_files(glass_box_path)]
    graph = build_graph(facts, glass_box_path)
    # auth_utils has 3 importers after jobs/worker.py — danger at 3, not at 4.
    assert is_danger_zone("auth_utils.py", graph, fan_out_threshold=3) is True
    assert is_danger_zone("auth_utils.py", graph, fan_out_threshold=4) is False


def test_package_init_skipped_for_fan_out_only():
    import networkx as nx

    graph = nx.DiGraph()
    graph.add_edges_from(
        [
            ("a.py", "pkg/__init__.py"),
            ("b.py", "pkg/__init__.py"),
            ("c.py", "pkg/__init__.py"),
            ("d.py", "pkg/__init__.py"),
        ]
    )
    assert is_danger_zone("pkg/__init__.py", graph, fan_out_threshold=3) is False


def test_changed_symbols_detects_def(tmp_path: Path, glass_box_path: Path):
    repo = tmp_path / "repo"
    shutil.copytree(glass_box_path, repo)
    _git(repo, "init")
    _git(repo, "config", "user.email", "focus@test")
    _git(repo, "config", "user.name", "Focus Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    _git(repo, "branch", "-M", "main")

    auth = repo / "auth_utils.py"
    auth.write_text(
        auth.read_text().replace(
            "return token == FIXTURE_SECRET",
            "return token == FIXTURE_SECRET  # change",
        )
    )
    symbols = changed_symbols(repo, "main")
    assert any(s.name == "validate_token" and s.path == "auth_utils.py" for s in symbols)
