"""Integration tests for the webhook retry sweep + retention prune
helpers (slice 7)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.models import WebhookDelivery, WebhookSubscription
from app.services.webhook_dispatch import (
    _is_retriable,
    _next_retry_due_at,
    prune_old_deliveries,
    retry_failed_deliveries,
)


@pytest.fixture(autouse=True)
def _bypass_ssrf_guard(monkeypatch):
    """R4 SSRF guard refuses ``example.invalid`` (no DNS A record).
    These tests stub the HTTP client wholesale, so the guard isn't
    validating real reachability — bypass it. The guard itself is
    exercised in ``test_webhook_ssrf.py``."""

    monkeypatch.setattr(
        "app.services.webhook_dispatch.assert_url_safe",
        lambda url: None,
    )


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
class TestIsRetriable:
    @pytest.mark.parametrize(
        "status,expected",
        [
            ("ok_200", False),
            ("ok_201", False),
            ("ok_204", False),
            ("timeout", True),
            ("network_error", True),
            ("internal_error", True),
            ("http_500", True),
            ("http_503", True),
            ("http_504", True),
            ("http_400", False),
            ("http_401", False),
            ("http_404", False),
            ("http_410", False),
            ("unknown", False),
            ("", False),
        ],
    )
    def test_status_classification(self, status, expected):
        assert _is_retriable(status) is expected


class TestNextRetryDueAt:
    def test_first_retry_is_30s(self):
        anchor = datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc)
        assert _next_retry_due_at(anchor, 1) == anchor + timedelta(seconds=30)

    def test_exponential_backoff(self):
        anchor = datetime(2026, 5, 2, 10, 0, 0, tzinfo=timezone.utc)
        assert _next_retry_due_at(anchor, 1) - anchor == timedelta(seconds=30)
        assert _next_retry_due_at(anchor, 2) - anchor == timedelta(seconds=60)
        assert _next_retry_due_at(anchor, 3) - anchor == timedelta(seconds=120)
        assert _next_retry_due_at(anchor, 4) - anchor == timedelta(seconds=240)

    def test_naive_datetime_is_treated_as_utc(self):
        anchor_naive = datetime(2026, 5, 2, 10, 0, 0)
        anchor_utc = anchor_naive.replace(tzinfo=timezone.utc)
        assert _next_retry_due_at(anchor_naive, 1) == _next_retry_due_at(
            anchor_utc, 1
        )


# ---------------------------------------------------------------------------
# retry_failed_deliveries
# ---------------------------------------------------------------------------
class _StubResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _StubClient:
    """Replays succeed (200) by default. Per-test instances configurable."""

    def __init__(self, *, status_code: int = 200, raises: Exception | None = None):
        self._status = status_code
        self._raises = raises
        self.calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url: str, *, content: bytes, headers: dict):
        self.calls.append(url)
        if self._raises is not None:
            raise self._raises
        return _StubResponse(self._status)


async def _seed_sub(db_session, *, owner_id: int, is_active: bool = True):
    sub = WebhookSubscription(
        owner_user_id=owner_id,
        name="retry-sub",
        target_url="http://127.0.0.1:1/never",
        secret="s" * 64,
        events=["*"],
        is_active=is_active,
    )
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(sub)
    return sub


async def _seed_delivery(
    db_session,
    *,
    subscription_id: int,
    delivery_id: str,
    status: str,
    attempt: int,
    created_at: datetime,
):
    row = WebhookDelivery(
        subscription_id=subscription_id,
        event_type="challenge.flag.submit.pass",
        delivery_id=delivery_id,
        payload={"x": 1},
        attempt=attempt,
        status=status,
        http_status=int(status.split("_")[1]) if status.startswith("http_") else None,
        response_ms=10,
        error=None if status.startswith("ok_") else "boom",
        created_at=created_at,
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


class TestRetryFailedDeliveries:
    async def test_no_rows_is_zero(self, db_session):
        replayed = await retry_failed_deliveries(db_session)
        assert replayed == 0

    async def test_skips_ok_rows(self, db_session, user_factory):
        admin = await user_factory()
        sub = await _seed_sub(db_session, owner_id=admin.id)
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        await _seed_delivery(
            db_session, subscription_id=sub.id, delivery_id="ok",
            status="ok_200", attempt=1, created_at=old,
        )
        replayed = await retry_failed_deliveries(
            db_session, http_client_factory=lambda: _StubClient(),
        )
        assert replayed == 0

    async def test_skips_4xx_rows(self, db_session, user_factory):
        admin = await user_factory()
        sub = await _seed_sub(db_session, owner_id=admin.id)
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        await _seed_delivery(
            db_session, subscription_id=sub.id, delivery_id="bad",
            status="http_404", attempt=1, created_at=old,
        )
        replayed = await retry_failed_deliveries(
            db_session, http_client_factory=lambda: _StubClient(),
        )
        assert replayed == 0

    async def test_replays_retriable_after_backoff(
        self, db_session, user_factory
    ):
        admin = await user_factory()
        sub = await _seed_sub(db_session, owner_id=admin.id)
        # Created 60s ago — past the 30s first-retry backoff window.
        old = datetime.now(timezone.utc) - timedelta(seconds=60)
        await _seed_delivery(
            db_session, subscription_id=sub.id, delivery_id="boom",
            status="timeout", attempt=1, created_at=old,
        )
        stubs: list[_StubClient] = []

        def factory():
            stub = _StubClient(status_code=200)
            stubs.append(stub)
            return stub

        replayed = await retry_failed_deliveries(
            db_session, http_client_factory=factory
        )
        assert replayed == 1
        # New attempt row exists with attempt=2 and status ok_200.
        rows = (
            await db_session.execute(
                select(WebhookDelivery)
                .where(WebhookDelivery.delivery_id == "boom")
                .order_by(WebhookDelivery.attempt.asc())
            )
        ).scalars().all()
        assert [r.attempt for r in rows] == [1, 2]
        assert rows[1].status == "ok_200"

    async def test_skips_within_backoff_window(
        self, db_session, user_factory
    ):
        admin = await user_factory()
        sub = await _seed_sub(db_session, owner_id=admin.id)
        # Created 5s ago — well inside the 30s first-retry window.
        recent = datetime.now(timezone.utc) - timedelta(seconds=5)
        await _seed_delivery(
            db_session, subscription_id=sub.id, delivery_id="b",
            status="timeout", attempt=1, created_at=recent,
        )
        replayed = await retry_failed_deliveries(
            db_session, http_client_factory=lambda: _StubClient(),
        )
        assert replayed == 0

    async def test_caps_at_max_attempts(self, db_session, user_factory):
        admin = await user_factory()
        sub = await _seed_sub(db_session, owner_id=admin.id)
        old = datetime.now(timezone.utc) - timedelta(hours=1)
        # Five attempts already — cap reached.
        for i in range(1, 6):
            await _seed_delivery(
                db_session, subscription_id=sub.id, delivery_id="cap",
                status="timeout", attempt=i, created_at=old,
            )
        replayed = await retry_failed_deliveries(
            db_session, http_client_factory=lambda: _StubClient(),
        )
        assert replayed == 0

    async def test_subscription_inactive_skipped(
        self, db_session, user_factory
    ):
        admin = await user_factory()
        sub = await _seed_sub(db_session, owner_id=admin.id, is_active=False)
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        await _seed_delivery(
            db_session, subscription_id=sub.id, delivery_id="d",
            status="timeout", attempt=1, created_at=old,
        )
        replayed = await retry_failed_deliveries(
            db_session, http_client_factory=lambda: _StubClient(),
        )
        assert replayed == 0

    async def test_picks_only_latest_attempt(
        self, db_session, user_factory
    ):
        admin = await user_factory()
        sub = await _seed_sub(db_session, owner_id=admin.id)
        old = datetime.now(timezone.utc) - timedelta(minutes=10)
        # Two existing attempts; we expect the retry sweep to consider
        # only attempt=2 (the head) and replay it as attempt=3.
        await _seed_delivery(
            db_session, subscription_id=sub.id, delivery_id="chain",
            status="timeout", attempt=1, created_at=old,
        )
        await _seed_delivery(
            db_session, subscription_id=sub.id, delivery_id="chain",
            status="timeout", attempt=2,
            created_at=old + timedelta(minutes=1),
        )

        def factory():
            return _StubClient(status_code=200)

        replayed = await retry_failed_deliveries(
            db_session, http_client_factory=factory
        )
        assert replayed == 1
        attempts = sorted(
            r.attempt
            for r in (
                await db_session.execute(
                    select(WebhookDelivery).where(
                        WebhookDelivery.delivery_id == "chain"
                    )
                )
            ).scalars().all()
        )
        assert attempts == [1, 2, 3]

    async def test_failed_replay_recorded_with_incremented_attempt(
        self, db_session, user_factory
    ):
        admin = await user_factory()
        sub = await _seed_sub(db_session, owner_id=admin.id)
        old = datetime.now(timezone.utc) - timedelta(minutes=5)
        await _seed_delivery(
            db_session, subscription_id=sub.id, delivery_id="f",
            status="timeout", attempt=1, created_at=old,
        )

        def factory():
            return _StubClient(raises=httpx.ConnectError("nope"))

        replayed = await retry_failed_deliveries(
            db_session, http_client_factory=factory
        )
        assert replayed == 1
        rows = (
            await db_session.execute(
                select(WebhookDelivery)
                .where(WebhookDelivery.delivery_id == "f")
                .order_by(WebhookDelivery.attempt.asc())
            )
        ).scalars().all()
        assert [r.attempt for r in rows] == [1, 2]
        assert rows[1].status == "network_error"


# ---------------------------------------------------------------------------
# prune_old_deliveries
# ---------------------------------------------------------------------------
class TestPruneOldDeliveries:
    async def test_removes_only_old_rows(self, db_session, user_factory):
        admin = await user_factory()
        sub = await _seed_sub(db_session, owner_id=admin.id)
        now = datetime.now(timezone.utc)
        # Two old rows, two recent rows.
        for offset_days in (60, 45):
            await _seed_delivery(
                db_session, subscription_id=sub.id,
                delivery_id=f"old-{offset_days}",
                status="ok_200", attempt=1,
                created_at=now - timedelta(days=offset_days),
            )
        for offset_days in (10, 1):
            await _seed_delivery(
                db_session, subscription_id=sub.id,
                delivery_id=f"new-{offset_days}",
                status="ok_200", attempt=1,
                created_at=now - timedelta(days=offset_days),
            )

        deleted = await prune_old_deliveries(
            db_session, retention_days=30, now=now
        )
        await db_session.commit()
        assert deleted == 2

        remaining = (
            await db_session.execute(
                select(WebhookDelivery.delivery_id).order_by(
                    WebhookDelivery.delivery_id
                )
            )
        ).scalars().all()
        assert sorted(remaining) == ["new-1", "new-10"]

    async def test_invalid_retention_rejected(self, db_session):
        with pytest.raises(ValueError):
            await prune_old_deliveries(db_session, retention_days=0)
