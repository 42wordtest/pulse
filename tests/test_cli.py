"""Tests for the Pulse CLI."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pulse import cli
from pulse.checker import EndpointCheckResult
from pulse.models import EndpointConfig

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
