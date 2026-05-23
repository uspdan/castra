"""Unit tests for :mod:`app.services.webhook_ssrf` (audit finding R4).

Each ``test_refuses_*`` covers a CIDR / scheme / shape that the
guard must block. ``test_accepts_*`` cases pin the happy path so a
future tightening doesn't silently turn the guard into a deny-all.
DNS resolution is monkey-patched per-test — production callers hit
real getaddrinfo; we stub it so the suite is hermetic + fast.
"""

from __future__ import annotations

import socket

import pytest

from app.services.webhook_ssrf import UnsafeUrlError, assert_url_safe


# ---------------------------------------------------------------------------
# Helper: stub getaddrinfo to return whatever the test wants.
# ---------------------------------------------------------------------------
def _stub_resolve(monkeypatch, addr: str) -> None:
    """Force ``socket.getaddrinfo`` to return one record for any host."""

    family = socket.AF_INET6 if ":" in addr else socket.AF_INET

    def fake(host, port, *args, **kwargs):
        return [(family, socket.SOCK_STREAM, 6, "", (addr, port or 0))]

    monkeypatch.setattr(
        "app.services.webhook_ssrf.socket.getaddrinfo", fake
    )


def _stub_resolve_multi(monkeypatch, addrs: list[str]) -> None:
    """Force getaddrinfo to return many records (covers public-A /
    private-AAAA mixed-resolve attacks)."""

    records = []
    for a in addrs:
        family = socket.AF_INET6 if ":" in a else socket.AF_INET
        records.append((family, socket.SOCK_STREAM, 6, "", (a, 0)))

    def fake(host, port, *args, **kwargs):
        return records

    monkeypatch.setattr(
        "app.services.webhook_ssrf.socket.getaddrinfo", fake
    )


# ---------------------------------------------------------------------------
# Scheme + shape
# ---------------------------------------------------------------------------
class TestScheme:
    def test_refuses_empty(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("")

    def test_refuses_non_http(self):
        for url in (
            "file:///etc/passwd",
            "ftp://example.com/foo",
            "gopher://example.com/foo",
            "ssh://example.com",
            "ldap://internal.corp/o=foo",
        ):
            with pytest.raises(UnsafeUrlError):
                assert_url_safe(url)

    def test_refuses_missing_host(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http:///path-only")


# ---------------------------------------------------------------------------
# Literal-IP path — no DNS round-trip
# ---------------------------------------------------------------------------
class TestLiteralIp:
    def test_refuses_loopback_v4(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://127.0.0.1:8080/x")

    def test_refuses_loopback_v6(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://[::1]:8080/x")

    def test_refuses_link_local_v4(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://169.254.169.254/latest/meta-data/")

    def test_refuses_private_v4(self):
        for addr in ("10.0.0.1", "172.16.0.1", "192.168.1.1"):
            with pytest.raises(UnsafeUrlError):
                assert_url_safe(f"http://{addr}/x")

    def test_refuses_multicast(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://224.0.0.1/x")

    def test_refuses_reserved(self):
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("http://255.255.255.255/x")

    def test_accepts_public_v4(self):
        # No DNS path on literal IP — guard validates the literal
        # directly without resolving. 1.1.1.1 is Cloudflare's public
        # resolver; documentation ranges (203.0.113.0/24,
        # 2001:db8::/32) carry ``is_reserved=True`` and are
        # correctly refused.
        assert_url_safe("http://1.1.1.1/x")

    def test_accepts_public_v6(self):
        assert_url_safe("http://[2606:4700:4700::1111]/x")


# ---------------------------------------------------------------------------
# Hostname path — DNS resolution stubbed
# ---------------------------------------------------------------------------
class TestHostnameResolves:
    def test_accepts_public_hostname(self, monkeypatch):
        _stub_resolve(monkeypatch, "1.1.1.1")
        assert_url_safe("https://hooks.example.com/path")

    def test_refuses_hostname_resolving_to_loopback(self, monkeypatch):
        _stub_resolve(monkeypatch, "127.0.0.1")
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("https://attacker-rebind.example/x")

    def test_refuses_hostname_resolving_to_private(self, monkeypatch):
        _stub_resolve(monkeypatch, "10.0.0.5")
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("https://internal-service.local/x")

    def test_refuses_hostname_resolving_to_imds(self, monkeypatch):
        _stub_resolve(monkeypatch, "169.254.169.254")
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("https://aws-pivot.example/latest/meta-data/")

    def test_refuses_hostname_with_mixed_public_and_private(self, monkeypatch):
        # First-record-public / second-record-private split — guard
        # must refuse on the first private hit, not stop at the
        # first record.
        _stub_resolve_multi(monkeypatch, ["1.1.1.1", "10.0.0.5"])
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("https://dual-resolve.example/x")

    def test_refuses_when_dns_fails(self, monkeypatch):
        def boom(*args, **kwargs):
            raise socket.gaierror("no such host")

        monkeypatch.setattr(
            "app.services.webhook_ssrf.socket.getaddrinfo", boom
        )
        with pytest.raises(UnsafeUrlError):
            assert_url_safe("https://nx.example/x")
