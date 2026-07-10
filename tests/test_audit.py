"""Audit --local: diff seeds → HUD, with smart-trigger pass-through."""

import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from focus.audit import audit_local
from focus.cli import app
from focus.triggers import should_emit_diagram

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


def test_audit_local_auth_change_is_critical(tmp_path: Path, glass_box_path: Path):
    repo = _glass_box_repo(tmp_path, glass_box_path)
    auth = repo / "auth_utils.py"
    auth.write_text(
        auth.read_text().replace(
            "return token == FIXTURE_SECRET",
            "return token == FIXTURE_SECRET  # audited",
        )
    )

    hud = audit_local(repo, base="main")
    assert hud.mode == "full"
    assert hud.risk_tier in {"HIGH", "CRITICAL"}
    assert hud.mermaid is not None
    assert any(n.path == "api/routes.py" for n in hud.danger_zones)
    assert any(n.path == "auth_utils.py" for n in hud.danger_zones)
    assert any("fan-out" in n.reason for n in hud.danger_zones if n.path == "auth_utils.py")
    assert any(s.name == "validate_token" for s in hud.changed_symbols)


def test_audit_local_docs_only_is_pass_through(tmp_path: Path, glass_box_path: Path):
    repo = _glass_box_repo(tmp_path, glass_box_path)
    (repo / "NOTES.md").write_text("docs only\n")

    hud = audit_local(repo, base="main")
    assert hud.mode == "pass_through"
    assert hud.risk_tier == "LOW"
    assert hud.mermaid is None


def test_audit_local_comment_only_is_pass_through(tmp_path: Path, glass_box_path: Path):
    repo = _glass_box_repo(tmp_path, glass_box_path)
    auth = repo / "auth_utils.py"
    auth.write_text(auth.read_text() + "\n# comment only\n")

    hud = audit_local(repo, base="main")
    assert hud.mode == "pass_through"
    assert "comments" in hud.summary.lower()


def test_audit_local_isolated_non_danger_is_pass_through(tmp_path: Path, glass_box_path: Path):
    repo = _glass_box_repo(tmp_path, glass_box_path)
    views = repo / "dashboard" / "views.py"
    views.write_text(
        views.read_text().replace('return "Session active"', 'return "Session active!"')
    )

    hud = audit_local(repo, base="main")
    assert hud.mode == "pass_through"
    assert hud.risk_tier == "LOW"
    assert hud.mermaid is None


def test_audit_local_danger_seed_without_downstream_is_full(tmp_path: Path, glass_box_path: Path):
    repo = _glass_box_repo(tmp_path, glass_box_path)
    routes = repo / "api" / "routes.py"
    routes.write_text(
        routes.read_text().replace(
            "return charge_user(user_id, token, amount_cents)",
            "return charge_user(user_id, token, amount_cents)  # x",
        )
    )

    hud = audit_local(repo, base="main")
    assert hud.mode == "full"
    assert any(n.path == "api/routes.py" for n in hud.danger_zones)


def test_audit_cli_local(tmp_path: Path, glass_box_path: Path):
    repo = _glass_box_repo(tmp_path, glass_box_path)
    auth = repo / "auth_utils.py"
    auth.write_text(
        auth.read_text().replace(
            "return token == FIXTURE_SECRET",
            "return token == FIXTURE_SECRET  # audited",
        )
    )
    out = tmp_path / "hud.md"
    result = runner.invoke(
        app,
        ["audit", "--local", "--path", str(repo), "--out", str(out)],
    )
    assert result.exit_code == 0
    assert "## Focus" in result.output
    assert "```mermaid" in result.output
    assert out.is_file()
    assert "```mermaid" in out.read_text()


def test_audit_requires_local_flag():
    result = runner.invoke(app, ["audit"])
    assert result.exit_code == 2
    assert "--local" in result.output


def test_trigger_helper():
    assert (
        should_emit_diagram(
            changed_paths=["README.md"],
            python_seeds=[],
            has_downstream=False,
        )
        is False
    )
    assert (
        should_emit_diagram(
            changed_paths=["auth_utils.py"],
            python_seeds=["auth_utils.py"],
            has_downstream=True,
            downstream_file_count=2,
        )
        is True
    )
    assert (
        should_emit_diagram(
            changed_paths=["tests/test_foo.py"],
            python_seeds=["tests/test_foo.py"],
            has_downstream=False,
        )
        is False
    )
    assert (
        should_emit_diagram(
            changed_paths=["api/routes.py"],
            python_seeds=["api/routes.py"],
            has_downstream=False,
        )
        is True
    )
