"""Sprint 11 Phase C — OpenTelemetry tracing setup tests.

Tracing is opt-in via OTEL_EXPORTER_OTLP_ENDPOINT. The tests here
verify the boot-time gate logic without actually shipping spans
(which would require a running OTLP collector).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.observability.tracing import configure_tracing, is_enabled


# ---------------------------------------------------------------------------
# is_enabled
# ---------------------------------------------------------------------------
class TestIsEnabled:
    def test_disabled_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        assert is_enabled() is False

    def test_enabled_when_env_set(self, monkeypatch):
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318"
        )
        assert is_enabled() is True


# ---------------------------------------------------------------------------
# configure_tracing
# ---------------------------------------------------------------------------
class TestConfigureTracing:
    def test_no_op_when_disabled(self, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        result = configure_tracing(MagicMock(), MagicMock())
        assert result is False

    def test_swallows_configure_errors(self, monkeypatch):
        """A bad OTLP endpoint must NOT crash boot."""

        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://does-not-exist:4318"
        )
        # Pass non-instrumentable mocks so the FastAPI instrumentor
        # raises; the function should catch and return False.
        broken_app = object()  # not a FastAPI app
        broken_engine = object()  # not a SQLAlchemy engine
        result = configure_tracing(broken_app, broken_engine)
        assert result is False

    def test_returns_true_on_success(self, monkeypatch):
        from fastapi import FastAPI
        from sqlalchemy import create_engine

        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318"
        )
        app = FastAPI()
        engine = create_engine("sqlite:///:memory:")
        try:
            result = configure_tracing(app, engine)
            assert result is True
        finally:
            # Tear down OTel global state so subsequent tests aren't
            # contaminated by a partial install.
            try:
                from opentelemetry.instrumentation.fastapi import (
                    FastAPIInstrumentor,
                )
                from opentelemetry.instrumentation.httpx import (
                    HTTPXClientInstrumentor,
                )
                from opentelemetry.instrumentation.sqlalchemy import (
                    SQLAlchemyInstrumentor,
                )

                FastAPIInstrumentor.uninstrument_app(app)
                SQLAlchemyInstrumentor().uninstrument()
                HTTPXClientInstrumentor().uninstrument()
            except Exception:  # noqa: BLE001
                pass
