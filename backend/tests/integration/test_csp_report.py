"""Sprint 12 Phase B — CSP violation report endpoint."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.integration


class TestCspReport:
    async def test_accepts_browser_report_shape(self, client):
        # Sample report-uri payload shape browsers send.
        payload = {
            "csp-report": {
                "document-uri": "https://example.com/page",
                "violated-directive": "script-src",
                "blocked-uri": "inline",
                "source-file": "https://example.com/page",
                "line-number": 42,
            }
        }
        r = await client.post("/csp-report", json=payload)
        assert r.status_code == 204
        # 204 means no body.
        assert not r.content

    async def test_handles_empty_body(self, client):
        r = await client.post(
            "/csp-report", content=b"", headers={"Content-Type": "application/json"}
        )
        assert r.status_code == 204

    async def test_handles_malformed_json(self, client):
        r = await client.post(
            "/csp-report",
            content=b"not-json{",
            headers={"Content-Type": "application/json"},
        )
        # Still returns 204 — browsers can't recover from a 4xx.
        assert r.status_code == 204

    async def test_csp_header_includes_report_uri(self, client):
        r = await client.get("/health")
        csp = r.headers.get("Content-REDACTED-Policy", "")
        assert "report-uri /csp-report" in csp
