"""Background retry of retriable failed deliveries.

Slice 7: a scheduled sweep walks the head of each delivery_id chain
and re-dispatches when the backoff window has elapsed. Exponential
backoff capped at 5 attempts so a permanently-broken receiver
doesn't pin a worker forever.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookDelivery, WebhookSubscription

from ._common import logger
from .replay import replay_delivery


_RETRY_MAX_ATTEMPTS = 5
# 30s, 60s, 120s, 240s, 480s — full schedule under 16 minutes.
_RETRY_BASE_DELAY_S = 30


def _is_retriable(status: str) -> bool:
    """Return True iff a delivery in ``status`` should be retried.

    Retriable failures are transient: timeouts, network errors,
    internal-error fallthroughs, and 5xx responses. 4xx responses
    are treated as final — the receiver rejected the body, retrying
    with the same payload won't help, and we'd just keep hammering
    them.
    """

    if status.startswith("ok_"):
        return False
    if status in {"timeout", "network_error", "internal_error"}:
        return True
    if status.startswith("http_5"):
        return True
    return False  # http_4xx and unknown statuses are final


def _next_retry_due_at(created_at: datetime, attempt: int) -> datetime:
    """Compute the earliest UTC instant the ``attempt``-th delivery
    may be retried.

    Exponential backoff: ``base * 2^(attempt-1)`` from the failed
    attempt's ``created_at``. Attempt 1 → +30s, 2 → +60s, 3 → +120s, etc.
    """

    delay = _RETRY_BASE_DELAY_S * (2 ** max(0, attempt - 1))
    base = (
        created_at if created_at.tzinfo
        else created_at.replace(tzinfo=timezone.utc)
    )
    return base + timedelta(seconds=delay)


async def retry_failed_deliveries(
    db: AsyncSession,
    *,
    max_attempts: int = _RETRY_MAX_ATTEMPTS,
    now: datetime | None = None,
    http_client_factory=None,
) -> int:
    """Replay every retriable delivery whose backoff has elapsed.

    Scans ``webhook_deliveries`` for the most-recent attempt per
    ``(subscription_id, delivery_id)`` pair. Skips rows that are
    succeeded (``ok_*``), terminally failed (``http_4xx``),
    cap-reached (``attempt >= max_attempts``), or still inside the
    backoff window. The remainder are replayed via
    :func:`replay_delivery`.

    Commits each replay independently so a poison row doesn't block
    the rest of the queue. Returns the number of rows actually
    re-dispatched (regardless of outcome).
    """

    current_time = now or datetime.now(timezone.utc)

    # Latest attempt per (subscription_id, delivery_id). The
    # subquery uses MAX(attempt) — the rows we want to consider are
    # the heads of each delivery_id's chain.
    latest_attempt_subq = (
        select(
            WebhookDelivery.subscription_id,
            WebhookDelivery.delivery_id,
            func.max(WebhookDelivery.attempt).label("max_attempt"),
        )
        .group_by(
            WebhookDelivery.subscription_id, WebhookDelivery.delivery_id
        )
        .subquery()
    )

    rows = (
        await db.execute(
            select(WebhookDelivery)
            .join(
                latest_attempt_subq,
                (WebhookDelivery.subscription_id == latest_attempt_subq.c.subscription_id)
                & (WebhookDelivery.delivery_id == latest_attempt_subq.c.delivery_id)
                & (WebhookDelivery.attempt == latest_attempt_subq.c.max_attempt),
            )
            .order_by(WebhookDelivery.created_at.asc())
        )
    ).scalars().all()

    replayed = 0
    for head in rows:
        if not _is_retriable(head.status):
            continue
        if head.attempt >= max_attempts:
            continue
        due_at = _next_retry_due_at(head.created_at, head.attempt)
        if current_time < due_at:
            continue

        subscription = (
            await db.execute(
                select(WebhookSubscription).where(
                    WebhookSubscription.id == head.subscription_id,
                    WebhookSubscription.is_active.is_(True),
                )
            )
        ).scalars().first()
        if subscription is None:
            # Subscription deleted or disabled since the last attempt;
            # skip silently rather than retrying into a void.
            continue

        try:
            await replay_delivery(
                db=db,
                delivery=head,
                subscription=subscription,
                http_client_factory=http_client_factory,
            )
            await db.commit()
            replayed += 1
        except Exception as exc:  # noqa: BLE001 — never propagate to scheduler
            logger.error(
                "webhook retry failed",
                subscription_id=head.subscription_id,
                delivery_id=head.delivery_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
    return replayed


__all__ = [
    "_is_retriable",
    "_next_retry_due_at",
    "retry_failed_deliveries",
]
