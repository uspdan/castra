"""OpenTelemetry tracing setup.

Sprint 11 Phase C. Implements CLAUDE.md §14.3 — distributed
tracing across inbound HTTP, SQLAlchemy queries, and outbound
``httpx`` calls.

Setup is **opt-in** via the ``OTEL_EXPORTER_OTLP_ENDPOINT`` env
var. If unset, :func:`configure_tracing` is a no-op — production
deployments without an OTLP collector pay no overhead. When set,
the function:

1. Builds a ``TracerProvider`` with ``service.name=siege-range``.
2. Installs an OTLP HTTP exporter pointing at the endpoint.
3. Instruments the FastAPI app for inbound spans.
4. Instruments the SQLAlchemy engine for DB spans.
5. Instruments httpx for outbound spans.

Spans propagate ``traceparent`` per W3C Trace Context, so the
platform participates in distributed traces emitted by upstream
services (orchestrator, etc.).

Sampling: 1-10% baseline in production via the OTel SDK's
``OTEL_TRACES_SAMPLER`` env var (e.g. ``parentbased_traceidratio``
with ``OTEL_TRACES_SAMPLER_ARG=0.05``). Errors are sampled at
100% via the ``always_on`` sampler in dev / staging.
"""

from __future__ import annotations

import os
from typing import Any

import structlog


logger = structlog.get_logger()


def is_enabled() -> bool:
    """Return True iff OTel tracing should be configured.

    Gate is the presence of the standard OTel endpoint env var so
    operators don't need a platform-specific knob.
    """

    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"))


def configure_tracing(app: Any, engine: Any) -> bool:
    """Wire up OpenTelemetry instrumentation.

    ``app`` is the FastAPI instance; ``engine`` is the SQLAlchemy
    async engine. Returns True if tracing was configured, False
    if disabled (the no-op path).

    Best-effort: any import / configuration failure is logged at
    WARN and degrades to disabled — the platform must boot
    cleanly even if the OTel stack is misconfigured.
    """

    if not is_enabled():
        logger.info("tracing.disabled", reason="OTEL_EXPORTER_OTLP_ENDPOINT unset")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import (
            SQLAlchemyInstrumentor,
        )
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        logger.warning(
            "tracing.import_failed",
            error=f"{type(exc).__name__}: {exc}",
        )
        return False

    try:
        provider = TracerProvider(
            resource=Resource.create(
                {SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "siege-range")}
            )
        )
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter())
        )
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)

        # SQLAlchemy auto-instrument needs the SYNC core engine —
        # not the async wrapper. Pull ``.sync_engine`` if present;
        # for a plain sync engine, use the engine itself.
        sync_engine = getattr(engine, "sync_engine", engine)
        SQLAlchemyInstrumentor().instrument(engine=sync_engine)

        HTTPXClientInstrumentor().instrument()

        logger.info(
            "tracing.enabled",
            endpoint=os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"],
        )
        return True
    except Exception as exc:  # noqa: BLE001 — never crash boot on observability
        logger.warning(
            "tracing.configure_failed",
            error=f"{type(exc).__name__}: {exc}",
        )
        return False


__all__ = ["configure_tracing", "is_enabled"]
