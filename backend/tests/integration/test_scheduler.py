"""Integration tests for the scheduler jobs.

Brings :mod:`app.services.scheduler` under the project-wide coverage
gate. The jobs use ``async_session`` directly (not the dependency-
injected per-request session), so the savepoint-rollback harness from
``conftest.py`` is bypassed — these tests run against the
testcontainer Postgres directly and clean up their own rows.

We stub Redis with a local in-memory fake (``_FakeRedis``) and patch
``aioredis.from_url`` so the scheduler doesn't need a live Redis to
exercise the ``cache_leaderboard`` path.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------
class _FakeRedis:
    """Minimal Redis stub: tracks ``set``/``publish`` calls."""

    def __init__(self):
        self.values: dict[str, tuple[str, int | None]] = {}
        self.published: list[tuple[str, str]] = []

    async def set(self, key, value, ex=None):
        self.values[key] = (value, ex)
        return True

    async def publish(self, channel, message):
        self.published.append((channel, message))

    async def close(self):
        return None


def _patch_aioredis(monkeypatch, fake):
    import redis.asyncio as aioredis

    def _from_url(*_args, **_kwargs):
        return fake

    monkeypatch.setattr(aioredis, "from_url", _from_url)


async def _seed_user_with_solves(db, *, username, points_each, count):
    from app.models import Challenge, Solve, TeamType, User, UserRole
    from app.services.auth import hash_password
    from app.validators.exact import hash_exact_value

    user = User(
        email=f"{username}@sched.local",
        username=username,
        display_name=username,
        hashed_password=hash_password("DummyPasswordA1!"),
        role=UserRole.operator,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Solves carry a FK to challenges + UNIQUE(user_id, challenge_id);
    # spawn ``count`` real Challenge rows so the leaderboard's
    # aggregate sum/count picks them up.
    challenge_ids: list[int] = []
    for i in range(count):
        chal = Challenge(
            slug=f"sched-{username}-{i}",
            title=f"Sched {username} {i}",
            description="seeded by test_scheduler",
            category="general",
            team=TeamType.red,
            difficulty=1,
            points=points_each,
            flag_hash=hash_exact_value(f"CTF{REDACTED}-{i}}}"),
            hints=[],
            skills=[],
            mitre_techniques=[],
            docker_image="alpine:3.19",
            docker_port=8080,
            docker_config={},
            prerequisite_ids=[],
            is_active=True,
            is_released=True,
            released_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(chal)
        await db.flush()
        await db.refresh(chal)
        challenge_ids.append(chal.id)
        db.add(
            Solve(
                user_id=user.id,
                challenge_id=chal.id,
                points_awarded=points_each,
                is_first_blood=False,
                solved_at=datetime.now(timezone.utc),
            )
        )
    await db.commit()
    await db.refresh(user)
    user.challenge_ids = challenge_ids  # type: ignore[attr-defined]
    return user


# ---------------------------------------------------------------------------
# cache_leaderboard
# ---------------------------------------------------------------------------
class TestCacheLeaderboard:
    async def test_writes_top_users_to_redis(
        self, _bootstrap_env, monkeypatch
    ):
        import json

        from app.database import async_session
        from app.models import Solve, User
        from app.services import scheduler

        fake = _FakeRedis()
        _patch_aioredis(monkeypatch, fake)

        async with async_session() as db:
            user = await _seed_user_with_solves(
                db, username="schedlbuser", points_each=50, count=2
            )

        try:
            await scheduler.cache_leaderboard()

            assert "siege:leaderboard" in fake.values
            payload, ttl = fake.values["siege:leaderboard"]
            entries = json.loads(payload)
            assert isinstance(entries, list)
            assert ttl == 120
            usernames = [e["username"] for e in entries]
            assert "schedlbuser" in usernames
            entry = next(e for e in entries if e["username"] == "schedlbuser")
            assert entry["total_points"] == 100  # 50 × 2
            assert entry["total_solves"] == 2
            assert entry["rank"] >= 1
        finally:
            from app.models import Challenge

            async with async_session() as db:
                await db.execute(
                    delete(Solve).where(Solve.user_id == user.id)
                )
                cids = getattr(user, "challenge_ids", []) or []
                if cids:
                    await db.execute(
                        delete(Challenge).where(Challenge.id.in_(cids))
                    )
                await db.execute(delete(User).where(User.id == user.id))
                await db.commit()

    async def test_swallows_redis_failures(
        self, _bootstrap_env, monkeypatch
    ):
        from app.services import scheduler

        class _Boom(_FakeRedis):
            async def set(self, *_a, **_kw):
                raise RuntimeError("redis down")

        _patch_aioredis(monkeypatch, _Boom())
        # Should NOT raise; logs and moves on.
        await scheduler.cache_leaderboard()


# ---------------------------------------------------------------------------
# cleanup_notifications
# ---------------------------------------------------------------------------
class TestCleanupNotifications:
    async def test_deletes_old_read_notifications(
        self, _bootstrap_env, monkeypatch
    ):
        from app.database import async_session
        from app.models import Notification
        from app.services import scheduler

        # Two notifications: one fresh + read, one old + read. Only
        # the second should be reaped.
        async with async_session() as db:
            fresh = Notification(
                title="Fresh",
                message="x",
                notification_type="info",
                is_global=True,
                is_read=True,
                created_at=datetime.now(timezone.utc),
            )
            old = Notification(
                title="Old",
                message="x",
                notification_type="info",
                is_global=True,
                is_read=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=60),
            )
            db.add_all([fresh, old])
            await db.commit()
            await db.refresh(fresh)
            await db.refresh(old)
            fresh_id = fresh.id
            old_id = old.id

        try:
            await scheduler.cleanup_notifications()

            async with async_session() as db:
                fresh_row = (
                    await db.execute(
                        select(Notification).where(
                            Notification.id == fresh_id
                        )
                    )
                ).scalars().first()
                old_row = (
                    await db.execute(
                        select(Notification).where(
                            Notification.id == old_id
                        )
                    )
                ).scalars().first()
            assert fresh_row is not None  # not reaped
            assert old_row is None  # reaped
        finally:
            async with async_session() as db:
                await db.execute(
                    delete(Notification).where(
                        Notification.id.in_([fresh_id, old_id])
                    )
                )
                await db.commit()

    async def test_keeps_unread_notifications(
        self, _bootstrap_env, monkeypatch
    ):
        from app.database import async_session
        from app.models import Notification
        from app.services import scheduler

        async with async_session() as db:
            unread_old = Notification(
                title="Unread Old",
                message="x",
                notification_type="info",
                is_global=True,
                is_read=False,
                created_at=datetime.now(timezone.utc) - timedelta(days=60),
            )
            db.add(unread_old)
            await db.commit()
            await db.refresh(unread_old)
            row_id = unread_old.id
        try:
            await scheduler.cleanup_notifications()
            async with async_session() as db:
                survived = (
                    await db.execute(
                        select(Notification).where(
                            Notification.id == row_id
                        )
                    )
                ).scalars().first()
            assert survived is not None
        finally:
            async with async_session() as db:
                await db.execute(
                    delete(Notification).where(Notification.id == row_id)
                )
                await db.commit()


# ---------------------------------------------------------------------------
# cleanup_expired_instances
# ---------------------------------------------------------------------------
class TestCleanupExpiredInstancesJob:
    async def test_swallows_inner_exceptions(
        self, _bootstrap_env, monkeypatch
    ):
        from app.services import scheduler

        async def _boom(_db, _redis):
            raise RuntimeError("simulated cleanup failure")

        # The scheduler imports cleanup_expired lazily inside the
        # function; patch the source module's attribute.
        import app.services.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "cleanup_expired", _boom)
        _patch_aioredis(monkeypatch, _FakeRedis())

        with pytest.raises(RuntimeError):
            # Implementation note: scheduler.cleanup_expired_instances
            # does NOT swallow inner exceptions today — it only logs
            # successful cleanup counts. The job is wrapped by
            # apscheduler at call time. Asserting the raise here
            # documents the contract; if we later add a try/except
            # this test pins what changed.
            await scheduler.cleanup_expired_instances()

    async def test_no_op_when_nothing_expired(
        self, _bootstrap_env, monkeypatch
    ):
        from app.services import scheduler

        async def _zero(_db, _redis):
            return 0

        import app.services.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "cleanup_expired", _zero)
        _patch_aioredis(monkeypatch, _FakeRedis())

        # Returns None on no-op; should not raise.
        out = await scheduler.cleanup_expired_instances()
        assert out is None


# ---------------------------------------------------------------------------
# Webhook retry / prune jobs
# ---------------------------------------------------------------------------
class TestWebhookSchedulerJobs:
    async def test_retry_failed_webhooks_runs(
        self, _bootstrap_env, monkeypatch
    ):
        from app.services import scheduler
        from app.services import webhook_dispatch as wd

        called = {"n": 0}

        async def _fake_retry(_db):
            called["n"] += 1
            return 0

        monkeypatch.setattr(wd, "retry_failed_deliveries", _fake_retry)

        await scheduler.retry_failed_webhooks()
        assert called["n"] == 1

    async def test_retry_failed_webhooks_swallows_errors(
        self, _bootstrap_env, monkeypatch
    ):
        from app.services import scheduler
        from app.services import webhook_dispatch as wd

        async def _boom(_db):
            raise RuntimeError("webhook backend down")

        monkeypatch.setattr(wd, "retry_failed_deliveries", _boom)

        await scheduler.retry_failed_webhooks()  # must not raise

    async def test_prune_old_webhook_deliveries_runs(
        self, _bootstrap_env, monkeypatch
    ):
        from app.services import scheduler
        from app.services import webhook_dispatch as wd

        seen = {"days": None}

        async def _fake_prune(_db, *, retention_days):
            seen["days"] = retention_days
            return 0

        monkeypatch.setattr(wd, "prune_old_deliveries", _fake_prune)

        await scheduler.prune_old_webhook_deliveries()
        assert seen["days"] == 30

    async def test_prune_swallows_errors(
        self, _bootstrap_env, monkeypatch
    ):
        from app.services import scheduler
        from app.services import webhook_dispatch as wd

        async def _boom(_db, *, retention_days):
            raise RuntimeError("prune broken")

        monkeypatch.setattr(wd, "prune_old_deliveries", _boom)

        await scheduler.prune_old_webhook_deliveries()  # no raise


# ---------------------------------------------------------------------------
# verify_audit_ledger — Sprint 10 Phase B
# ---------------------------------------------------------------------------
class TestVerifyAuditLedger:
    async def test_clean_chain_no_notification(
        self, _bootstrap_env, monkeypatch
    ):
        from app.services import scheduler

        async def _fake_verify():
            return {
                "ok": True,
                "rows_checked": 5,
                "tail_seq": 5,
                "tail_hash": "abcd",
                "findings": [],
            }

        import app.tools.audit_verify as av_mod
        monkeypatch.setattr(av_mod, "_verify", _fake_verify)
        # Capture pre-state so we can assert the heartbeat updated
        # but no tamper increment.
        before_hb = scheduler.AUDIT_LAST_VERIFY._value.get()  # type: ignore[attr-defined]
        before_findings = scheduler.AUDIT_TAMPER_FINDINGS._value.get()  # type: ignore[attr-defined]

        await scheduler.verify_audit_ledger()

        assert scheduler.AUDIT_LAST_VERIFY._value.get() >= before_hb  # type: ignore[attr-defined]
        # Clean chain — finding counter must NOT advance.
        assert (
            scheduler.AUDIT_TAMPER_FINDINGS._value.get()  # type: ignore[attr-defined]
            == before_findings
        )

    async def test_tamper_increments_metric(
        self, _bootstrap_env, monkeypatch
    ):
        """Sprint 11 Phase A — audit alert rules read this counter."""

        from app.services import scheduler

        async def _fake_verify():
            return {
                "ok": False,
                "rows_checked": 5,
                "tail_seq": 5,
                "tail_hash": "abcd",
                "findings": [
                    {"kind": "hash_mismatch", "seq": 3, "row_id": 3},
                    {"kind": "seq_gap", "seq": 4, "row_id": 4},
                ],
            }

        import app.tools.audit_verify as av_mod
        monkeypatch.setattr(av_mod, "_verify", _fake_verify)
        before = scheduler.AUDIT_TAMPER_FINDINGS._value.get()  # type: ignore[attr-defined]

        await scheduler.verify_audit_ledger()

        # Two findings → counter advances by 2.
        assert (
            scheduler.AUDIT_TAMPER_FINDINGS._value.get()  # type: ignore[attr-defined]
            == before + 2
        )

        # Cleanup the notification we just created so other tests
        # don't see it.
        from sqlalchemy import delete as _delete
        from app.database import async_session
        from app.models import Notification

        async with async_session() as db:
            await db.execute(
                _delete(Notification).where(
                    Notification.notification_type == "audit_tamper"
                )
            )
            await db.commit()

    async def test_tamper_emits_notification(
        self, _bootstrap_env, monkeypatch
    ):
        from app.database import async_session
        from app.models import Notification
        from app.services import scheduler
        from sqlalchemy import delete

        async def _fake_verify():
            return {
                "ok": False,
                "rows_checked": 5,
                "tail_seq": 5,
                "tail_hash": "abcd",
                "findings": [
                    {"kind": "hash_mismatch", "seq": 3, "row_id": 3}
                ],
            }

        import app.tools.audit_verify as av_mod
        monkeypatch.setattr(av_mod, "_verify", _fake_verify)

        async with async_session() as db:
            await db.execute(
                delete(Notification).where(
                    Notification.notification_type == "audit_tamper"
                )
            )
            await db.commit()

        await scheduler.verify_audit_ledger()

        async with async_session() as db:
            from sqlalchemy import select
            rows = (
                await db.execute(
                    select(Notification).where(
                        Notification.notification_type == "audit_tamper"
                    )
                )
            ).scalars().all()
        assert len(rows) >= 1
        assert "tamper" in rows[-1].title.lower()

        # Cleanup so other tests don't see the notification.
        async with async_session() as db:
            await db.execute(
                delete(Notification).where(
                    Notification.notification_type == "audit_tamper"
                )
            )
            await db.commit()

    async def test_operational_failure_swallowed(
        self, _bootstrap_env, monkeypatch
    ):
        from app.services import scheduler

        async def _boom():
            raise RuntimeError("db down")

        import app.tools.audit_verify as av_mod
        monkeypatch.setattr(av_mod, "_verify", _boom)
        # Must not raise.
        await scheduler.verify_audit_ledger()


# ---------------------------------------------------------------------------
# setup_scheduler — registers all expected jobs
# ---------------------------------------------------------------------------
class TestSetupScheduler:
    def test_registers_expected_jobs(self, monkeypatch):
        from app.services import scheduler as scheduler_mod

        # Patch start() so we don't actually spin a background loop.
        started = {"n": 0}

        def _fake_start():
            started["n"] += 1

        monkeypatch.setattr(scheduler_mod.scheduler, "start", _fake_start)
        # Clear any pre-existing jobs from earlier test runs.
        for job in list(scheduler_mod.scheduler.get_jobs()):
            scheduler_mod.scheduler.remove_job(job.id)

        scheduler_mod.setup_scheduler()

        ids = {j.id for j in scheduler_mod.scheduler.get_jobs()}
        assert ids == {
            "cleanup_expired",
            "cache_leaderboard",
            "notification_cleanup",
            "webhook_retry",
            "webhook_prune",
            "audit_verify",
            "db_backup",
            "workstation_reap",
        }
        assert started["n"] == 1

        # Cleanup so the scheduler doesn't carry state into later tests.
        for job in list(scheduler_mod.scheduler.get_jobs()):
            scheduler_mod.scheduler.remove_job(job.id)
