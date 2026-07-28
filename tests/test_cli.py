"""Tests for the Pulse CLI."""

from typer.testing import CliRunner

from pulse.cli import app

runner = CliRunner()


def test_check_command_exits_successfully() -> None:
    """The check command should run successfully."""
    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert "Pulse is ready." in result.output