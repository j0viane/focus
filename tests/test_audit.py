"""Audit --local: diff seeds → HUD, with smart-trigger pass-through."""

import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from focus.audit import audit_local
from focus.cli import app
from focus.triggers import (
    TINY_DIFF_MAX_LINES,
    count_changed_lines,
    should_emit_diagram,
)

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


def test_audit_local_helper_change_filters_importers(tmp_path: Path, glass_box_path: Path):
    """Changing an unused helper must not file-level blast-radius every importer."""
    repo = _glass_box_repo(tmp_path, glass_box_path)
    auth = repo / "auth_utils.py"
    auth.write_text(
        auth.read_text().replace(
            "return password[::-1]",
            "return password[::-1]  # audited",
        )
    )

    hud = audit_local(repo, base="main")
    downstream_paths = {n.path for n in hud.downstream}
    danger_downstream = {n.path for n in hud.danger_zones if n.hops > 0}
    assert "billing/service.py" not in downstream_paths
    assert "dashboard/views.py" not in downstream_paths
    assert "jobs/worker.py" not in downstream_paths
    assert "api/routes.py" not in danger_downstream
    assert any(s.name == "hash_password" for s in hud.changed_symbols)


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
    assert any(
        "shared hub" in n.reason.lower() and "imported directly by" in n.reason.lower()
        for n in hud.danger_zones
        if n.path == "auth_utils.py"
    )
    assert any(s.name == "validate_token" for s in hud.changed_symbols)
    token = next(s for s in hud.changed_symbols if s.name == "validate_token")
    assert token.explanation
    assert "validate_token" in token.explanation
    assert "You changed" not in token.explanation
    assert "calls `validate_token`" in token.explanation or "called from" in token.explanation.lower()


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


def test_audit_local_tiny_diff_one_downstream_is_pass_through(
    tmp_path: Path, glass_box_path: Path
):
    """ROA: ≤5 lines + <2 downstream files + no Danger Zone → no Mermaid."""
    repo = _glass_box_repo(tmp_path, glass_box_path)
    billing = repo / "billing" / "service.py"
    billing.write_text(
        billing.read_text().replace(
            'return {"user_id": user_id, "charged_cents": amount_cents, "status": "ok"}',
            'return {"user_id": user_id, "charged_cents": amount_cents, "status": "ok"}  # x',
        )
    )

    hud = audit_local(repo, base="main")
    assert hud.mode == "pass_through"
    assert hud.risk_tier == "LOW"
    assert hud.mermaid is None
    assert "tiny" in hud.summary.lower() or "low blast" in hud.summary.lower()


def test_audit_local_large_diff_one_downstream_is_full(tmp_path: Path, glass_box_path: Path):
    """Same single importer, but enough changed lines → full HUD."""
    repo = _glass_box_repo(tmp_path, glass_box_path)
    billing = repo / "billing" / "service.py"
    # Pad with many executable lines so the diff exceeds TINY_DIFF_MAX_LINES.
    padding = "\n".join(f"    _pad_{i} = {i}" for i in range(TINY_DIFF_MAX_LINES + 3))
    billing.write_text(
        billing.read_text().replace(
            "    return {\"user_id\": user_id, \"charged_cents\": amount_cents, \"status\": \"ok\"}",
            f"{padding}\n    return {{\n"
            f'        "user_id": user_id,\n'
            f'        "charged_cents": amount_cents,\n'
            f'        "status": "ok",\n'
            f"    }}",
        )
    )

    hud = audit_local(repo, base="main")
    assert hud.mode == "full"
    assert hud.mermaid is not None


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


def test_audit_without_local_uses_branch_range(tmp_path: Path, glass_box_path: Path):
    """Without --local, audit diffs base...HEAD (committed PR range)."""
    repo = _glass_box_repo(tmp_path, glass_box_path)
    auth = repo / "auth_utils.py"
    auth.write_text(
        auth.read_text().replace(
            "return token == FIXTURE_SECRET",
            "return token == FIXTURE_SECRET  # audited",
        )
    )
    _git(repo, "add", "auth_utils.py")
    _git(repo, "commit", "-m", "change auth")
    # Ensure we are on a branch ahead of main for range mode.
    # _glass_box_repo already committed on main; create a feature tip.
    # If the change was made on main, range vs main is empty — move commit to a branch.
    _git(repo, "branch", "feature-auth")
    _git(repo, "reset", "--hard", "HEAD~1")
    _git(repo, "checkout", "feature-auth")

    result = runner.invoke(app, ["audit", "--path", str(repo), "--base", "main"])
    assert result.exit_code == 0
    assert "Focus" in result.output or "risk" in result.output.lower()


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
    # Tiny + one downstream file → pass-through (ROA).
    assert (
        should_emit_diagram(
            changed_paths=["billing/service.py"],
            python_seeds=["billing/service.py"],
            has_downstream=True,
            downstream_file_count=1,
            changed_line_count=2,
        )
        is False
    )
    # Same coupling, not tiny → diagram.
    assert (
        should_emit_diagram(
            changed_paths=["billing/service.py"],
            python_seeds=["billing/service.py"],
            has_downstream=True,
            downstream_file_count=1,
            changed_line_count=TINY_DIFF_MAX_LINES + 1,
        )
        is True
    )
    # Path Danger Zone still diagrams even when tiny.
    assert (
        should_emit_diagram(
            changed_paths=["api/routes.py"],
            python_seeds=["api/routes.py"],
            has_downstream=False,
            downstream_file_count=0,
            changed_line_count=1,
        )
        is True
    )


def test_count_changed_lines():
    assert count_changed_lines({}) == 0
    assert count_changed_lines({"a.py": [(10, 10)]}) == 1
    assert count_changed_lines({"a.py": [(10, 12)], "b.py": [(1, 2)]}) == 5
