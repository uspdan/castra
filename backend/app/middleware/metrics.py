"""Prometheus instrumentation — Sprint 10 Phase A.

Records the RED triad (CLAUDE.md §14.2) plus a few platform-
specific gauges:

- ``http_requests_total{method, route, status}`` — counter
- ``http_request_duration_seconds{method, route}`` — histogram
- ``http_requests_in_progress{method}`` — gauge

The ``route`` label is the FastAPI route template (e.g.
``/api/v1/challenges/{slug}``) rather than the materialised URL.
This keeps the cardinality bounded — one series per route * method *
status, not per slug.
"""

from __future__ import annotations

import time

from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests, labelled by method / route template / status code.",
    ("method", "route", "status"),
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Request duration in seconds, labelled by method / route template.",
    ("method", "route"),
    # Buckets tuned for an interactive API: 5ms, 10ms, ..., 5s.
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being handled.",
    ("method",),
)


def _route_template(request: Request) -> str:
    """Resolve the ``Route.path`` (e.g. ``/users/{id}``) for the
    matched endpoint, or fall back to the literal path."""

    route = request.scope.get("route")
    if route is None:
        return request.url.path
    # ``Route`` exposes ``.path``; ``Mount`` exposes ``.path`` too.
    return getattr(route, "path", request.url.path)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        method = request.method
        # /metrics scrapes itself shouldn't count as user traffic; skip.
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        REQUESTS_IN_PROGRESS.labels(method=method).inc()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            route = _route_template(request)
            REQUEST_COUNT.labels(
                method=method, route=route, status=str(status_code)
            ).inc()
            REQUEST_DURATION.labels(method=method, route=route).observe(duration)
            REQUESTS_IN_PROGRESS.labels(method=method).dec()


__all__ = [
    "REQUEST_COUNT",
    "REQUEST_DURATION",
    "REQUESTS_IN_PROGRESS",
    "PrometheusMetricsMiddleware",
]
