"""Tests for SQLite check-result storage."""

import sqlite3
from datetime import datetime, UTC
from pathlib import Path

from pulse.checker import EndpointCheckResult
from pulse.models import EndpointConfig
from pulse.storage import initialise_database, insert_check_result


def test_insert_check_result_persists_a_failed_check(tmp_path: Path) -> None:
    """A failed check should retain its timestamp, metrics, and error message."""
    database_path = tmp_path / "pulse.db"
    result = EndpointCheckResult(
        endpoint=EndpointConfig("api", "https://api.example.com/health"),
        healthy=False,
        latency_seconds=0.123,
        status_code=503,
        message="Unhealthy: expected HTTP 200 but received HTTP 503.",
    )
    checked_at = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)

    initialise_database(database_path)
    with sqlite3.connect(database_path) as connection:
        insert_check_result(connection, result, checked_at=checked_at)

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT checked_at, endpoint_name, url, healthy, status_code,
                   latency_ms, error_message
            FROM check_results
            """
        ).fetchone()

    assert row == (
        "2026-07-31T12:00:00+00:00",
        "api",
        "https://api.example.com/health",
        0,
        503,
        123.0,
        "Unhealthy: expected HTTP 200 but received HTTP 503.",
    )
