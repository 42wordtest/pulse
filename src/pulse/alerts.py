"""Alert-rule evaluation and notification-state decisions."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from .models import AlertRule, AlertState, EndpointConfig
from .storage import get_availability_window


@dataclass(frozen=True, slots=True)
class AlertEvaluation:
    """The current result of evaluating one configured alert rule."""

    rule: AlertRule
    endpoint: EndpointConfig
    status: Literal["alert", "ok", "insufficient_data"]
    message: str


@dataclass(frozen=True, slots=True)
class AlertEvent:
    """A notification-worthy transition in an alert's lifecycle."""

    evaluation: AlertEvaluation
    type: Literal["opened", "recovered"]


def evaluate_availability_alert(
    connection: sqlite3.Connection,
    *,
    rule: AlertRule,
    endpoint: EndpointConfig,
    now: datetime,
) -> AlertEvaluation:
    """Evaluate one availability threshold over its configured time window."""
    window = get_availability_window(
        connection,
        endpoint_name=endpoint.name,
        url=endpoint.url,
        since=now - timedelta(hours=rule.window_hours),
        until=now,
    )

    if window.total_checks < rule.min_samples:
        return AlertEvaluation(
            rule=rule,
            endpoint=endpoint,
            status="insufficient_data",
            message=(
                f"Only {window.total_checks}/{rule.min_samples} required checks "
                f"recorded in the last {rule.window_hours} hour(s)."
            ),
        )

    percentage = window.percentage
    sample_counts = f"{window.healthy_checks}/{window.total_checks} healthy"
    if percentage < rule.threshold_percent:
        return AlertEvaluation(
            rule=rule,
            endpoint=endpoint,
            status="alert",
            message=(
                f"Availability is {percentage:.1f}%, below the "
                f"{rule.threshold_percent:.1f}% threshold ({sample_counts})."
            ),
        )

    return AlertEvaluation(
        rule=rule,
        endpoint=endpoint,
        status="ok",
        message=(
            f"Availability is {percentage:.1f}%, meeting the "
            f"{rule.threshold_percent:.1f}% threshold ({sample_counts})."
        ),
    )


def get_alert_event(
    evaluation: AlertEvaluation,
    state: AlertState | None,
) -> AlertEvent | None:
    """Return an event only when an alert opens or recovers."""
    if evaluation.status == "insufficient_data":
        return None
    if evaluation.status == "alert" and (state is None or not state.active):
        return AlertEvent(evaluation=evaluation, type="opened")
    if evaluation.status == "ok" and state is not None and state.active:
        return AlertEvent(evaluation=evaluation, type="recovered")
    return None
