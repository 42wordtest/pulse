"""Tests for the Pulse CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pulse.cli import app

runner = CliRunner()


def test_check_command_lists_configured_endpoint_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check command should show each check from pulse.yaml."""
    monkeypatch.chdir(tmp_path)
    Path("pulse.yaml").write_text(
        """
checks:
  - name: example-site
    url: https://example.com
  - name: payments-api
    url: https://payments.example.com/health
    expected_status: 204
    timeout_seconds: 2.5
"""
    )

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert "Found 2 endpoint checks:" in result.output
    assert (
        "example-site: https://example.com (expects 200; timeout 5s)"
        in result.output
    )
    assert (
        "payments-api: https://payments.example.com/health "
        "(expects 204; timeout 2.5s)"
    ) in result.output


def test_check_command_reports_a_missing_configuration_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check command should report a missing pulse.yaml without a traceback."""
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1
    assert (
        "Configuration error: Configuration file not found: pulse.yaml"
        in result.output
    )
    assert "Traceback" not in result.output


def test_check_command_reports_invalid_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The check command should report invalid configuration without a traceback."""
    monkeypatch.chdir(tmp_path)
    Path("pulse.yaml").write_text("checks: not-a-list\n")

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 1
    assert (
        "Configuration error: Configuration must contain a 'checks' list."
        in result.output
    )
    assert "Traceback" not in result.output
