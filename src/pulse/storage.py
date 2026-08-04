"""SQLite persistence for endpoint check results."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .checker import EndpointCheckResult
from .models import AvailabilitySummary
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
