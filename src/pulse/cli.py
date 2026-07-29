"""Command-line interface for Pulse."""

from pathlib import Path

import typer
from rich.console import Console

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
    """List the endpoint checks configured in pulse.yaml."""
    config_path = Path("pulse.yaml")

    try:
        endpoints = load_config(config_path)
    except ConfigError as error:
        console.print(f"[bold red]Configuration error:[/bold red] {error}")
        raise typer.Exit(code=1) from error

    count = len(endpoints)
    noun = "check" if count == 1 else "checks"
    console.print(f"[bold green]Found {count} endpoint {noun}:[/bold green]")

    for endpoint in endpoints:
        console.print(
            "- "
            f"{endpoint.name}: {endpoint.url} "
            f"(expects {endpoint.expected_status}; "
            f"timeout {endpoint.timeout_seconds:g}s)"
        )
