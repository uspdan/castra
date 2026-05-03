"""Integration tests for the v1 webhook admin surface."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import UserRole, WebhookSubscription


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# auth gates
# ---------------------------------------------------------------------------
class TestAuthGate:
    async def test_unauthenticated_rejected_for_create(self, client):
        r = await client.post(
            "/api/v1/webhooks",
            json={
                "name": "x",
                "target_url": "https://example.invalid/h",
                "events": ["challenge.flag.submit.pass"],
            },
        )
        assert r.status_code in (401, 403)

    async def test_non_admin_rejected_for_create(
        self, client, user_factory, auth_headers
    ):
        operator = await user_factory()  # default role: operator
        r = await client.post(
            "/api/v1/webhooks",
            headers=auth_headers(operator),
            json={
                "name": "x",
                "target_url": "https://example.invalid/h",
                "events": ["challenge.flag.submit.pass"],
            },
        )
        assert r.status_code == 403

    async def test_non_admin_rejected_for_list(
        self, client, user_factory, auth_headers
    ):
        operator = await user_factory()
        r = await client.get(
            "/api/v1/webhooks", headers=auth_headers(operator)
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
class TestCreate:
    async def test_admin_create_returns_secret_once(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/webhooks",
            headers=auth_headers(admin),
            json={
                "name": "soc-channel",
                "target_url": "https://hooks.example.invalid/x",
                "events": ["challenge.flag.submit.pass"],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        # Locked shape includes secret on create.
        expected_keys = {
            "id", "name", "target_url", "events", "is_active",
            "created_at", "last_delivery_at", "last_status",
            "last_error", "secret",
        }
        assert set(body.keys()) == expected_keys
        assert body["name"] == "soc-channel"
        assert body["events"] == ["challenge.flag.submit.pass"]
        assert body["is_active"] is True
        assert len(body["secret"]) >= 32

        # Row exists with the secret persisted.
        rows = (
            await db_session.execute(select(WebhookSubscription))
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].secret == body["secret"]

    async def test_unknown_event_rejected(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/webhooks",
            headers=auth_headers(admin),
            json={
                "name": "x",
                "target_url": "https://example.invalid/h",
                "events": ["bogus.event"],
            },
        )
        assert r.status_code == 422

    async def test_wildcard_must_be_alone(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/webhooks",
            headers=auth_headers(admin),
            json={
                "name": "x",
                "target_url": "https://example.invalid/h",
                "events": ["*", "challenge.flag.submit.pass"],
            },
        )
        assert r.status_code == 422

    async def test_invalid_url_rejected(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/webhooks",
            headers=auth_headers(admin),
            json={
                "name": "x",
                "target_url": "not-a-url",
                "events": ["challenge.flag.submit.pass"],
            },
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# list / get / delete
# ---------------------------------------------------------------------------
class TestListGetDelete:
    async def _create(self, client, admin, auth_headers, name="test"):
        r = await client.post(
            "/api/v1/webhooks",
            headers=auth_headers(admin),
            json={
                "name": name,
                "target_url": "https://example.invalid/h",
                "events": ["challenge.flag.submit.pass"],
            },
        )
        assert r.status_code == 201
        return r.json()

    async def test_list_omits_secret(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        await self._create(client, admin, auth_headers, name="hook-a")
        await self._create(client, admin, auth_headers, name="hook-b")
        r = await client.get(
            "/api/v1/webhooks", headers=auth_headers(admin)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        for item in body["items"]:
            assert "secret" not in item
            assert set(item.keys()) == {
                "id", "name", "target_url", "events", "is_active",
                "created_at", "last_delivery_at", "last_status",
                "last_error",
            }

    async def test_get_returns_single_record(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        created = await self._create(client, admin, auth_headers)
        r = await client.get(
            f"/api/v1/webhooks/{created['id']}",
            headers=auth_headers(admin),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == created["id"]
        assert "secret" not in body

    async def test_get_404_for_missing(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.get(
            "/api/v1/webhooks/99999", headers=auth_headers(admin)
        )
        assert r.status_code == 404

    async def test_delete_removes_row(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin)
        created = await self._create(client, admin, auth_headers)
        r = await client.delete(
            f"/api/v1/webhooks/{created['id']}",
            headers=auth_headers(admin),
        )
        assert r.status_code == 204
        rows = (
            await db_session.execute(select(WebhookSubscription))
        ).scalars().all()
        assert rows == []

    async def test_delete_404_for_missing(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.delete(
            "/api/v1/webhooks/99999", headers=auth_headers(admin)
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# end-to-end: a flag submission with an active subscription writes
# the dispatch outcome to ``last_status`` (target is unreachable, so
# we expect a network_error there).
# ---------------------------------------------------------------------------
class TestE2EDispatchOnSubmit:
    async def test_submission_pings_subscription(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        admin = await user_factory(role=UserRole.admin, username="admin-e2e")
        operator = await user_factory(username="op-e2e")
        # Seed a subscription pointing at an unroutable host so the
        # dispatch fails fast with a network error rather than
        # actually trying to reach the public internet.
        await client.post(
            "/api/v1/webhooks",
            headers=auth_headers(admin),
            json={
                "name": "e2e",
                "target_url": "http://127.0.0.1:1/never-listens",
                "events": ["*"],
            },
        )
        await challenge_factory(slug="v1-wh-e2e", flag="CTF{REDACTED}")
        r = await client.post(
            "/api/v1/challenges/v1-wh-e2e/submit",
            headers=auth_headers(operator),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200
        sub = (
            await db_session.execute(select(WebhookSubscription))
        ).scalars().first()
        # last_status reflects the dispatch attempt: either
        # network_error / timeout / internal_error depending on the
        # exact failure mode the runner sees, but it must be
        # populated and must not be a 2xx success.
        assert sub.last_status is not None
        assert not sub.last_status.startswith("ok_")
        assert sub.last_delivery_at is not None
