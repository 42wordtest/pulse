"""Tests for the Pulse CLI."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pulse import cli
from pulse.checker import EndpointCheckResult
from pulse.models import EndpointConfig
from pulse.storage import initialise_database, insert_check_result

runner = CliRunner()


def test_check_command_prints_a_healthy_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("pulse.yaml").write_text(
        """
checks:
  - name: example
    url: https://example.com
"""
    )

    async def fake_check_endpoints(
        endpoints: list[EndpointConfig],
    ) -> list[EndpointCheckResult]:
        endpoint = endpoints[0]
        return [
            EndpointCheckResult(
                endpoint=endpoint,
                healthy=True,
                latency_seconds=0.123,
                status_code=200,
                message="Healthy: received expected HTTP 200.",
            )
        ]

    monkeypatch.setattr(cli, "check_endpoints", fake_check_endpoints)

    result = runner.invoke(cli.app, ["check"])

    assert result.exit_code == 0
    assert "HEALTHY example" in result.output
    assert "123 ms" in result.output
    assert "Healthy: received expected HTTP 200." in result.output


def test_alerts_command_notifies_once_for_an_active_availability_alert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The command should suppress duplicate notifications for the same alert."""
    monkeypatch.chdir(tmp_path)
    Path("pulse.yaml").write_text(
        """
checks:
  - name: api
    url: https://api.example.com/health
alerts:
  - name: api-availability
    endpoint: api
    threshold_percent: 99
    min_samples: 3
"""
    )
    endpoint = EndpointConfig("api", "https://api.example.com/health")
    now = datetime.now(UTC)
    database_path = Path(".pulse/pulse.db")

    initialise_database(database_path)
    with sqlite3.connect(database_path) as connection:
        for offset, healthy in enumerate((True, True, False), start=1):
            insert_check_result(
                connection,
                EndpointCheckResult(
                    endpoint=endpoint,
                    healthy=healthy,
                    latency_seconds=0.1,
                    status_code=200 if healthy else 503,
                    message="result",
                ),
                checked_at=now - timedelta(minutes=offset),
            )

    first_result = runner.invoke(cli.app, ["alerts"])
    second_result = runner.invoke(cli.app, ["alerts"])

    assert first_result.exit_code == 1
    assert "NOTIFIED console: ALERT api-availability (api):" in first_result.output
    assert second_result.exit_code == 1
    assert "ALERT ACTIVE api-availability:" in second_result.output
    assert "NOTIFIED console" not in second_result.output
