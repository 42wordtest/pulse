"""Command-line interface for Pulse."""
import sqlite3
from pathlib import Path

import typer
from rich.console import Console

from .checker import check_endpoint
from .config import ConfigError, load_config
from .storage import insert_check_result, initialise_database

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

    results = [check_endpoint(endpoint) for endpoint in endpoints]
    with sqlite3.connect(database_path) as connection:
        for result in results:
            insert_check_result(connection, result)
            state = "HEALTHY" if result.healthy else "UNHEALTHY"
            latency_ms = result.latency_seconds * 1000
            console.print(
                f"{state} {result.endpoint.name} ({latency_ms:.0f} ms) — {result.message}"
            )
