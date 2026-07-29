"""Tests for synchronous endpoint checks."""

import httpx

from pulse.checker import check_endpoint
from pulse.models import EndpointConfig


def make_endpoint(
    *,
    name: str = "example",
    url: str = "https://example.com/health",
    expected_status: int = 200,
    timeout_seconds: float = 5.0,
) -> EndpointConfig:
    """Build a valid endpoint with optional field overrides."""
    return EndpointConfig(
        name=name,
        url=url,
        expected_status=expected_status,
        timeout_seconds=timeout_seconds,
    )


def test_check_endpoint_sends_get_and_marks_expected_status_healthy() -> None:
    """A matching HTTP status is reported as a healthy endpoint."""
    endpoint = make_endpoint()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == endpoint.url
        return httpx.Response(200, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_endpoint(endpoint, client=client)

    assert result.healthy is True
    assert result.status_code == 200
    assert result.latency_seconds >= 0
    assert result.message == "Healthy: received expected HTTP 200."


def test_check_endpoint_marks_an_unexpected_status_unhealthy() -> None:
    """A non-matching HTTP status is reported as unhealthy."""
    endpoint = make_endpoint(expected_status=204)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = check_endpoint(endpoint, client=client)

    assert result.healthy is False
    assert result.status_code == 503
    assert result.message == "Unhealthy: expected HTTP 204 but received HTTP 503."


def test_check_endpoint_reports_timeouts_cleanly() -> None:
    """Timeout exceptions should return a useful failed-check result."""
    endpoint = make_endpoint(timeout_seconds=2.0)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_endpoint(endpoint, client=client)

    assert result.healthy is False
    assert result.status_code is None
    assert result.latency_seconds >= 0
    assert result.message == (
        "Timed out after 2s while requesting https://example.com/health."
    )


def test_check_endpoint_reports_connection_errors_cleanly() -> None:
    """Connection errors should return a useful failed-check result."""
    endpoint = make_endpoint()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = check_endpoint(endpoint, client=client)

    assert result.healthy is False
    assert result.status_code is None
    assert result.latency_seconds >= 0
    assert result.message == (
        "Connection error while requesting https://example.com/health: "
        "connection refused"
    )
