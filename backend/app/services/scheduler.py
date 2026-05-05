import json
from datetime import datetime, timedelta, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from prometheus_client import Counter, Gauge
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import Notification, Solve, Streak, User

logger = structlog.get_logger()


# Sprint 11 Phase A — audit-verify heartbeat + cumulative finding
# count. Read by ``docs/alerts/audit.rules.yml``.
AUDIT_LAST_VERIFY = Gauge(
    "siege_audit_last_verify_timestamp_seconds",
    "Unix timestamp of the most recent audit verify run.",
)
AUDIT_TAMPER_FINDINGS = Counter(
    "siege_audit_tamper_findings_total",
    "Total tamper findings observed across all verify runs.",
)

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


async def verify_audit_ledger():
    """Sprint 10 Phase B — periodic audit-ledger tamper detection.

    Re-walks the hash chain via :mod:`app.tools.audit_verify` and,
    on a finding, emits a global ``Notification`` + ``ws_manager``
    broadcast tagged ``audit_tamper`` so admins see it on the
    NotificationDropdown immediately. The structured ``ERROR`` log
    line is the secondary signal for log-shipper alerting.

    Sprint 11 Phase A also publishes Prometheus gauges/counters
    that ``docs/alerts/audit.rules.yml`` reads — heartbeat
    timestamp + cumulative finding count.

    Best-effort: an operational failure (DB unreachable) is logged
    but doesn't crash the scheduler.
    """

    from app.tools.audit_verify import _verify
    from app.services.notifications import create_notification

    try:
        report = await _verify()
    except Exception as exc:  # noqa: BLE001 — log + continue
        logger.error("Audit verify scheduler crashed", error=str(exc))
        return

    # Sprint 11 Phase A — heartbeat + finding-count metrics for
    # the alert rules in docs/alerts/audit.rules.yml.
    try:
        AUDIT_LAST_VERIFY.set_to_current_time()
        if report["findings"]:
            AUDIT_TAMPER_FINDINGS.inc(len(report["findings"]))
    except Exception:  # noqa: BLE001 — never fail on metrics
        pass

    if report["ok"]:
        logger.info(
            "audit_ledger.verify_ok",
            rows_checked=report["rows_checked"],
            tail_seq=report["tail_seq"],
        )
        return

    logger.error(
        "audit_ledger.tamper_detected",
        finding_count=len(report["findings"]),
        rows_checked=report["rows_checked"],
        first_finding=report["findings"][0] if report["findings"] else None,
    )

    try:
        async with async_session() as db:
            await create_notification(
                db,
                title="Audit ledger tamper detected",
                message=(
                    f"{len(report['findings'])} finding(s) across "
                    f"{report['rows_checked']} ledger rows. Run "
                    f"`python -m app.tools.audit_verify --json` to inspect."
                ),
                notification_type="audit_tamper",
                is_global=True,
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("audit_ledger.notify_failed", error=str(exc))


async def nightly_db_backup():
    """Sprint 12 Phase A — automated DB backup via pg_dump.

    Reads ``settings.BACKUP_DIR`` + ``BACKUP_RETENTION_DAYS``;
    delegates to :func:`app.services.backup.run_backup`. On
    failure, emits a global ``Notification(type="backup_failed")``
    so admins see it in the NotificationDropdown.
    """

    from app.config import get_settings
    from app.services.backup import run_backup
    from app.services.notifications import create_notification

    settings = get_settings()
    backup_dir = (settings.BACKUP_DIR or "").strip()
    if not backup_dir:
        logger.info("backup.skipped", reason="BACKUP_DIR empty")
        return

    result = await run_backup(
        database_url=settings.DATABASE_URL,
        backup_dir=backup_dir,
        retention_days=settings.BACKUP_RETENTION_DAYS,
    )

    if result.ok:
        return

    logger.error(
        "backup.failed",
        error=result.error,
        duration_s=result.duration_s,
    )
    try:
        async with async_session() as db:
            await create_notification(
                db,
                title="Nightly DB backup failed",
                message=(
                    f"pg_dump returned an error: "
                    f"{(result.error or '?')[:200]}. "
                    f"Inspect the api container logs and re-run "
                    f"`make backup` manually."
                ),
                notification_type="backup_failed",
                is_global=True,
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.error("backup.notify_failed", error=str(exc))


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
    # Sprint 10 Phase B — hourly audit-ledger tamper sweep.
    scheduler.add_job(
        verify_audit_ledger, "interval", hours=1, id="audit_verify"
    )
    # Sprint 12 Phase A — nightly DB backup at 02:30 UTC.
    scheduler.add_job(
        nightly_db_backup, "cron", hour=2, minute=30, id="db_backup"
    )
    scheduler.start()
    logger.info("Scheduler started")
