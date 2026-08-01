"""Command-line interface for Pulse."""

import asyncio
from datetime import UTC, datetime, timedelta
import sqlite3
from pathlib import Path

import typer
from rich.console import Console

from .checker import check_endpoints
from .config import ConfigError, load_config
from .storage import initialise_database, insert_check_result, get_availability

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

    if any(not result.healthy for result in results):
        raise typer.Exit(code=1)

    with sqlite3.connect(database_path) as connection:
        for result in results:
            insert_check_result(connection, result)
            state = "HEALTHY" if result.healthy else "UNHEALTHY"
            latency_ms = result.latency_seconds * 1000
            console.print(
                f"{state} {result.endpoint.name} ({latency_ms:.0f} ms) — {result.message}"
            )

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