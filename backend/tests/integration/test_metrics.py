"""Sprint 10 Phase A — Prometheus /metrics + middleware."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


class TestMetricsEndpoint:
    async def test_metrics_returns_exposition_format(self, client):
        # Hit any endpoint first so counters are populated.
        await client.get("/health")

        r = await client.get("/metrics")
        assert r.status_code == 200
        # Prometheus exposition format starts with '# HELP' / '# TYPE'
        # comments. The body is text, not JSON.
        body = r.text
        assert "# HELP http_requests_total" in body
        assert "# TYPE http_requests_total counter" in body
        # The /health request we just made is a recorded line.
        assert 'http_requests_total{method="GET",route="/health"' in body

    async def test_404_paths_recorded(self, client):
        await client.get("/no-such-endpoint")
        r = await client.get("/metrics")
        assert r.status_code == 200
        # 404 traffic shows up as status="404".
        assert 'status="404"' in r.text

    async def test_metrics_excludes_self(self, client):
        # Hit /metrics twice; the count should NOT include /metrics
        # itself (the middleware skip in dispatch).
        await client.get("/metrics")
        await client.get("/metrics")
        r = await client.get("/metrics")
        assert r.status_code == 200
        # No metrics line for /metrics route.
        for line in r.text.splitlines():
            if line.startswith("http_requests_total{") and 'route="/metrics"' in line:
                pytest.fail(f"/metrics should not record itself: {line}")

    async def test_latency_histogram_present(self, client):
        await client.get("/health")
        r = await client.get("/metrics")
        body = r.text
        assert "# TYPE http_request_duration_seconds histogram" in body
        # Histograms emit _bucket / _count / _sum lines.
        assert "http_request_duration_seconds_bucket" in body
        assert "http_request_duration_seconds_count" in body
