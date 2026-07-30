"""Command-line interface for Pulse."""

import asyncio
from pathlib import Path

import typer
from rich.console import Console

from .checker import check_endpoints
from .config import ConfigError, load_config

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

    results = asyncio.run(check_endpoints(endpoints))

    if any(not result.healthy for result in results):
        raise typer.Exit(code=1)

    for result in results:
        state = "HEALTHY" if result.healthy else "UNHEALTHY"
        latency_ms = result.latency_seconds * 1000
        console.print(
            f"{state} {result.endpoint.name} ({latency_ms:.0f} ms) — {result.message}"
        )
