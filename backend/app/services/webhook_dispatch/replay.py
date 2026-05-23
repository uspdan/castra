"""Manual replay of a previously-recorded delivery."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookDelivery, WebhookSubscription

from ._common import (
    _attempt_one,
    _canonical_body,
    _default_http_client,
    _get_shared_client,
)


async def replay_delivery(
    *,
    db: AsyncSession,
    delivery: WebhookDelivery,
    subscription: WebhookSubscription,
    http_client_factory=None,
) -> WebhookDelivery:
    """Re-dispatch a previously recorded delivery.

    Re-uses the original ``delivery_id`` and canonical payload so
    receivers can de-dupe (they should treat repeated delivery_ids
    as the same logical event). The body is re-signed against the
    subscription's *current* secret — rotating the secret therefore
    invalidates outstanding replays cleanly.

    Returns the freshly-inserted :class:`WebhookDelivery` row,
    flushed but not committed; the caller owns the surrounding tx.
    """

    canonical_body = _canonical_body(
        delivery.event_type, delivery.delivery_id, delivery.payload or {}
    )
    factory = http_client_factory or _default_http_client
    shared_client = (
        _get_shared_client() if http_client_factory is None else None
    )
    outcome = await _attempt_one(
        subscription=subscription,
        event_type=delivery.event_type,
        delivery_id=delivery.delivery_id,
        body=canonical_body,
        factory=factory,
        shared_client=shared_client,
    )

    # Update the subscription's "last_*" cache.
    now = datetime.now(timezone.utc)
    subscription.last_delivery_at = now
    subscription.last_status = outcome.status
    subscription.last_error = (
        (outcome.error or "")[:500] if outcome.error else None
    )
    db.add(subscription)

    # Compute the next attempt number across all rows sharing this
    # delivery_id. The first attempt (attempt=1) was the original
    # ``deliver_event`` call; replays bump from there.
    prior_max = (
        await db.execute(
            select(func.max(WebhookDelivery.attempt)).where(
                WebhookDelivery.delivery_id == delivery.delivery_id,
                WebhookDelivery.subscription_id == subscription.id,
            )
        )
    ).scalar() or 0
    next_attempt = int(prior_max) + 1

    new_row = WebhookDelivery(
        subscription_id=subscription.id,
        event_type=delivery.event_type,
        delivery_id=delivery.delivery_id,
        payload=dict(delivery.payload or {}),
        attempt=next_attempt,
        status=outcome.status,
        http_status=outcome.http_status,
        response_ms=outcome.response_ms,
        error=(outcome.error or "")[:500] if outcome.error else None,
        created_at=now,
    )
    db.add(new_row)
    await db.flush()
    return new_row


__all__ = ["replay_delivery"]
