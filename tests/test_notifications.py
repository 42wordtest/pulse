"""Tests for alert notification delivery."""

import json

import httpx

from pulse.alerts import AlertEvaluation, AlertEvent
from pulse.models import AlertRule, EndpointConfig, NotificationConfig
from pulse.notifications import deliver_notifications


def make_event() -> AlertEvent:
    """Build a representative opened-alert event."""
    rule = AlertRule(
        name="api-availability",
        endpoint_name="api",
        window_hours=1,
        min_samples=10,
        threshold_percent=99.0,
        notifications=(),
    )
    endpoint = EndpointConfig("api", "https://api.example.com/health")
    evaluation = AlertEvaluation(
        rule=rule,
        endpoint=endpoint,
        status="alert",
        message="Availability is 90.0%, below the 99.0% threshold.",
    )
    return AlertEvent(evaluation=evaluation, type="opened")


def test_deliver_notifications_posts_a_generic_webhook_payload() -> None:
    """Webhooks should receive only useful alert metadata, never environment names."""
    event = make_event()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://alerts.example.com/notify"
        assert json.loads(request.content) == {
            "endpoint": "api",
            "event": "opened",
            "message": "Availability is 90.0%, below the 99.0% threshold.",
            "rule": "api-availability",
            "status": "alert",
        }
        return httpx.Response(204, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        deliveries = deliver_notifications(
            event,
            (NotificationConfig(type="webhook", url_env="PULSE_ALERT_WEBHOOK_URL"),),
            environment={"PULSE_ALERT_WEBHOOK_URL": "https://alerts.example.com/notify"},
            client=client,
        )

    assert deliveries[0].channel == "webhook"
    assert deliveries[0].succeeded is True


def test_deliver_notifications_reports_missing_webhook_configuration() -> None:
    """A missing environment variable should fail without attempting a request."""
    deliveries = deliver_notifications(
        make_event(),
        (NotificationConfig(type="webhook", url_env="PULSE_ALERT_WEBHOOK_URL"),),
        environment={},
    )

    assert deliveries[0].succeeded is False
    assert "PULSE_ALERT_WEBHOOK_URL" in deliveries[0].message


def test_deliver_notifications_posts_a_discord_compatible_payload() -> None:
    """Discord should receive content and have all mentions disabled."""
    event = make_event()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://discord.com/api/webhooks/example"
        assert json.loads(request.content) == {
            "allowed_mentions": {"parse": []},
            "content": (
                "ALERT api-availability (api): Availability is 90.0%, below the 99.0% threshold."
            ),
        }
        return httpx.Response(204, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        deliveries = deliver_notifications(
            event,
            (NotificationConfig(type="discord", url_env="PULSE_DISCORD_WEBHOOK_URL"),),
            environment={"PULSE_DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/example"},
            client=client,
        )

    assert deliveries[0].channel == "discord"
    assert deliveries[0].succeeded is True


def test_deliver_notifications_reports_missing_discord_configuration() -> None:
    """A missing Discord environment variable should not make a network request."""
    deliveries = deliver_notifications(
        make_event(),
        (NotificationConfig(type="discord", url_env="PULSE_DISCORD_WEBHOOK_URL"),),
        environment={},
    )

    assert deliveries[0].channel == "discord"
    assert deliveries[0].succeeded is False
    assert "PULSE_DISCORD_WEBHOOK_URL" in deliveries[0].message
