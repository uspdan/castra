"""Unit tests for rate-limit keying and X-Forwarded-For handling.

Regression coverage for two findings:
  * ``client_ip`` must key on the right-most (proxy-appended) XFF token,
    not the spoofable left-most one — otherwise an attacker rotates the
    left-most value to mint unlimited rate-limit buckets.
  * ``flag_rate_limit`` must key on the authenticated user when
    ``request.state.user_id`` is set, falling back to client IP only when
    it is absent.
"""

from __future__ import annotations

import types

import pytest
from starlette.requests import Request

from app.middleware import rate_limit
from app.middleware.rate_limit import client_ip, flag_rate_limit


def _request(*, xff: str | None = None, peer: str | None = "10.9.9.9") -> Request:
    headers = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/challenges/x/submit",
        "query_string": b"",
        "headers": headers,
        "client": (peer, 40000) if peer else None,
    }
    return Request(scope)


@pytest.fixture
def trust_proxy(monkeypatch):
    def _set(trust: bool) -> None:
        monkeypatch.setattr(
            rate_limit,
            "get_settings",
            lambda: types.SimpleNamespace(TRUST_PROXY_HEADERS=trust),
        )

    return _set


def test_client_ip_takes_rightmost_xff_when_proxy_trusted(trust_proxy) -> None:
    trust_proxy(True)
    # Left-most is attacker-controlled; nginx appended the real peer last.
    req = _request(xff="1.2.3.4, 5.6.7.8, 203.0.113.9")
    assert client_ip(req) == "203.0.113.9"


def test_client_ip_ignores_spoofed_leftmost(trust_proxy) -> None:
    trust_proxy(True)
    req = _request(xff="evil-spoof, 198.51.100.7")
    assert client_ip(req) == "198.51.100.7"


def test_client_ip_skips_trailing_empty_tokens(trust_proxy) -> None:
    trust_proxy(True)
    req = _request(xff="203.0.113.9, ")
    assert client_ip(req) == "203.0.113.9"


def test_client_ip_ignores_xff_when_proxy_untrusted(trust_proxy) -> None:
    trust_proxy(False)
    # XFF present but not trusted -> must use the socket peer.
    req = _request(xff="1.2.3.4", peer="10.9.9.9")
    assert client_ip(req) == "10.9.9.9"


def test_client_ip_falls_back_to_peer_without_xff(trust_proxy) -> None:
    trust_proxy(True)
    req = _request(xff=None, peer="10.9.9.9")
    assert client_ip(req) == "10.9.9.9"


async def test_flag_rate_limit_keys_on_user_when_present(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_check(key, limit, window, request) -> None:
        captured["key"] = key
        captured["limit"] = limit

    monkeypatch.setattr(rate_limit, "_check_rate_limit", _fake_check)
    req = _request(peer="10.9.9.9")
    req.state.user_id = 4242

    await flag_rate_limit(req)

    assert captured["key"] == "siege:ratelimit:flag:4242"
    assert captured["limit"] == 10


async def test_flag_rate_limit_falls_back_to_ip_without_user(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_check(key, limit, window, request) -> None:
        captured["key"] = key

    monkeypatch.setattr(rate_limit, "_check_rate_limit", _fake_check)
    monkeypatch.setattr(
        rate_limit,
        "get_settings",
        lambda: types.SimpleNamespace(TRUST_PROXY_HEADERS=False),
    )
    # No request.state.user_id -> key on the socket peer.
    req = _request(peer="10.9.9.9")

    await flag_rate_limit(req)

    assert captured["key"] == "siege:ratelimit:flag:10.9.9.9"
