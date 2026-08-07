"""SQLite persistence for endpoint check results."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .checker import EndpointCheckResult
from .models import AlertState, AvailabilitySummary
from .regression import AvailabilityWindow

SCHEMA = """
CREATE TABLE IF NOT EXISTS check_results (
    id INTEGER PRIMARY KEY,
    checked_at TEXT NOT NULL,
    endpoint_name TEXT NOT NULL,
    url TEXT NOT NULL,
    healthy INTEGER NOT NULL,
    status_code INTEGER,
    latency_ms REAL NOT NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_check_results_endpoint_checked_at
ON check_results (endpoint_name, checked_at);

CREATE TABLE IF NOT EXISTS alert_states (
    rule_name TEXT NOT NULL,
    endpoint_name TEXT NOT NULL,
    active INTEGER NOT NULL,
    opened_at TEXT NOT NULL,
    last_notified_at TEXT NOT NULL,
    resolved_at TEXT,
    PRIMARY KEY (rule_name, endpoint_name)
);
"""

INSERT_CHECK_RESULT = """
INSERT INTO check_results (
    checked_at,
    endpoint_name,
    url,
    healthy,
    status_code,
    latency_ms,
    error_message
) VALUES (?, ?, ?, ?, ?, ?, ?);
"""

GET_AVAILABILITY = """
SELECT
    endpoint_name,
    url,
    COUNT(*) AS total_checks,
    SUM(CASE WHEN healthy = 1 THEN 1 ELSE 0 END) AS healthy_checks
FROM check_results
WHERE checked_at >= ?
GROUP BY endpoint_name, url
ORDER BY endpoint_name;
"""

GET_AVAILABILITY_WINDOW = """
SELECT
    COUNT(*) AS total_checks,
    SUM(CASE WHEN healthy = 1 THEN 1 ELSE 0 END) AS healthy_checks
FROM check_results
WHERE endpoint_name = ?
  AND url = ?
  AND checked_at >= ?
  AND checked_at < ?;
"""

GET_ALERT_STATE = """
SELECT rule_name, endpoint_name, active, opened_at, last_notified_at, resolved_at
FROM alert_states
WHERE rule_name = ? AND endpoint_name = ?;
"""

ACTIVATE_ALERT_STATE = """
INSERT INTO alert_states (
    rule_name, endpoint_name, active, opened_at, last_notified_at, resolved_at
) VALUES (?, ?, 1, ?, ?, NULL)
ON CONFLICT(rule_name, endpoint_name) DO UPDATE SET
    active = 1,
    opened_at = CASE
        WHEN alert_states.active = 0 THEN excluded.opened_at
        ELSE alert_states.opened_at
    END,
    last_notified_at = excluded.last_notified_at,
    resolved_at = NULL;
"""

RESOLVE_ALERT_STATE = """
UPDATE alert_states
SET active = 0, last_notified_at = ?, resolved_at = ?
WHERE rule_name = ? AND endpoint_name = ?;
"""


def initialise_database(database_path: Path) -> None:
    """Create the result database and schema when they do not yet exist."""
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)


def insert_check_result(
    connection: sqlite3.Connection,
    result: EndpointCheckResult,
    *,
    checked_at: datetime | None = None,
) -> None:
    """Insert one completed endpoint check into an existing transaction."""
    timestamp = checked_at or datetime.now(UTC)

    connection.execute(
        INSERT_CHECK_RESULT,
        (
            timestamp.isoformat(),
            result.endpoint.name,
            result.endpoint.url,
            int(result.healthy),
            result.status_code,
            result.latency_seconds * 1000,
            None if result.healthy else result.message,
        ),
    )


def get_availability(
    connection: sqlite3.Connection,
    *,
    since: datetime,
) -> list[AvailabilitySummary]:
    rows = connection.execute(
        GET_AVAILABILITY,
        (since.isoformat(),),
    ).fetchall()

    return [
        AvailabilitySummary(
            endpoint_name=endpoint_name,
            url=url,
            total_checks=total_checks,
            healthy_checks=healthy_checks,
        )
        for endpoint_name, url, total_checks, healthy_checks in rows
    ]


def get_availability_window(
    connection: sqlite3.Connection,
    *,
    endpoint_name: str,
    url: str,
    since: datetime,
    until: datetime,
) -> AvailabilityWindow:
    """Return one endpoint's check counts within a half-open time window."""
    row = connection.execute(
        GET_AVAILABILITY_WINDOW,
        (endpoint_name, url, since.isoformat(), until.isoformat()),
    ).fetchone()

    if row is None:
        return AvailabilityWindow(healthy_checks=0, total_checks=0)

    total_checks, healthy_checks = row
    return AvailabilityWindow(
        healthy_checks=healthy_checks or 0,
        total_checks=total_checks,
    )


def get_alert_state(
    connection: sqlite3.Connection,
    *,
    rule_name: str,
    endpoint_name: str,
) -> AlertState | None:
    """Return the persisted state for an alert rule, if it has ever notified."""
    row = connection.execute(GET_ALERT_STATE, (rule_name, endpoint_name)).fetchone()
    if row is None:
        return None

    (
        stored_rule_name,
        stored_endpoint_name,
        active,
        opened_at,
        last_notified_at,
        resolved_at,
    ) = row
    return AlertState(
        rule_name=stored_rule_name,
        endpoint_name=stored_endpoint_name,
        active=bool(active),
        opened_at=datetime.fromisoformat(opened_at),
        last_notified_at=datetime.fromisoformat(last_notified_at),
        resolved_at=datetime.fromisoformat(resolved_at) if resolved_at is not None else None,
    )


def activate_alert_state(
    connection: sqlite3.Connection,
    *,
    rule_name: str,
    endpoint_name: str,
    occurred_at: datetime,
) -> None:
    """Persist an alert opening and its notification timestamp."""
    timestamp = occurred_at.isoformat()
    connection.execute(
        ACTIVATE_ALERT_STATE,
        (rule_name, endpoint_name, timestamp, timestamp),
    )


def resolve_alert_state(
    connection: sqlite3.Connection,
    *,
    rule_name: str,
    endpoint_name: str,
    occurred_at: datetime,
) -> None:
    """Persist the recovery of an active alert."""
    timestamp = occurred_at.isoformat()
    connection.execute(
        RESOLVE_ALERT_STATE,
        (timestamp, timestamp, rule_name, endpoint_name),
    )
