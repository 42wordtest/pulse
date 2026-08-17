"""Command-line interface for Pulse."""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console

from .alerts import evaluate_availability_alert, get_alert_event
from .checker import check_endpoints
from .config import ConfigError, load_config, load_pulse_config
from .notifications import deliver_notifications
from .regression import detect_availability_regression
from .storage import (
    activate_alert_state,
    get_alert_state,
    get_availability,
    get_availability_window,
    initialise_database,
    insert_check_result,
    resolve_alert_state,
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


@app.command()
def alerts() -> None:
    """Evaluate alert rules and deliver opening or recovery notifications."""
    try:
        config = load_pulse_config(Path("pulse.yaml"))
    except ConfigError as error:
        console.print(f"Configuration error: {error}")
        raise typer.Exit(code=1) from error

    if not config.alert_rules:
        console.print("No alert rules are configured.")
        return

    endpoints = {endpoint.name: endpoint for endpoint in config.endpoints}
    database_path = Path(".pulse/pulse.db")
    initialise_database(database_path)
    now = datetime.now(UTC)
    has_active_alert = False

    with sqlite3.connect(database_path) as connection:
        for rule in config.alert_rules:
            endpoint = endpoints[rule.endpoint_name]
            evaluation = evaluate_availability_alert(
                connection,
                rule=rule,
                endpoint=endpoint,
                now=now,
            )
            state = get_alert_state(
                connection,
                rule_name=rule.name,
                endpoint_name=endpoint.name,
            )
            event = get_alert_event(evaluation, state)

            if evaluation.status == "insufficient_data":
                console.print(f"INSUFFICIENT {rule.name}: {evaluation.message}")
                continue

            if evaluation.status == "alert":
                has_active_alert = True

            if event is None:
                state_label = "ALERT ACTIVE" if evaluation.status == "alert" else "OK"
                console.print(f"{state_label} {rule.name}: {evaluation.message}")
                continue

            deliveries = deliver_notifications(event, rule.notifications)
            for delivery in deliveries:
                status = "NOTIFIED" if delivery.succeeded else "NOTIFY FAILED"
                console.print(f"{status} {delivery.channel}: {delivery.message}")

            if not all(delivery.succeeded for delivery in deliveries):
                continue
            if event.type == "opened":
                activate_alert_state(
                    connection,
                    rule_name=rule.name,
                    endpoint_name=endpoint.name,
                    occurred_at=now,
                )
            else:
                resolve_alert_state(
                    connection,
                    rule_name=rule.name,
                    endpoint_name=endpoint.name,
                    occurred_at=now,
                )

    if has_active_alert:
        raise typer.Exit(code=1)
