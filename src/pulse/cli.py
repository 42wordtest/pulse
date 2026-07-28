"""Command-line interface for Pulse."""

import typer
from rich.console import Console

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
    console.print("[bold green]Pulse is ready.[/bold green]")
