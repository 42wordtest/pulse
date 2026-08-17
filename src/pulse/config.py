from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

import yaml

from .models import AlertRule, EndpointConfig, NotificationConfig, PulseConfig


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> list[EndpointConfig]:
    """Load endpoint checks from a Pulse configuration file."""
    return list(load_pulse_config(path).endpoints)


def load_pulse_config(path: Path) -> PulseConfig:
    """Load endpoint checks and alert rules from a Pulse configuration file."""
    try:
        raw_config = yaml.safe_load(path.read_text())
    except FileNotFoundError as error:
        raise ConfigError(f"Configuration file not found: {path}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid YAML in {path}: {error}") from error

    if not isinstance(raw_config, dict):
        raise ConfigError("Configuration must be a YAML mapping.")

    raw_checks = raw_config.get("checks")
    if not isinstance(raw_checks, list):
        raise ConfigError("Configuration must contain a 'checks' list.")

    endpoints = tuple(
        _parse_endpoint(raw_check, position)
        for position, raw_check in enumerate(raw_checks, start=1)
    )

    _ensure_unique_names(endpoints)

    return PulseConfig(
        endpoints=endpoints,
        alert_rules=_parse_alert_rules(raw_config.get("alerts", []), endpoints),
    )


def _parse_endpoint(raw_check: object, position: int) -> EndpointConfig:
    """Convert one YAML check entry into an EndpointConfig."""
    if not isinstance(raw_check, dict):
        raise ConfigError(f"Check {position} must be a mapping.")

    name = raw_check.get("name")
    url = raw_check.get("url")

    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"Check {position} must have a non-empty 'name'.")

    if not isinstance(url, str) or not _is_valid_http_url(url):
        raise ConfigError(f"Check '{name}' must have a valid HTTP or HTTPS 'url'.")

    expected_status = _read_expected_status(
        raw_check.get("expected_status", 200),
        name,
    )
    timeout_seconds = _read_timeout_seconds(
        raw_check.get("timeout_seconds", 5.0),
        name,
    )

    return EndpointConfig(
        name=name,
        url=url,
        expected_status=expected_status,
        timeout_seconds=timeout_seconds,
    )


def _read_expected_status(value: object, check_name: str) -> int:
    """Validate an expected HTTP status code."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            f"Check '{check_name}' has an invalid 'expected_status'. It must be an integer."
        )

    if not 100 <= value <= 599:
        raise ConfigError(
            f"Check '{check_name}' has an invalid 'expected_status'. "
            "It must be between 100 and 599."
        )

    return value


def _read_timeout_seconds(value: object, check_name: str) -> float:
    """Validate an HTTP timeout value."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(
            f"Check '{check_name}' has an invalid 'timeout_seconds'. It must be a number."
        )

    timeout_seconds = float(value)

    if timeout_seconds <= 0:
        raise ConfigError(
            f"Check '{check_name}' has an invalid 'timeout_seconds'. It must be greater than zero."
        )

    return timeout_seconds


def _is_valid_http_url(value: str) -> bool:
    """Return whether a URL has an HTTP scheme and hostname."""
    parsed_url = urlparse(value)

    return parsed_url.scheme in {"http", "https"} and bool(parsed_url.netloc)


def _ensure_unique_names(endpoints: Sequence[EndpointConfig]) -> None:
    """Reject duplicate endpoint names."""
    names = [endpoint.name for endpoint in endpoints]
    duplicate_names = {name for name in names if names.count(name) > 1}

    if duplicate_names:
        duplicates = ", ".join(sorted(duplicate_names))
        raise ConfigError(f"Check names must be unique. Duplicate names: {duplicates}")


def _parse_alert_rules(
    raw_alert_rules: object,
    endpoints: tuple[EndpointConfig, ...],
) -> tuple[AlertRule, ...]:
    """Convert configured alert rules into validated domain models."""
    if not isinstance(raw_alert_rules, list):
        raise ConfigError("'alerts' must be a list.")

    endpoint_names = {endpoint.name for endpoint in endpoints}
    alert_rules = tuple(
        _parse_alert_rule(raw_alert_rule, position, endpoint_names)
        for position, raw_alert_rule in enumerate(raw_alert_rules, start=1)
    )
    names = [rule.name for rule in alert_rules]
    duplicate_names = {name for name in names if names.count(name) > 1}

    if duplicate_names:
        duplicates = ", ".join(sorted(duplicate_names))
        raise ConfigError(f"Alert rule names must be unique. Duplicate names: {duplicates}")

    return alert_rules


