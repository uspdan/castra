"""Integration tests for ``app.services.cheat_detector``.

Drives audit-ledger rows through the in-test Postgres + verifies
that the burst detector raises exactly one ``cheat.burst``
notification per burst, idempotently.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Notification

pytestmark = pytest.mark.integration


async def _append_pass(db, *, actor_id: str, when: datetime, slug: str = "demo") -> None:
    from app.services.audit import ActorType, EventType, append as audit_append
    # Insert a fake created_at via direct row construction would
    # require bypassing the chain — instead, just append normally;
    # the test fixtures already strip transaction state per-test.
    await audit_append(
        db,
        event_type=EventType.FLAG_SUBMIT_PASS,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        resource_type="challenge",
        resource_id=slug,
        payload={
            "challenge_slug": slug,
            "points_awarded": 100,
            "is_first_blood": False,
        },
        ip_address="127.0.0.1",
        request_id="test",
    )


@pytest.mark.asyncio
async def test_no_burst_below_threshold(client, user_factory, db_session):
    """Submitting 7 correct flags (under the threshold of 8) raises
    no notifications."""
    from app.services.cheat_detector import detect_bursts

    user = await user_factory(username="cheat-below")
    for i in range(7):
        await _append_pass(db_session, actor_id=str(user.id),
                           when=datetime.now(timezone.utc), slug=f"c{i}")
    await db_session.commit()

    raised = await detect_bursts(db_session)
    assert raised == 0


@pytest.mark.asyncio
async def test_burst_raises_one_notification(client, user_factory, db_session):
    """Crossing the threshold raises one ``cheat.burst`` row."""
    from app.services.cheat_detector import detect_bursts, BURST_THRESHOLD

    user = await user_factory(username="cheat-burst")
    for i in range(BURST_THRESHOLD + 2):
        await _append_pass(db_session, actor_id=str(user.id),
                           when=datetime.now(timezone.utc), slug=f"c{i}")
    await db_session.commit()

    raised = await detect_bursts(db_session)
    assert raised == 1

    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.notification_type == "cheat.burst"
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert str(user.id) in rows[0].title
    assert "Review activity" in rows[0].message


@pytest.mark.asyncio
async def test_burst_is_idempotent(client, user_factory, db_session):
    """Running the detector twice for the same burst raises only
    one notification (signature dedup)."""
    from app.services.cheat_detector import detect_bursts, BURST_THRESHOLD

    user = await user_factory(username="cheat-idem")
    for i in range(BURST_THRESHOLD + 1):
        await _append_pass(db_session, actor_id=str(user.id),
                           when=datetime.now(timezone.utc), slug=f"c{i}")
    await db_session.commit()

    first = await detect_bursts(db_session)
    second = await detect_bursts(db_session)
    assert first == 1
    assert second == 0

    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.notification_type == "cheat.burst"
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_distinct_actors_each_get_one(client, user_factory, db_session):
    from app.services.cheat_detector import detect_bursts, BURST_THRESHOLD

    a = await user_factory(username="cheat-a")
    b = await user_factory(username="cheat-b")
    for i in range(BURST_THRESHOLD + 1):
        await _append_pass(db_session, actor_id=str(a.id),
                           when=datetime.now(timezone.utc), slug=f"a{i}")
        await _append_pass(db_session, actor_id=str(b.id),
                           when=datetime.now(timezone.utc), slug=f"b{i}")
    await db_session.commit()

    raised = await detect_bursts(db_session)
    assert raised == 2
