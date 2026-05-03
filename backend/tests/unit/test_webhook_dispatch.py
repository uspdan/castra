"""Unit tests for the webhook dispatch service.

Covers the pure helpers (signature derivation, secret generation)
plus the dispatch-with-mocked-httpx happy/error paths. The
end-to-end "audit pass triggers fan-out" path is covered in the
integration suite where we have a real DB.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import pytest

from app.services.webhook_dispatch import (
    deliver_event,
    generate_subscription_secret,
    sign_body,
)


pytestmark = pytest.mark.integration  # uses db_session


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
class TestPureHelpers:
    def test_secret_is_64_hex_chars(self):
        s = generate_subscription_secret()
        assert len(s) == 64
        int(s, 16)  # raises if not hex

    def test_two_secrets_differ(self):
        # Astronomically unlikely to collide; if they do, our RNG is broken.
        assert generate_subscription_secret() != generate_subscription_secret()

    def test_sign_body_is_deterministic(self):
        secret = "0" * 64
        body = b'{"event":"test"}'
        a = sign_body(secret, body)
        b = sign_body(secret, body)
        assert a == b

    def test_sign_body_format(self):
        secret = "0" * 64
        body = b'{"event":"test"}'
        sig = sign_body(secret, body)
        assert sig.startswith("sha256=")
        # Extracted hex equals an independently computed HMAC.
        expected = hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        assert sig == f"sha256={expected}"

    def test_sign_body_different_secret_different_sig(self):
        body = b'{"event":"test"}'
        a = sign_body("a" * 64, body)
        b = sign_body("b" * 64, body)
        assert a != b


# ---------------------------------------------------------------------------
# deliver_event (mocked httpx)
# ---------------------------------------------------------------------------
@dataclass
class _StubResponse:
    status_code: int


class _StubClient:
    """Minimal async-context-manager mock for ``httpx.AsyncClient``."""

    def __init__(self, *, status_code: int = 200, raises: Exception | None = None):
        self._status = status_code
        self._raises = raises
        self.calls: list[tuple[str, bytes, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url: str, *, content: bytes, headers: dict):
        self.calls.append((url, content, dict(headers)))
        if self._raises is not None:
            raise self._raises
        return _StubResponse(status_code=self._status)


async def _seed_subscription(
    db_session, *, owner_id: int, events: list[str], is_active: bool = True
):
    from app.models import WebhookSubscription

    sub = WebhookSubscription(
        owner_user_id=owner_id,
        name="test-sub",
        target_url="https://example.invalid/hook",
        secret="s" * 64,
        events=events,
        is_active=is_active,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


class TestDeliverEvent:
    async def test_no_subscriptions_is_noop(self, db_session):
        # No rows seeded; deliver_event should return cleanly.
        await deliver_event(
            db=db_session,
            event_type="challenge.flag.submit.pass",
            payload={"challenge_slug": "x"},
        )
        # Nothing to assert — the function returns when there are
        # no matching subscriptions.

    async def test_matching_subscription_called_with_signed_body(
        self, db_session, user_factory
    ):
        admin = await user_factory()
        sub = await _seed_subscription(
            db_session,
            owner_id=admin.id,
            events=["challenge.flag.submit.pass"],
        )
        stubs = []

        def factory():
            stub = _StubClient(status_code=200)
            stubs.append(stub)
            return stub

        await deliver_event(
            db=db_session,
            event_type="challenge.flag.submit.pass",
            payload={"challenge_slug": "blue-001", "points_awarded": 100,
                     "is_first_blood": True},
            http_client_factory=factory,
        )
        assert len(stubs) == 1
        url, body, headers = stubs[0].calls[0]
        assert url == sub.target_url
        # Signature header is well-formed and matches secret + body.
        assert headers["X-Siege-Signature"] == sign_body(sub.secret, body)
        assert headers["X-Siege-Event"] == "challenge.flag.submit.pass"
        assert "X-Siege-Delivery-Id" in headers
        # Canonical envelope shape.
        envelope = json.loads(body)
        assert envelope["event_type"] == "challenge.flag.submit.pass"
        assert envelope["payload"]["challenge_slug"] == "blue-001"

        await db_session.refresh(sub)
        assert sub.last_status == "ok_200"
        assert sub.last_error is None
        assert sub.last_delivery_at is not None

    async def test_inactive_subscription_skipped(self, db_session, user_factory):
        admin = await user_factory()
        sub = await _seed_subscription(
            db_session,
            owner_id=admin.id,
            events=["challenge.flag.submit.pass"],
            is_active=False,
        )
        stubs: list[_StubClient] = []

        def factory():
            stub = _StubClient(status_code=200)
            stubs.append(stub)
            return stub

        await deliver_event(
            db=db_session,
            event_type="challenge.flag.submit.pass",
            payload={"challenge_slug": "x"},
            http_client_factory=factory,
        )
        assert stubs == []
        await db_session.refresh(sub)
        assert sub.last_status is None

    async def test_event_filter_skips_unmatched(self, db_session, user_factory):
        admin = await user_factory()
        sub = await _seed_subscription(
            db_session, owner_id=admin.id, events=["instance.launch"],
        )
        stubs: list[_StubClient] = []

        def factory():
            stub = _StubClient()
            stubs.append(stub)
            return stub

        await deliver_event(
            db=db_session,
            event_type="challenge.flag.submit.pass",
            payload={"challenge_slug": "x"},
            http_client_factory=factory,
        )
        assert stubs == []

    async def test_wildcard_subscription_matches_anything(
        self, db_session, user_factory
    ):
        admin = await user_factory()
        await _seed_subscription(
            db_session, owner_id=admin.id, events=["*"],
        )
        stubs: list[_StubClient] = []

        def factory():
            stub = _StubClient()
            stubs.append(stub)
            return stub

        await deliver_event(
            db=db_session,
            event_type="instance.expired",
            payload={},
            http_client_factory=factory,
        )
        assert len(stubs) == 1

    async def test_5xx_response_persists_error(self, db_session, user_factory):
        admin = await user_factory()
        sub = await _seed_subscription(
            db_session, owner_id=admin.id, events=["*"],
        )

        def factory():
            return _StubClient(status_code=503)

        await deliver_event(
            db=db_session,
            event_type="auth.login.success",
            payload={"username": "x"},
            http_client_factory=factory,
        )
        await db_session.refresh(sub)
        assert sub.last_status == "http_503"
        assert sub.last_error and "503" in sub.last_error

    async def test_network_error_persisted(self, db_session, user_factory):
        admin = await user_factory()
        sub = await _seed_subscription(
            db_session, owner_id=admin.id, events=["*"],
        )

        def factory():
            return _StubClient(raises=httpx.ConnectError("boom"))

        await deliver_event(
            db=db_session,
            event_type="auth.login.success",
            payload={"username": "x"},
            http_client_factory=factory,
        )
        await db_session.refresh(sub)
        assert sub.last_status == "network_error"
        assert "ConnectError" in (sub.last_error or "")

    async def test_timeout_persisted(self, db_session, user_factory):
        admin = await user_factory()
        sub = await _seed_subscription(
            db_session, owner_id=admin.id, events=["*"],
        )

        def factory():
            return _StubClient(raises=httpx.TimeoutException("slow"))

        await deliver_event(
            db=db_session,
            event_type="auth.login.success",
            payload={"username": "x"},
            http_client_factory=factory,
        )
        await db_session.refresh(sub)
        assert sub.last_status == "timeout"

    async def test_multiple_subscriptions_dispatch_concurrently(
        self, db_session, user_factory
    ):
        admin = await user_factory()
        for i in range(3):
            await _seed_subscription(
                db_session, owner_id=admin.id, events=["*"],
            )
        stubs: list[_StubClient] = []

        def factory():
            stub = _StubClient(status_code=200)
            stubs.append(stub)
            return stub

        await deliver_event(
            db=db_session,
            event_type="instance.launch",
            payload={},
            http_client_factory=factory,
        )
        assert len(stubs) == 3
