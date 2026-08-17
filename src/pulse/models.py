"""Domain models used by Pulse."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class EndpointConfig:
    """Configuration for one monitored HTTP endpoint."""

    name: str
    url: str
    expected_status: int = 200
    timeout_seconds: float = 5.0


@dataclass(frozen=True, slots=True)
class AvailabilitySummary:
    endpoint_name: str
    url: str
    total_checks: int
    healthy_checks: int

    @property
    def percentage(self) -> float:
        return self.healthy_checks / self.total_checks * 100


@dataclass(frozen=True, slots=True)
class NotificationConfig:
    """One configured alert delivery destination."""

    type: Literal["console", "webhook", "discord"]
    url_env: str | None = None


@dataclass(frozen=True, slots=True)
class AlertRule:
    """An availability threshold evaluated for one configured endpoint."""

    name: str
    endpoint_name: str
    window_hours: int
    min_samples: int
    threshold_percent: float
    notifications: tuple[NotificationConfig, ...]


@dataclass(frozen=True, slots=True)
class PulseConfig:
    """All validated Pulse configuration."""

    endpoints: tuple[EndpointConfig, ...]
    alert_rules: tuple[AlertRule, ...]


@dataclass(frozen=True, slots=True)
class AlertState:
    """Persisted notification state for one alert rule and endpoint."""

    rule_name: str
    endpoint_name: str
    active: bool
    opened_at: datetime
    last_notified_at: datetime
    resolved_at: datetime | None
