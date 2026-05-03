import json
from datetime import datetime, timedelta, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import Notification, Solve, Streak, User

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()


async def cleanup_expired_instances():
    from app.services.orchestrator import cleanup_expired
    import redis.asyncio as aioredis
    from app.config import get_settings

    settings = get_settings()
    redis_client = aioredis.from_url(settings.REDIS_URL)
    try:
        async with async_session() as db:
            count = await cleanup_expired(db, redis_client)
            if count:
                logger.info("Cleaned up expired instances", count=count)
    finally:
        await redis_client.close()


async def cache_leaderboard():
    import redis.asyncio as aioredis
    from app.config import get_settings

    settings = get_settings()
    redis_client = aioredis.from_url(settings.REDIS_URL)
    try:
        async with async_session() as db:
            result = await db.execute(
                select(
                    User.id,
                    User.username,
                    User.display_name,
                    User.team,
                    func.coalesce(func.sum(Solve.points_awarded), 0).label("total_points"),
                    func.count(Solve.id).label("total_solves"),
                )
                .outerjoin(Solve, User.id == Solve.user_id)
                .where(User.is_active == True)
                .group_by(User.id)
                .order_by(func.coalesce(func.sum(Solve.points_awarded), 0).desc())
                .limit(50)
            )
            rows = result.all()
            leaderboard = []
            for rank, row in enumerate(rows, 1):
                streak_result = await db.execute(
                    select(Streak).where(Streak.user_id == row.id)
                )
                streak = streak_result.scalar_one_or_none()
                leaderboard.append({
                    "rank": rank,
                    "user_id": row.id,
                    "username": row.username,
                    "display_name": row.display_name,
                    "team": row.team.value if row.team else None,
                    "total_points": int(row.total_points),
                    "total_solves": int(row.total_solves),
                    "current_streak": streak.current_streak if streak else 0,
                    "longest_streak": streak.longest_streak if streak else 0,
                })
            await redis_client.set("siege:leaderboard", json.dumps(leaderboard), ex=120)
    except Exception as e:
        logger.error("Failed to cache leaderboard", error=str(e))
    finally:
        await redis_client.close()


async def cleanup_notifications():
    try:
        async with async_session() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            await db.execute(
                delete(Notification).where(
                    Notification.is_read == True,
                    Notification.created_at < cutoff,
                )
            )
            await db.commit()
            logger.info("Cleaned up old notifications")
    except Exception as e:
        logger.error("Notification cleanup failed", error=str(e))


async def retry_failed_webhooks():
    """Phase 12 (slice 7) — replay retriable webhook deliveries."""

    from app.services.webhook_dispatch import retry_failed_deliveries

    try:
        async with async_session() as db:
            replayed = await retry_failed_deliveries(db)
            if replayed:
                logger.info(
                    "webhook retry pass complete", replayed=replayed
                )
    except Exception as e:
        logger.error("Webhook retry failed", error=str(e))


async def prune_old_webhook_deliveries():
    """Phase 12 (slice 7) — drop webhook_deliveries rows past retention."""

    from app.services.webhook_dispatch import prune_old_deliveries

    try:
        async with async_session() as db:
            deleted = await prune_old_deliveries(db, retention_days=30)
            await db.commit()
            if deleted:
                logger.info(
                    "webhook deliveries pruned", deleted=deleted
                )
    except Exception as e:
        logger.error("Webhook prune failed", error=str(e))


def setup_scheduler():
    scheduler.add_job(cleanup_expired_instances, "interval", minutes=5, id="cleanup_expired")
    scheduler.add_job(cache_leaderboard, "interval", seconds=60, id="cache_leaderboard")
    scheduler.add_job(cleanup_notifications, "cron", hour=3, minute=0, id="notification_cleanup")
    # Phase 12 (slice 7): webhook retry sweep + retention prune.
    scheduler.add_job(
        retry_failed_webhooks, "interval", minutes=1, id="webhook_retry"
    )
    scheduler.add_job(
        prune_old_webhook_deliveries,
        "cron", hour=4, minute=0, id="webhook_prune",
    )
    scheduler.start()
    logger.info("Scheduler started")
