"""Tests for Pulse configuration loading."""

from pathlib import Path

import pytest

from pulse.config import ConfigError, load_config


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
