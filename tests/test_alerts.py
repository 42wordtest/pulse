"""Tests for availability alert evaluation and state transitions."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pulse.alerts import evaluate_availability_alert, get_alert_event
from pulse.checker import EndpointCheckResult
from pulse.models import AlertRule, EndpointConfig, NotificationConfig
from pulse.storage import (
    activate_alert_state,
    get_alert_state,
    initialise_database,
    insert_check_result,
    resolve_alert_state,
)


def make_rule() -> AlertRule:
    """Build a simple availability rule for one endpoint."""
    return AlertRule(
        name="api-availability",
        endpoint_name="api",
        window_hours=1,
        min_samples=3,
        threshold_percent=99.0,
        notifications=(NotificationConfig(type="console"),),
    )


def insert_result(
    connection: sqlite3.Connection,
    endpoint: EndpointConfig,
    *,
    healthy: bool,
    checked_at: datetime,
) -> None:
    """Store one deterministic check result for alert evaluation."""
    insert_check_result(
        connection,
        EndpointCheckResult(
            endpoint=endpoint,
            healthy=healthy,
            latency_seconds=0.1,
            status_code=200 if healthy else 503,
            message="result",
        ),
        checked_at=checked_at,
    )


def test_availability_alert_opens_only_on_the_first_unhealthy_evaluation(
    tmp_path: Path,
) -> None:
    """An already-active alert should not produce duplicate open events."""
    database_path = tmp_path / "pulse.db"
    endpoint = EndpointConfig("api", "https://api.example.com/health")
    rule = make_rule()
    now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)

    initialise_database(database_path)
    with sqlite3.connect(database_path) as connection:
        insert_result(connection, endpoint, healthy=True, checked_at=now - timedelta(minutes=3))
        insert_result(connection, endpoint, healthy=True, checked_at=now - timedelta(minutes=2))
        insert_result(connection, endpoint, healthy=False, checked_at=now - timedelta(minutes=1))

        evaluation = evaluate_availability_alert(
            connection,
            rule=rule,
            endpoint=endpoint,
            now=now,
        )
        event = get_alert_event(evaluation, state=None)

        assert evaluation.status == "alert"
        assert event is not None
        assert event.type == "opened"

        activate_alert_state(
            connection,
            rule_name=rule.name,
            endpoint_name=endpoint.name,
            occurred_at=now,
        )
        state = get_alert_state(
            connection,
            rule_name=rule.name,
            endpoint_name=endpoint.name,
        )

        assert get_alert_event(evaluation, state) is None


def test_availability_alert_recovers_when_the_threshold_is_met(tmp_path: Path) -> None:
    """An active alert should emit one recovery event after it returns to normal."""
    database_path = tmp_path / "pulse.db"
    endpoint = EndpointConfig("api", "https://api.example.com/health")
    rule = make_rule()
    now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)

    initialise_database(database_path)
    with sqlite3.connect(database_path) as connection:
        for minute in range(3):
            insert_result(
                connection,
                endpoint,
                healthy=True,
                checked_at=now - timedelta(minutes=minute + 1),
            )
        activate_alert_state(
            connection,
            rule_name=rule.name,
            endpoint_name=endpoint.name,
            occurred_at=now - timedelta(minutes=4),
        )

        evaluation = evaluate_availability_alert(
            connection,
            rule=rule,
            endpoint=endpoint,
            now=now,
        )
        state = get_alert_state(
            connection,
            rule_name=rule.name,
            endpoint_name=endpoint.name,
        )
        event = get_alert_event(evaluation, state)

        assert evaluation.status == "ok"
        assert event is not None
        assert event.type == "recovered"

        resolve_alert_state(
            connection,
            rule_name=rule.name,
            endpoint_name=endpoint.name,
            occurred_at=now,
        )

    with sqlite3.connect(database_path) as connection:
        state = get_alert_state(
            connection,
            rule_name=rule.name,
            endpoint_name=endpoint.name,
        )

    assert state is not None
    assert state.active is False
    assert state.resolved_at == now
