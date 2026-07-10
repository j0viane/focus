"""Smoke tests: the CLI installs, runs, and reports its version."""

from typer.testing import CliRunner

from focus.cli import app

runner = CliRunner()


def test_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scan" in result.output


def test_version_matches_pyproject() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == "0.0.1"


def test_scan_lists_fixture_files(glass_box_path) -> None:
    result = runner.invoke(app, ["scan", str(glass_box_path)])
    assert result.exit_code == 0
    assert "billing/service.py" in result.output
    assert "4 Python file(s) found" in result.output


def test_scan_rejects_missing_path() -> None:
    result = runner.invoke(app, ["scan", "does/not/exist"])
    assert result.exit_code != 0
