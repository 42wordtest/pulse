"""Delivery adapters for alert events."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

from .alerts import AlertEvent
from .models import NotificationConfig


@dataclass(frozen=True, slots=True)
class NotificationDelivery:
    """The result of sending one configured notification."""

    channel: str
    succeeded: bool
    message: str


def deliver_notifications(
    event: AlertEvent,
    notifications: tuple[NotificationConfig, ...],
    *,
    environment: Mapping[str, str] | None = None,
    client: httpx.Client | None = None,
) -> list[NotificationDelivery]:
    """Deliver an alert event to every configured destination."""
    if client is not None:
        return _deliver_notifications(event, notifications, environment, client)

    with httpx.Client(timeout=5.0) as new_client:
        return _deliver_notifications(event, notifications, environment, new_client)


def _deliver_notifications(
    event: AlertEvent,
    notifications: tuple[NotificationConfig, ...],
    environment: Mapping[str, str] | None,
    client: httpx.Client,
) -> list[NotificationDelivery]:
    """Send notifications with a shared client."""
    env = os.environ if environment is None else environment
    return [
        _deliver_notification(event, notification, env, client) for notification in notifications
    ]


def _deliver_notification(
    event: AlertEvent,
    notification: NotificationConfig,
    environment: Mapping[str, str],
    client: httpx.Client,
) -> NotificationDelivery:
    """Send one console, generic webhook, or Discord notification."""
    if notification.type == "console":
        return NotificationDelivery(
            channel="console",
            succeeded=True,
            message=_event_message(event),
        )

    if notification.type == "discord":
        return _deliver_discord(event, notification, environment, client)

    url_env = notification.url_env
    webhook_url = environment.get(url_env) if url_env is not None else None
    if not webhook_url:
        return NotificationDelivery(
            channel="webhook",
            succeeded=False,
            message=f"Webhook environment variable '{url_env}' is not set.",
        )

    try:
        response = client.post(webhook_url, json=_event_payload(event))
        response.raise_for_status()
    except httpx.HTTPError as error:
        return NotificationDelivery(
            channel="webhook",
            succeeded=False,
            message=f"Webhook delivery failed: {error}",
        )

    return NotificationDelivery(
        channel="webhook",
        succeeded=True,
        message="Webhook delivery succeeded.",
    )


def _deliver_discord(
    event: AlertEvent,
    notification: NotificationConfig,
    environment: Mapping[str, str],
    client: httpx.Client,
) -> NotificationDelivery:
    """Send one alert event using Discord's webhook payload format."""
    url_env = notification.url_env
    webhook_url = environment.get(url_env) if url_env is not None else None
    if not webhook_url:
        return NotificationDelivery(
            channel="discord",
            succeeded=False,
            message=f"Discord webhook environment variable '{url_env}' is not set.",
        )

    try:
        response = client.post(webhook_url, json=_discord_payload(event))
        response.raise_for_status()
    except httpx.HTTPError as error:
        return NotificationDelivery(
            channel="discord",
            succeeded=False,
            message=f"Discord webhook delivery failed: {error}",
        )

    return NotificationDelivery(
        channel="discord",
        succeeded=True,
        message="Discord webhook delivery succeeded.",
    )


def _event_message(event: AlertEvent) -> str:
    """Format a concise human-readable alert notification."""
    state = "ALERT" if event.type == "opened" else "RECOVERED"
    evaluation = event.evaluation
    return f"{state} {evaluation.rule.name} ({evaluation.endpoint.name}): {evaluation.message}"


def _event_payload(event: AlertEvent) -> dict[str, str]:
    """Build the JSON payload shared by generic webhook integrations."""
    evaluation = event.evaluation
    return {
        "event": event.type,
        "rule": evaluation.rule.name,
        "endpoint": evaluation.endpoint.name,
        "status": evaluation.status,
        "message": evaluation.message,
    }


def _discord_payload(event: AlertEvent) -> dict[str, object]:
    """Build a Discord-safe webhook payload without allowing mentions."""
    return {
        "content": _event_message(event)[:2000],
        "allowed_mentions": {"parse": []},
    }
