"""Cheat-resistance Tier 4 — submission-burst detector.

Queries the hash-chained audit ledger for
``challenge.flag.submit.pass`` events in a rolling window, groups by
actor, and raises an admin notification when a single actor crosses
the burst threshold.

Design:

* **Stateless** — the audit ledger is the source of truth. Each
  scheduler tick re-scans the last ``window`` minutes. No
  intermediate table.
* **Idempotent** — a per-user fingerprint of (count, window-start)
  is encoded in the notification's title so duplicate alerts for
  the same burst aren't created on the next tick.
* **Defence in depth, not enforcement** — this surfaces a signal;
  human review is the gate. Auto-disqualification belongs in a
  separate decision layer.

Tunables (defaults documented in CLAUDE.md §16.3 spirit — bounded
queries, no unbounded scans):

* ``BURST_WINDOW_MINUTES = 15``
* ``BURST_THRESHOLD = 8`` correct flags in that window
* The query is capped at ``BURST_QUERY_LIMIT = 5000`` rows; if
  exceeded, the log line "cheat_detector.window_capped" fires and
  the operator should narrow the window or bump the threshold.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Final

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLedger, Notification
from app.services.notifications import create_notification

logger = structlog.get_logger()

BURST_WINDOW_MINUTES: Final = 15
BURST_THRESHOLD: Final = 8
BURST_QUERY_LIMIT: Final = 5000

_EVENT = "challenge.flag.submit.pass"


def _signature(actor_id: str, count: int, window_start_iso: str) -> str:
    """Stable per-burst fingerprint embedded in the notification title
    so duplicate alerts for the same burst don't pile up.
    """
    return f"actor={actor_id}|count={count}|since={window_start_iso}"


async def detect_bursts(db: AsyncSession) -> int:
    """Single sweep. Returns the number of new alerts raised."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=BURST_WINDOW_MINUTES)

    rows = (
        await db.execute(
            select(AuditLedger.actor_id, AuditLedger.created_at)
            .where(AuditLedger.event_type == _EVENT)
            .where(AuditLedger.created_at >= window_start)
            .order_by(AuditLedger.created_at)
            .limit(BURST_QUERY_LIMIT)
        )
    ).all()

    if len(rows) >= BURST_QUERY_LIMIT:
        logger.warning(
            "cheat_detector.window_capped",
            limit=BURST_QUERY_LIMIT,
            window_minutes=BURST_WINDOW_MINUTES,
        )

    by_actor: dict[str, list[datetime]] = {}
    for actor_id, when in rows:
        if not actor_id:
            continue
        by_actor.setdefault(actor_id, []).append(when)

    raised = 0
    for actor_id, timestamps in by_actor.items():
        if len(timestamps) < BURST_THRESHOLD:
            continue
        window_start_iso = timestamps[0].isoformat(timespec="seconds")
        sig = _signature(actor_id, len(timestamps), window_start_iso)

        # Idempotency check — same signature already raised this hour?
        existing = (
            await db.execute(
                select(Notification.id)
                .where(Notification.notification_type == "cheat.burst")
                .where(Notification.title.contains(sig))
                .limit(1)
            )
        ).first()
        if existing is not None:
            continue

        await create_notification(
            db,
            title=f"Submission burst: {sig}",
            message=(
                f"User {actor_id} recorded {len(timestamps)} correct "
                f"flag submissions in the {BURST_WINDOW_MINUTES} minute "
                f"window starting {window_start_iso}. Threshold is "
                f"{BURST_THRESHOLD}. Review activity at "
                f"/admin → Audit log → filter by actor_id={actor_id}."
            ),
            notification_type="cheat.burst",
            is_global=False,  # admin-only — surfaced via /admin
        )
        raised += 1
        logger.info(
            "cheat_detector.burst",
            actor_id=actor_id,
            count=len(timestamps),
            window_minutes=BURST_WINDOW_MINUTES,
            window_start=window_start_iso,
        )
    if raised:
        await db.commit()
    return raised
