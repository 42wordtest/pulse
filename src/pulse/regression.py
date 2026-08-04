"""Reliability regression detection."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AvailabilityWindow:
    """Availability measurements for one time window."""

    healthy_checks: int
    total_checks: int

    @property
    def percentage(self) -> float:
        return self.healthy_checks / self.total_checks * 100


@dataclass(frozen=True, slots=True)
class AvailabilityRegression:
    """Comparison of recent availability against a baseline."""

    recent_percentage: float
    baseline_percentage: float
    drop_percentage_points: float
    regressed: bool


def detect_availability_regression(
    recent: AvailabilityWindow,
    baseline: AvailabilityWindow,
    *,
    minimum_samples: int = 10,
    allowed_drop_percentage_points: float = 2.0,
) -> AvailabilityRegression | None:
    """Return None when there is insufficient data; otherwise compare windows."""
    if recent.total_checks < minimum_samples or baseline.total_checks < minimum_samples:
        return None

    recent_percentage = recent.percentage
    baseline_percentage = baseline.percentage
    drop = baseline_percentage - recent_percentage

    return AvailabilityRegression(
        recent_percentage=recent_percentage,
        baseline_percentage=baseline_percentage,
        drop_percentage_points=drop,
        regressed=drop >= allowed_drop_percentage_points,
    )
