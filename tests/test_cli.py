"""Smoke tests: the CLI installs, runs, and reports its version."""

from typer.testing import CliRunner

from focus.cli import app

runner = CliRunner()


def test_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "explain" in result.output
    assert "scan" in result.output


def test_version_matches_pyproject() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == "0.2.0"


def test_scan_indexes_fixture_files(glass_box_path) -> None:
    result = runner.invoke(app, ["scan", str(glass_box_path)])
    assert result.exit_code == 0
    assert "billing/service.py — 1 imports · 1 defs · 2 calls" in result.output
    assert "jobs/worker.py — 1 imports · 1 defs · 1 calls" in result.output
    assert "5 source file(s) indexed" in result.output


def test_scan_rejects_missing_path() -> None:
    result = runner.invoke(app, ["scan", "does/not/exist"])
    assert result.exit_code != 0


def test_trace_reports_rings(glass_box_path) -> None:
    result = runner.invoke(
        app,
        ["trace", str(glass_box_path / "auth_utils.py"), "--root", str(glass_box_path)],
    )
    assert result.exit_code == 0
    assert "## Focus" in result.output
    assert "```mermaid" in result.output
    assert "billing/service.py" in result.output
    assert "dashboard/views.py" in result.output
    assert "api/routes.py" in result.output
    assert "Danger Zones" in result.output
    assert "Caveat" in result.output


def test_trace_json_format(glass_box_path) -> None:
    import json

    result = runner.invoke(
        app,
        [
            "trace",
            str(glass_box_path / "auth_utils.py"),
            "--root",
            str(glass_box_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["seed"] == "auth_utils.py"
    assert payload["risk_tier"] == "CRITICAL"
    assert isinstance(payload["downstream"], list)
    assert isinstance(payload["danger_zones"], list)
    assert payload["mermaid"]


def test_trace_isolated_file(glass_box_path) -> None:
    result = runner.invoke(
        app,
        ["trace", str(glass_box_path / "api" / "routes.py"), "--root", str(glass_box_path)],
    )
    assert result.exit_code == 0
    assert "LOW" in result.output
    assert "touches nothing downstream" in result.output
    assert "```mermaid" not in result.output


def test_trace_file_outside_root_fails(glass_box_path, tmp_path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("")
    result = runner.invoke(app, ["trace", str(outside), "--root", str(glass_box_path)])
    assert result.exit_code == 1
