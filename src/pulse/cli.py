"""Command-line interface for Pulse."""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console

from .checker import check_endpoints
from .config import ConfigError, load_config
from .regression import detect_availability_regression
from .storage import (
    get_availability,
    get_availability_window,
    initialise_database,
    insert_check_result,
)

app = typer.Typer(
    no_args_is_help=True,
    help="Check the health of configured HTTP endpoints.",
)

console = Console()


@app.callback()
def main() -> None:
    """Pulse checks configured HTTP endpoints."""


@app.command()
def check() -> None:
    """Run configured health checks."""
    try:
        endpoints = load_config(Path("pulse.yaml"))
    except ConfigError as error:
        console.print(f"Configuration error: {error}")
        raise typer.Exit(code=1)

    database_path = Path(".pulse/pulse.db")
    initialise_database(database_path)

    results = asyncio.run(check_endpoints(endpoints))

    with sqlite3.connect(database_path) as connection:
        for result in results:
            insert_check_result(connection, result)
            state = "HEALTHY" if result.healthy else "UNHEALTHY"
            latency_ms = result.latency_seconds * 1000
            console.print(
                f"{state} {result.endpoint.name} ({latency_ms:.0f} ms) — {result.message}"
            )
    if any(not result.healthy for result in results):
        raise typer.Exit(code=1)


@app.command()
def availability(
    hours: int = typer.Option(
        24,
        min=1,
        help="Number of hours of check history to include.",
    ),
) -> None:
    """Show endpoint availability over a time window."""
    database_path = Path(".pulse/pulse.db")
    initialise_database(database_path)
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    with sqlite3.connect(database_path) as connection:
        summaries = get_availability(connection, since=cutoff)

    if not summaries:
        console.print(f"No check results found in the last {hours} hours.")
        return

    for summary in summaries:
        console.print(
            f"{summary.endpoint_name}: {summary.percentage:.1f}% "
            f"({summary.healthy_checks}/{summary.total_checks} healthy)"
        )


@app.command()
def regression(
    recent_hours: int = typer.Option(
        1,
        min=1,
        help="Number of recent hours to evaluate.",
    ),
    baseline_hours: int = typer.Option(
        168,
        min=1,
        help="Number of baseline hours to compare against.",
    ),
) -> None:
    try:
        endpoints = load_config(Path("pulse.yaml"))
    except ConfigError as error:
        console.print(f"Configuration error: {error}")
        raise typer.Exit(code=1) from error

    database_path = Path(".pulse/pulse.db")
    initialise_database(database_path)

    now = datetime.now(UTC)
    recent_start = now - timedelta(hours=recent_hours)
    baseline_start = recent_start - timedelta(hours=baseline_hours)

    with sqlite3.connect(database_path) as connection:
        for endpoint in endpoints:
            recent = get_availability_window(
                connection,
                endpoint_name=endpoint.name,
                url=endpoint.url,
                since=recent_start,
                until=now,
            )
            baseline = get_availability_window(
                connection,
                endpoint_name=endpoint.name,
                url=endpoint.url,
                since=baseline_start,
                until=recent_start,
            )

            result = detect_availability_regression(recent, baseline)

            if result is None:
                console.print(f"{endpoint.name}: insufficient data")
            elif result.regressed:
                console.print(
                    f"{endpoint.name}: REGRESSION — "
                    f"{result.recent_percentage:.1f}% vs "
                    f"{result.baseline_percentage:.1f}% "
                    f"(down {result.drop_percentage_points:.1f} points)"
                )
            else:
                console.print(
                    f"{endpoint.name}: stable — {result.recent_percentage:.1f}% availability"
                )
