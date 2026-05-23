"""Bulk retention prune for ``webhook_deliveries``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookDelivery


async def prune_old_deliveries(
    db: AsyncSession,
    *,
    retention_days: int = 30,
    now: datetime | None = None,
) -> int:
    """Delete ``webhook_deliveries`` rows older than
    ``retention_days``.

    Bulk DELETE without per-row hooks. Returns the count of rows
    removed for logging. The caller is responsible for the
    surrounding commit.
    """

    if retention_days < 1:
        raise ValueError("retention_days must be >= 1")
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(
        days=retention_days
    )
    result = await db.execute(
        sa_delete(WebhookDelivery).where(
            WebhookDelivery.created_at < cutoff
        )
    )
    await db.flush()
    return int(result.rowcount or 0)


__all__ = ["prune_old_deliveries"]
