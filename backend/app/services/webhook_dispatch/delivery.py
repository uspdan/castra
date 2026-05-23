"""Fan-out: take one ``audit_ledger`` emit + push to every matching
subscription concurrently."""

from __future__ import annotations

import asyncio
import secrets as _secrets
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookDelivery, WebhookSubscription

from ._common import (
    _AttemptOutcome,
    _attempt_one,
    _canonical_body,
    _default_http_client,
    _get_shared_client,
)


async def deliver_event(
    *,
    db: AsyncSession,
    event_type: str,
    payload: Mapping[str, Any],
    http_client_factory=None,
) -> None:
    """Fan out a single audit event to every matching subscription.

    Loads active :class:`WebhookSubscription` rows whose ``events``
    list contains ``event_type``, signs the canonical JSON body
    with each subscription's secret, and POSTs concurrently. The
    function returns when every dispatch task has completed (or
    its 5-second timeout has elapsed). Per-row ``last_*`` fields
    are updated and committed in the calling transaction.

    ``http_client_factory`` is a test seam; production callers omit
    it and reuse the module-scoped client via
    :func:`_get_shared_client`.
    """

    subscriptions = await _matching_subscriptions(db, event_type)
    if not subscriptions:
        return

    delivery_id = _secrets.token_hex(8)
    canonical_body = _canonical_body(event_type, delivery_id, payload)

    # R32: production callers reuse the module-scoped client so the
    # connection pool persists across attempts + fan-outs. Tests
    # still pass ``http_client_factory`` to stub the HTTP layer.
    factory = http_client_factory or _default_http_client
    shared_client = (
        _get_shared_client() if http_client_factory is None else None
    )

    outcomes: list[_AttemptOutcome] = await asyncio.gather(
        *(
            _attempt_one(
                subscription=sub,
                event_type=event_type,
                delivery_id=delivery_id,
                body=canonical_body,
                factory=factory,
                shared_client=shared_client,
            )
            for sub in subscriptions
        ),
        return_exceptions=False,
    )
    now = datetime.now(timezone.utc)
    for outcome in outcomes:
        sub = outcome.subscription
        sub.last_delivery_at = now
        sub.last_status = outcome.status
        sub.last_error = (
            (outcome.error or "")[:500] if outcome.error else None
        )
        db.add(sub)
        # Phase 12 (slice 6): record an attempt row in
        # ``webhook_deliveries`` so the v1 list endpoint and replay
        # endpoint have something to read.
        db.add(
            WebhookDelivery(
                subscription_id=sub.id,
                event_type=event_type,
                delivery_id=delivery_id,
                payload=dict(payload),
                attempt=1,
                status=outcome.status,
                http_status=outcome.http_status,
                response_ms=outcome.response_ms,
                error=(outcome.error or "")[:500] if outcome.error else None,
                created_at=now,
            )
        )
    await db.flush()


async def _matching_subscriptions(
    db: AsyncSession, event_type: str
) -> list[WebhookSubscription]:
    rows = (
        await db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.is_active.is_(True)
            )
        )
    ).scalars().all()
    out: list[WebhookSubscription] = []
    for row in rows:
        events = list(row.events or [])
        if event_type in events or "*" in events:
            out.append(row)
    return out


__all__ = ["deliver_event"]
