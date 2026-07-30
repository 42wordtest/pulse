"""Asynchronous HTTP endpoint checks."""

import asyncio
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


async def check_endpoint(
    endpoint: EndpointConfig,
    *,
    client: httpx.AsyncClient,
) -> EndpointCheckResult:
    """Send asynchronous GET request to an endpoint and report its outcome."""
    return await _send_get_request(endpoint, client)


async def check_endpoints(
    endpoints: list[EndpointConfig],
) -> list[EndpointCheckResult]:
    async with httpx.AsyncClient() as client:
        tasks = [check_endpoint(endpoint, client=client) for endpoint in endpoints]
        return await asyncio.gather(*tasks)


async def _send_get_request(
    endpoint: EndpointConfig, client: httpx.Client
) -> EndpointCheckResult:
    """Perform the request and translate expected network failures into results."""
    started_at = perf_counter()

    try:
        response = await client.get(
            endpoint.url,
            timeout=endpoint.timeout_seconds,
        )
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
