"""Domain models used by Pulse."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EndpointConfig:
    """Configuration for one monitored HTTP endpoint."""

    name: str
    url: str
    expected_status: int = 200
    timeout_seconds: float = 5.0