def _parse_alert_rule(
    raw_alert_rule: object,
    position: int,
    endpoint_names: set[str],
) -> AlertRule:
    """Validate one availability-threshold alert rule."""
    if not isinstance(raw_alert_rule, dict):
        raise ConfigError(f"Alert rule {position} must be a mapping.")

    name = raw_alert_rule.get("name")
    endpoint_name = raw_alert_rule.get("endpoint")
    rule_type = raw_alert_rule.get("type", "availability_below")

    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"Alert rule {position} must have a non-empty 'name'.")
    if not isinstance(endpoint_name, str) or endpoint_name not in endpoint_names:
        raise ConfigError(f"Alert rule '{name}' must reference a configured endpoint.")
    if rule_type != "availability_below":
        raise ConfigError(
            f"Alert rule '{name}' has unsupported type '{rule_type}'. "
            "Only 'availability_below' is supported."
        )

    return AlertRule(
        name=name,
        endpoint_name=endpoint_name,
        window_hours=_read_positive_int(
            raw_alert_rule.get("window_hours", 1),
            name,
            "window_hours",
        ),
        min_samples=_read_positive_int(
            raw_alert_rule.get("min_samples", 10),
            name,
            "min_samples",
        ),
        threshold_percent=_read_percentage(
            raw_alert_rule.get("threshold_percent"),
            name,
        ),
        notifications=_parse_notifications(
            raw_alert_rule.get("notifications", [{"type": "console"}]),
            name,
        ),
    )


def _read_positive_int(value: object, rule_name: str, field_name: str) -> int:
    """Return a positive integer alert-rule field."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"Alert rule '{rule_name}' must have a positive integer '{field_name}'.")

    return value


def _read_percentage(value: object, rule_name: str) -> float:
    """Return an availability percentage between zero and one hundred."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"Alert rule '{rule_name}' must have a numeric 'threshold_percent'.")

    percentage = float(value)
    if not 0 <= percentage <= 100:
        raise ConfigError(
            f"Alert rule '{rule_name}' must have 'threshold_percent' between 0 and 100."
        )

    return percentage


def _parse_notifications(
    raw_notifications: object,
    rule_name: str,
) -> tuple[NotificationConfig, ...]:
    """Validate configured notification destinations."""
    if not isinstance(raw_notifications, list) or not raw_notifications:
        raise ConfigError(f"Alert rule '{rule_name}' must have a notifications list.")

    return tuple(
        _parse_notification(raw_notification, rule_name, position)
        for position, raw_notification in enumerate(raw_notifications, start=1)
    )


def _parse_notification(
    raw_notification: object,
    rule_name: str,
    position: int,
) -> NotificationConfig:
    """Validate one alert delivery destination."""
    if not isinstance(raw_notification, dict):
        raise ConfigError(
            f"Notification {position} for alert rule '{rule_name}' must be a mapping."
        )

    notification_type = raw_notification.get("type")
    if notification_type == "console":
        return NotificationConfig(type="console")
    if notification_type == "webhook":
        url_env = raw_notification.get("url_env")
        if not isinstance(url_env, str) or not url_env.strip():
            raise ConfigError(
                f"Webhook notification for alert rule '{rule_name}' must have 'url_env'."
            )
        return NotificationConfig(type="webhook", url_env=url_env)
    if notification_type == "discord":
        url_env = raw_notification.get("url_env")
        if not isinstance(url_env, str) or not url_env.strip():
            raise ConfigError(
                f"Discord notification for alert rule '{rule_name}' must have 'url_env'."
            )
        return NotificationConfig(type="discord", url_env=url_env)

    raise ConfigError(
        f"Notification {position} for alert rule '{rule_name}' has unsupported "
        f"type '{notification_type}'."
    )
