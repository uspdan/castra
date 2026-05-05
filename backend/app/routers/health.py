"""Liveness (`/health`) and readiness (`/readyz`) endpoints.

Per CLAUDE.md §14.1:
    - /health is liveness only — process is up. Cheap. Used by Docker /
      orchestrator restart loops. Never 503.
    - /readyz checks every external dependency. 200 only if everything
      the app needs to handle a request is reachable. 503 with a
      per-probe breakdown otherwise.

Probes run **concurrently** with a per-probe `asyncio.wait_for` ceiling
so a slow Redis can't drag the whole readiness check out. Result is
cached in-process for ``_CACHE_TTL_S`` seconds so a load balancer
hammering /readyz at 1 Hz doesn't translate into 1 Hz of probes.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Response
from sqlalchemy import text

from app.config import get_settings
from app.database import async_session


router = APIRouter(tags=["health"])
logger = structlog.get_logger()


_PROBE_TIMEOUT_S: float = 2.0
_CACHE_TTL_S: float = 5.0


_cache_lock = asyncio.Lock()
_cache: dict[str, Any] = {"expires_at": 0.0, "report": None}


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness — process is up. No dependency checks. Always 200."""

    return {"status": "ok", "version": "2.4.1"}


async def _probe_postgres() -> None:
    async with async_session() as db:
        await db.execute(text("SELECT 1"))


async def _probe_redis() -> None:
    settings = get_settings()
    client = aioredis.from_url(settings.REDIS_URL)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def _probe_docker() -> None:
    # docker-py is sync; run in a thread so it doesn't block the loop
    # and so the per-probe wait_for actually times out. Phase 9 routes
    # this through the long-lived client wired to the docker-socket-proxy
    # so a 1-Hz readyz hammer doesn't churn fresh TCP sessions.
    from app.services.orchestration import docker_client

    def _ping() -> None:
        client = docker_client.get()
        client.ping()

    await asyncio.to_thread(_ping)


_PROBES: dict[str, Any] = {
    "postgres": _probe_postgres,
    "redis": _probe_redis,
    "docker": _probe_docker,
}


async def _run_probe(name: str, fn) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        await asyncio.wait_for(fn(), timeout=_PROBE_TIMEOUT_S)
        return {
            "name": name,
            "ok": True,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except asyncio.TimeoutError:
        return {
            "name": name,
            "ok": False,
            "error": "timeout",
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except Exception as exc:  # noqa: BLE001 — readiness must classify everything as not-ready
        return {
            "name": name,
            "ok": False,
            "error": str(exc) or exc.__class__.__name__,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        }


async def _build_report() -> dict[str, Any]:
    results = await asyncio.gather(
        *(_run_probe(name, fn) for name, fn in _PROBES.items()),
        return_exceptions=False,
    )
    return {
        "ok": all(r["ok"] for r in results),
        "checked_at": time.time(),
        "probes": {r["name"]: {k: v for k, v in r.items() if k != "name"} for r in results},
    }


async def _cached_report() -> dict[str, Any]:
    now = time.monotonic()
    async with _cache_lock:
        if _cache["report"] is not None and now < _cache["expires_at"]:
            return _cache["report"]
        report = await _build_report()
        _cache["report"] = report
        _cache["expires_at"] = now + _CACHE_TTL_S
        return report


@router.get("/readyz")
async def readyz(response: Response) -> dict[str, Any]:
    """Readiness — every dependency must be reachable. 200 or 503."""

    report = await _cached_report()
    response.status_code = 200 if report["ok"] else 503
    return report


# ---------------------------------------------------------------------------
# /metrics — Sprint 10 Phase A
# ---------------------------------------------------------------------------
@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus exposition format.

    Counters / histograms / gauges live in
    :mod:`app.middleware.metrics` and are populated by
    :class:`PrometheusMetricsMiddleware`. Returns text in the
    standard exposition format for ``prometheus`` to scrape.
    """

    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    body = generate_latest()
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# /csp-report — Sprint 12 Phase B
# ---------------------------------------------------------------------------
from fastapi import Request as _Request

_CSP_LOG = structlog.get_logger("siege_range.csp")


@router.post("/csp-report", include_in_schema=False)
async def csp_report(request: _Request) -> Response:
    """Browser-posted CSP violation reports.

    Logs every report as a structured JSON line so log-shippers
    can dashboard / alert on volume. Body shape varies between
    ``report-uri`` (legacy, application/csp-report) and
    ``report-to`` (newer, application/reports+json) — we capture
    whatever arrived plus the user-agent + IP.

    Returns 204; browsers don't parse the response body.
    """

    import json

    try:
        body_bytes = await request.body()
        try:
            payload = json.loads(body_bytes) if body_bytes else None
        except json.JSONDecodeError:
            payload = {
                "raw": body_bytes.decode("utf-8", errors="replace")[:2000]
            }

        _CSP_LOG.warning(
            "csp.violation",
            payload=payload,
            user_agent=request.headers.get("user-agent", "")[:300],
            client_ip=getattr(request.client, "host", None),
        )
    except Exception as exc:  # noqa: BLE001 — never fail browsers
        _CSP_LOG.error("csp.report_handler_failed", error=str(exc))

    return Response(status_code=204)
