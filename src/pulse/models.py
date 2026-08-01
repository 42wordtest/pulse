"""Domain models used by Pulse."""

from dataclasses import dataclass


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
