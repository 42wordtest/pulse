"""Synchronous HTTP endpoint checks."""

from dataclasses import dataclass
from time import perf_counter

import httpx

from .models import EndpointConfig


@dataclass(frozen=True, slots=True)
class EndpointCheckResult:
    """The outcome of checking one configured endpoint."""

    endpoint: EndpointConfig
    healthy: bool
    latency_seconds: float
    message: str
    status_code: int | None = None


def check_endpoint(
    endpoint: EndpointConfig,
    *,
    client: httpx.Client | None = None,
) -> EndpointCheckResult:
    """Send a synchronous GET request to an endpoint and report its outcome."""
    if client is not None:
        return _send_get_request(endpoint, client)

    with httpx.Client(timeout=endpoint.timeout_seconds) as new_client:
        return _send_get_request(endpoint, new_client)


def _send_get_request(
    endpoint: EndpointConfig,
    client: httpx.Client,
) -> EndpointCheckResult:
    """Perform the request and translate expected network failures into results."""
    started_at = perf_counter()

    try:
        response = client.get(endpoint.url)
    except httpx.TimeoutException:
        return EndpointCheckResult(
            endpoint=endpoint,
            healthy=False,
            latency_seconds=perf_counter() - started_at,
            message=(
                f"Timed out after {endpoint.timeout_seconds:g}s while requesting "
                f"{endpoint.url}."
            ),
        )
    except httpx.ConnectError as error:
        return EndpointCheckResult(
            endpoint=endpoint,
            healthy=False,
            latency_seconds=perf_counter() - started_at,
            message=f"Connection error while requesting {endpoint.url}: {error}",
        )
    except httpx.RequestError as error:
        return EndpointCheckResult(
            endpoint=endpoint,
            healthy=False,
            latency_seconds=perf_counter() - started_at,
            message=f"Request error while requesting {endpoint.url}: {error}",
        )

    latency_seconds = perf_counter() - started_at
    healthy = response.status_code == endpoint.expected_status

    if healthy:
        message = f"Healthy: received expected HTTP {response.status_code}."
    else:
        message = (
            f"Unhealthy: expected HTTP {endpoint.expected_status} "
            f"but received HTTP {response.status_code}."
        )

    return EndpointCheckResult(
        endpoint=endpoint,
        healthy=healthy,
        latency_seconds=latency_seconds,
        message=message,
        status_code=response.status_code,
    )
