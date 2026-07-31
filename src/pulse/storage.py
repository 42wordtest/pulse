"""SQLite persistence for endpoint check results."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .checker import EndpointCheckResult

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
    timestamp = checked_at or datetime.now(timezone.utc)

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
