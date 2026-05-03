"""Integration tests for v1 webhook deliveries history + replay (slice 6)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import UserRole, WebhookDelivery, WebhookSubscription


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _seed_subscription(
    db_session, *, owner_id: int, events: list[str] | None = None
) -> WebhookSubscription:
    sub = WebhookSubscription(
        owner_user_id=owner_id,
        name="hist-sub",
        target_url="http://127.0.0.1:1/never-listens",
        secret="s" * 64,
        events=events or ["*"],
        is_active=True,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


async def _seed_delivery(
    db_session,
    *,
    subscription_id: int,
    delivery_id: str = "d1",
    status: str = "ok_200",
    attempt: int = 1,
) -> WebhookDelivery:
    row = WebhookDelivery(
        subscription_id=subscription_id,
        event_type="challenge.flag.submit.pass",
        delivery_id=delivery_id,
        payload={"challenge_slug": "x"},
        attempt=attempt,
        status=status,
        http_status=200 if status.startswith("ok_") else None,
        response_ms=12,
        error=None if status.startswith("ok_") else "boom",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# GET /api/v1/webhooks/{id}/deliveries
# ---------------------------------------------------------------------------
class TestListDeliveries:
    async def test_unauth_rejected(self, client):
        r = await client.get("/api/v1/webhooks/1/deliveries")
        assert r.status_code in (401, 403)

    async def test_non_admin_rejected(self, client, user_factory, auth_headers):
        operator = await user_factory()
        r = await client.get(
            "/api/v1/webhooks/1/deliveries", headers=auth_headers(operator)
        )
        assert r.status_code == 403

    async def test_404_for_missing_subscription(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.get(
            "/api/v1/webhooks/99999/deliveries", headers=auth_headers(admin)
        )
        assert r.status_code == 404

    async def test_empty_list(self, client, user_factory, auth_headers, db_session):
        admin = await user_factory(role=UserRole.admin)
        sub = await _seed_subscription(db_session, owner_id=admin.id)
        r = await client.get(
            f"/api/v1/webhooks/{sub.id}/deliveries", headers=auth_headers(admin)
        )
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "items": [],
            "total": 0,
            "page": 1,
            "per_page": 50,
        }

    async def test_returns_rows_ordered_desc(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin)
        sub = await _seed_subscription(db_session, owner_id=admin.id)
        await _seed_delivery(db_session, subscription_id=sub.id, delivery_id="d1")
        await _seed_delivery(db_session, subscription_id=sub.id, delivery_id="d2")
        await _seed_delivery(
            db_session, subscription_id=sub.id, delivery_id="d3",
            status="http_503",
        )
        r = await client.get(
            f"/api/v1/webhooks/{sub.id}/deliveries",
            headers=auth_headers(admin),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        delivery_ids = [item["delivery_id"] for item in body["items"]]
        # Most recent insert first.
        assert delivery_ids == ["d3", "d2", "d1"]
        # Per-row shape locked.
        for item in body["items"]:
            assert set(item.keys()) == {
                "id", "subscription_id", "event_type", "delivery_id",
                "payload", "attempt", "status", "http_status",
                "response_ms", "error", "created_at",
            }

    async def test_pagination(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin)
        sub = await _seed_subscription(db_session, owner_id=admin.id)
        for i in range(5):
            await _seed_delivery(
                db_session, subscription_id=sub.id, delivery_id=f"d{i}"
            )
        r = await client.get(
            f"/api/v1/webhooks/{sub.id}/deliveries?per_page=2&page=2",
            headers=auth_headers(admin),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 2
        assert len(body["items"]) == 2


# ---------------------------------------------------------------------------
# POST /api/v1/webhooks/{id}/deliveries/{delivery_id}/replay
# ---------------------------------------------------------------------------
class TestReplayDelivery:
    async def test_unauth_rejected(self, client):
        r = await client.post("/api/v1/webhooks/1/deliveries/d1/replay")
        assert r.status_code in (401, 403)

    async def test_non_admin_rejected(self, client, user_factory, auth_headers):
        operator = await user_factory()
        r = await client.post(
            "/api/v1/webhooks/1/deliveries/d1/replay",
            headers=auth_headers(operator),
        )
        assert r.status_code == 403

    async def test_404_for_missing_subscription(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/webhooks/99999/deliveries/d1/replay",
            headers=auth_headers(admin),
        )
        assert r.status_code == 404

    async def test_404_for_missing_delivery(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin)
        sub = await _seed_subscription(db_session, owner_id=admin.id)
        r = await client.post(
            f"/api/v1/webhooks/{sub.id}/deliveries/missing/replay",
            headers=auth_headers(admin),
        )
        assert r.status_code == 404

    async def test_replay_inserts_new_attempt_row(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin)
        sub = await _seed_subscription(db_session, owner_id=admin.id)
        await _seed_delivery(
            db_session,
            subscription_id=sub.id,
            delivery_id="dxyz",
            status="http_503",
            attempt=1,
        )
        r = await client.post(
            f"/api/v1/webhooks/{sub.id}/deliveries/dxyz/replay",
            headers=auth_headers(admin),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["delivery_id"] == "dxyz"
        # New attempt number = max(prior) + 1.
        assert body["attempt"] == 2
        # Replay against an unroutable host produces a non-2xx
        # outcome; status reflects that.
        assert not body["status"].startswith("ok_")

        rows = (
            await db_session.execute(
                select(WebhookDelivery).where(
                    WebhookDelivery.delivery_id == "dxyz",
                    WebhookDelivery.subscription_id == sub.id,
                )
                .order_by(WebhookDelivery.attempt.asc())
            )
        ).scalars().all()
        assert [r.attempt for r in rows] == [1, 2]
        assert rows[0].status == "http_503"
        # Subscription's last_status reflects the replay outcome.
        await db_session.refresh(sub)
        assert sub.last_status == body["status"]

    async def test_replay_preserves_payload(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin)
        sub = await _seed_subscription(db_session, owner_id=admin.id)
        delivery = WebhookDelivery(
            subscription_id=sub.id,
            event_type="challenge.flag.submit.pass",
            delivery_id="dpayload",
            payload={"challenge_slug": "x", "points_awarded": 100},
            attempt=1,
            status="http_503",
            http_status=503,
            response_ms=42,
            error="boom",
        )
        db_session.add(delivery)
        await db_session.commit()

        r = await client.post(
            f"/api/v1/webhooks/{sub.id}/deliveries/dpayload/replay",
            headers=auth_headers(admin),
        )
        assert r.status_code == 201
        body = r.json()
        assert body["payload"] == {
            "challenge_slug": "x",
            "points_awarded": 100,
        }
        assert body["event_type"] == "challenge.flag.submit.pass"


# ---------------------------------------------------------------------------
# End-to-end: a flag submission writes one delivery row per
# matching subscription, alongside the existing last_status update.
# ---------------------------------------------------------------------------
class TestE2EDeliveryRow:
    async def test_submit_writes_delivery_row(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        admin = await user_factory(role=UserRole.admin, username="d-admin")
        operator = await user_factory(username="d-op")
        await _seed_subscription(db_session, owner_id=admin.id)
        await challenge_factory(slug="v1-deliv-e2e", flag="CTF{REDACTED}")

        r = await client.post(
            "/api/v1/challenges/v1-deliv-e2e/submit",
            headers=auth_headers(operator),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200

        rows = (
            await db_session.execute(select(WebhookDelivery))
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].event_type == "challenge.flag.submit.pass"
        assert rows[0].attempt == 1
        # Outcome non-OK because the receiver is unreachable.
        assert not rows[0].status.startswith("ok_")
        assert rows[0].response_ms is not None
