"""CLI tests for `focus explain`."""

import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from focus.cli import app
from focus.hud.explain import ExplainContext, explain_symbol_with_evidence
from focus.models import ChangedSymbolInfo

import networkx as nx

runner = CliRunner()


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _glass_box_repo(tmp_path: Path, glass_box_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(glass_box_path, repo)
    _git(repo, "init")
    _git(repo, "config", "user.email", "focus@test")
    _git(repo, "config", "user.name", "Focus Test")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init glass_box")
    _git(repo, "branch", "-M", "main")
    return repo


def test_explain_symbol_with_evidence_includes_proven_docstring():
    from focus.models import Definition, ModuleFacts

    facts = {
        "auth_utils.py": ModuleFacts(
            path=Path("auth_utils.py"),
            definitions=[
                Definition(
                    name="validate_token",
                    kind="function",
                    line=6,
                    docstring="Return True when the token matches the fixture secret.",
                ),
            ],
        ),
    }
    context = ExplainContext(
        symbols=[ChangedSymbolInfo(path="auth_utils.py", name="validate_token", kind="function", line=6)],
        graph=nx.DiGraph(),
        seeds=["auth_utils.py"],
        danger_paths=set(),
        downstream_count=0,
        risk="LOW",
        facts_by_path=facts,
    )
    sym = context.symbols[0]
    result = explain_symbol_with_evidence(sym, context=context)
    kinds = {item.kind for clause in result.clauses for item in clause.evidence}
    assert "docstring" in kinds
    assert "diff_overlap" in kinds
    assert any(item.confidence == "proven" for clause in result.clauses for item in clause.evidence)


def test_explain_cli_local_with_why(tmp_path: Path, glass_box_path: Path):
    repo = _glass_box_repo(tmp_path, glass_box_path)
    auth = repo / "auth_utils.py"
    auth.write_text(
        auth.read_text().replace(
            "return token == FIXTURE_SECRET",
            "return token == FIXTURE_SECRET  # audited",
        )
    )

    result = runner.invoke(
        app,
        [
            "explain",
            "--local",
            "--path",
            str(repo),
            "--symbol",
            "validate_token",
            "--why",
        ],
    )
    assert result.exit_code == 0
    assert "validate_token" in result.output
    assert "Why this text" in result.output
    assert "proven" in result.output.lower()


def test_explain_cli_json(tmp_path: Path, glass_box_path: Path):
    repo = _glass_box_repo(tmp_path, glass_box_path)
    auth = repo / "auth_utils.py"
    auth.write_text(
        auth.read_text().replace(
            "return token == FIXTURE_SECRET",
            "return token == FIXTURE_SECRET  # audited",
        )
    )

    result = runner.invoke(
        app,
        [
            "explain",
            "--local",
            "--path",
            str(repo),
            "--symbol",
            "validate_token",
            "--format",
            "json",
            "--why",
        ],
    )
    assert result.exit_code == 0
    assert '"clauses"' in result.output
    assert '"evidence"' in result.output
