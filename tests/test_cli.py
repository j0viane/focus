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


def test_scan_is_honest_about_not_being_implemented() -> None:
    result = runner.invoke(app, ["scan"])
    assert result.exit_code == 1
    assert "not implemented" in result.output
