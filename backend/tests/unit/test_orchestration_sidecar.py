"""Tests for the per-instance egress-proxy sidecar lifecycle."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.orchestration import sidecar


# ---------------------------------------------------------------------------
# render_sidecar_filter
# ---------------------------------------------------------------------------
class TestRenderSidecarFilter:
    def test_empty_allowlist_yields_header_only(self):
        out = sidecar.render_sidecar_filter([])
        assert "rule_count: 0" in out
        # No regex lines.
        assert all(not line.startswith("^") for line in out.splitlines())

    def test_single_fqdn(self):
        out = sidecar.render_sidecar_filter(["api.example.com"])
        assert "^api\\.example\\.com$" in out
        assert "rule_count: 1" in out

    def test_wildcard_subdomain(self):
        out = sidecar.render_sidecar_filter(["*.example.com"])
        assert "^.+\\.example\\.com$" in out

    def test_dedupes(self):
        out = sidecar.render_sidecar_filter(
            ["api.example.com", "api.example.com", " API.example.com "]
        )
        # Only one rule, regardless of casing/whitespace.
        rule_lines = [
            l for l in out.splitlines() if l.startswith("^")
        ]
        assert len(rule_lines) == 1

    def test_drops_empty_entries(self):
        out = sidecar.render_sidecar_filter(["", "  ", "good.example.com"])
        rules = [l for l in out.splitlines() if l.startswith("^")]
        assert len(rules) == 1
        assert rules[0] == "^good\\.example\\.com$"


# ---------------------------------------------------------------------------
# launch_sidecar
# ---------------------------------------------------------------------------
class _FakeContainer:
    def __init__(self):
        self.id = "sidecar-fake-id"


class _FakeContainersAPI:
    def __init__(self):
        self.last_kwargs: dict | None = None

    def run(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeContainer()


class _FakeClient:
    def __init__(self):
        self.containers = _FakeContainersAPI()


class TestLaunchSidecar:
    def test_passes_allowlist_via_env(self):
        client = _FakeClient()
        out = sidecar.launch_sidecar(
            client,
            network_name="siege-ch-1-foo-abcd",
            allowlist=["api.example.com"],
            instance_label="1-foo",
        )
        kwargs = client.containers.last_kwargs
        assert kwargs is not None
        env = kwargs["environment"]
        assert "EGRESS_ALLOWLIST" in env
        assert "^api\\.example\\.com$" in env["EGRESS_ALLOWLIST"]
        # Hardening: caps dropped, no-new-privs, read-only fs, mem cap.
        assert kwargs["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in kwargs["security_opt"]
        assert kwargs["read_only"] is True
        assert kwargs["mem_limit"] == "64m"
        assert kwargs["network"] == "siege-ch-1-foo-abcd"
        assert out.container_id == "sidecar-fake-id"
        assert "siege-egress-sidecar" in out.container_name

    def test_label_includes_instance_marker(self):
        client = _FakeClient()
        sidecar.launch_sidecar(
            client,
            network_name="net",
            allowlist=[],
            instance_label="42-some-slug",
        )
        labels = client.containers.last_kwargs["labels"]
        assert labels["siege.role"] == "egress-sidecar"
        assert labels["siege.instance"] == "42-some-slug"


# ---------------------------------------------------------------------------
# teardown_sidecar
# ---------------------------------------------------------------------------
class TestTeardownSidecar:
    def test_no_op_on_empty_id(self):
        client = MagicMock()
        assert sidecar.teardown_sidecar(client, None) is False
        assert sidecar.teardown_sidecar(client, "") is False

    def test_stops_and_removes(self):
        client = MagicMock()
        container = MagicMock()
        client.containers.get.return_value = container

        ok = sidecar.teardown_sidecar(client, "ctr-123")
        assert ok is True
        container.stop.assert_called_once()
        container.remove.assert_called_once_with(force=True)

    def test_swallows_failures(self):
        client = MagicMock()
        client.containers.get.side_effect = RuntimeError("docker down")
        # Best-effort: returns False, never raises.
        assert sidecar.teardown_sidecar(client, "ctr-123") is False
