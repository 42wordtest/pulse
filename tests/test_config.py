"""Tests for Pulse configuration loading."""

from pathlib import Path

import pytest

from pulse.config import ConfigError, load_config, load_pulse_config


def test_load_config_returns_endpoint_configs_with_defaults(tmp_path: Path) -> None:
    """A minimal valid check should receive default values."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text(
        """
checks:
  - name: example-site
    url: https://example.com
"""
    )

    endpoints = load_config(config_file)

    assert len(endpoints) == 1
    assert endpoints[0].name == "example-site"
    assert endpoints[0].url == "https://example.com"
    assert endpoints[0].expected_status == 200
    assert endpoints[0].timeout_seconds == 5.0


def test_load_config_uses_custom_values(tmp_path: Path) -> None:
    """Explicit configuration values should override defaults."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text(
        """
checks:
  - name: payments-api
    url: https://payments.example.com/health
    expected_status: 204
    timeout_seconds: 2.5
"""
    )

    endpoints = load_config(config_file)

    assert len(endpoints) == 1
    assert endpoints[0].expected_status == 204
    assert endpoints[0].timeout_seconds == 2.5


def test_load_pulse_config_loads_availability_alert_rules(tmp_path: Path) -> None:
    """Alert rules should reference configured endpoints and notification targets."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text(
        """
checks:
  - name: payments-api
    url: https://payments.example.com/health
alerts:
  - name: payments-availability
    endpoint: payments-api
    type: availability_below
    window_hours: 2
    min_samples: 20
    threshold_percent: 99.5
    notifications:
      - type: console
      - type: webhook
        url_env: PULSE_ALERT_WEBHOOK_URL
"""
    )

    config = load_pulse_config(config_file)

    assert len(config.alert_rules) == 1
    rule = config.alert_rules[0]
    assert rule.name == "payments-availability"
    assert rule.endpoint_name == "payments-api"
    assert rule.window_hours == 2
    assert rule.min_samples == 20
    assert rule.threshold_percent == 99.5
    assert [notification.type for notification in rule.notifications] == [
        "console",
        "webhook",
    ]
    assert rule.notifications[1].url_env == "PULSE_ALERT_WEBHOOK_URL"


def test_load_pulse_config_rejects_alerts_for_unknown_endpoints(tmp_path: Path) -> None:
    """Alert rules must point at checks declared in the same file."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text(
        """
checks:
  - name: payments-api
    url: https://payments.example.com/health
alerts:
  - name: unknown-endpoint-alert
    endpoint: missing-api
    threshold_percent: 99
"""
    )

    with pytest.raises(ConfigError, match="must reference a configured endpoint"):
        load_pulse_config(config_file)


def test_load_pulse_config_rejects_webhooks_without_environment_variables(
    tmp_path: Path,
) -> None:
    """Webhook URLs must be supplied through an environment variable name."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text(
        """
checks:
  - name: payments-api
    url: https://payments.example.com/health
alerts:
  - name: payments-availability
    endpoint: payments-api
    threshold_percent: 99
    notifications:
      - type: webhook
"""
    )

    with pytest.raises(ConfigError, match="must have 'url_env'"):
        load_pulse_config(config_file)


def test_load_config_raises_error_when_file_does_not_exist(tmp_path: Path) -> None:
    """A missing configuration file should produce a useful error."""
    missing_file = tmp_path / "missing.yaml"

    with pytest.raises(ConfigError, match="Configuration file not found"):
        load_config(missing_file)


def test_load_config_raises_error_when_checks_is_missing(tmp_path: Path) -> None:
    """The configuration must define a checks list."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text("version: 1\n")

    with pytest.raises(ConfigError, match="must contain a 'checks' list"):
        load_config(config_file)


def test_load_config_raises_error_for_invalid_url(tmp_path: Path) -> None:
    """Each endpoint URL must be HTTP or HTTPS."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text(
        """
checks:
  - name: invalid-api
    url: not-a-url
"""
    )

    with pytest.raises(ConfigError, match="valid HTTP or HTTPS"):
        load_config(config_file)


def test_load_config_raises_error_for_duplicate_names(tmp_path: Path) -> None:
    """Endpoint names must be unique."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text(
        """
checks:
  - name: api
    url: https://one.example.com
  - name: api
    url: https://two.example.com
"""
    )

    with pytest.raises(ConfigError, match="Duplicate names: api"):
        load_config(config_file)


def test_load_config_raises_error_for_invalid_status_code(tmp_path: Path) -> None:
    """Expected HTTP statuses must be valid HTTP status codes."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text(
        """
checks:
  - name: api
    url: https://api.example.com
    expected_status: 700
"""
    )

    with pytest.raises(ConfigError, match="between 100 and 599"):
        load_config(config_file)


def test_load_config_raises_error_for_non_positive_timeout(tmp_path: Path) -> None:
    """Timeouts must be greater than zero."""
    config_file = tmp_path / "pulse.yaml"
    config_file.write_text(
        """
checks:
  - name: api
    url: https://api.example.com
    timeout_seconds: 0
"""
    )

    with pytest.raises(ConfigError, match="greater than zero"):
        load_config(config_file)
