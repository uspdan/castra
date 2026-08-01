"""The backup job must leave an observable trace.

``nightly_db_backup`` never raises — a failed dump must not take the
scheduler down with it. The cost of that design is that APScheduler
logs ``Job "nightly_db_backup" executed successfully`` even when the
dump failed, so job-level monitoring shows green on a broken backup.
That is how a missing ``pg_dump`` survived unnoticed.

The heartbeat gauge is what makes the failure visible, so these tests
pin its semantics — in particular that it does *not* advance on a run
that produced no dump.

**``app.*`` is imported lazily here, never at module scope.**
``tests/conftest.py`` starts the Postgres/Redis testcontainers and only
then lets app modules load, so ``get_settings()`` caches the container
URLs. Importing ``app.services.scheduler`` at collection time populates
that cache with the compose defaults (``redis://redis:6379/0``) instead,
and every later test that resolves a hostname dies with "Temporary
failure in name resolution". Four integration tests did exactly that
before these imports were moved inside fixtures.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml


_REPO_ROOT = Path(__file__).resolve().parents[3]
_RULES = _REPO_ROOT / "docs" / "alerts" / "backup.rules.yml"


def _read(metric) -> float:
    return metric._value.get()


class _NoDbSession:
    """Stand-in for ``async_session`` so these stay unit tests.

    The failure branch of ``nightly_db_backup`` opens a real session to
    write the admin notification. Letting it through would build a
    SQLAlchemy engine from this module's fake DATABASE_URL, and that
    engine is cached process-wide.
    """

    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *exc_info):
        return False


@pytest.fixture
def sched(_bootstrap_env, monkeypatch):
    """The scheduler module, imported lazily and detached from the DB.

    Depends on ``_bootstrap_env`` even though nothing here touches the
    database: that fixture is what points DATABASE_URL/REDIS_URL at the
    testcontainers and clears the settings cache. Importing the
    scheduler pulls in ``app.database``, which builds its engine at
    module scope — do that first and the engine is stuck on the compose
    default ``db:5432`` for the rest of the session.
    """

    from app.services import scheduler

    monkeypatch.setattr(scheduler, "async_session", lambda: _NoDbSession())
    return scheduler


@pytest.fixture
def settings(monkeypatch):
    cfg = SimpleNamespace(
        BACKUP_DIR="/var/lib/siege-range/backups",
        BACKUP_RETENTION_DAYS=30,
        DATABASE_URL="postgresql+asyncpg://u:p@db:5432/siege",
    )
    monkeypatch.setattr("app.config.get_settings", lambda: cfg)
    return cfg


def _result(**kwargs):
    from app.services.backup import BackupResult

    return BackupResult(**kwargs)


def _stub_run_backup(monkeypatch, result) -> None:
    monkeypatch.setattr(
        "app.services.backup.run_backup", AsyncMock(return_value=result)
    )


class TestBackupHeartbeat:
    async def test_success_advances_the_heartbeat(
        self, sched, settings, monkeypatch
    ):
        before = _read(sched.BACKUP_LAST_SUCCESS)
        _stub_run_backup(
            monkeypatch,
            _result(ok=True, path="/tmp/x.sql.gz", bytes_written=4096),
        )

        await sched.nightly_db_backup()

        assert _read(sched.BACKUP_LAST_SUCCESS) > before
        assert _read(sched.BACKUP_BYTES) == 4096

    async def test_failure_does_not_advance_the_heartbeat(
        self, sched, settings, monkeypatch
    ):
        # The whole point: a failed run must leave the heartbeat stale so
        # SiegeBackupStale fires, rather than looking like a fresh backup.
        sched.BACKUP_LAST_SUCCESS.set(1000.0)
        failures_before = _read(sched.BACKUP_FAILURES)
        _stub_run_backup(
            monkeypatch,
            _result(ok=False, error="'pg_dump' not found on PATH"),
        )
        monkeypatch.setattr(
            "app.services.notifications.create_notification", AsyncMock()
        )

        await sched.nightly_db_backup()

        assert _read(sched.BACKUP_LAST_SUCCESS) == 1000.0
        assert _read(sched.BACKUP_FAILURES) == failures_before + 1

    async def test_opted_out_run_does_not_advance_the_heartbeat(
        self, sched, settings, monkeypatch
    ):
        # BACKUP_DIR empty means the operator opted out. ``run_backup``
        # reports ok=True for that, but no dump exists — advancing the
        # heartbeat would silence the alert for the one configuration
        # where there is definitively nothing to restore from.
        sched.BACKUP_LAST_SUCCESS.set(2000.0)
        _stub_run_backup(monkeypatch, _result(ok=True, error="disabled"))

        await sched.nightly_db_backup()

        assert _read(sched.BACKUP_LAST_SUCCESS) == 2000.0

    async def test_empty_backup_dir_short_circuits(
        self, sched, settings, monkeypatch
    ):
        settings.BACKUP_DIR = "   "
        sched.BACKUP_LAST_SUCCESS.set(3000.0)
        called = AsyncMock()
        monkeypatch.setattr("app.services.backup.run_backup", called)

        await sched.nightly_db_backup()

        called.assert_not_awaited()
        assert _read(sched.BACKUP_LAST_SUCCESS) == 3000.0


class TestHeartbeatSeeding:
    """The gauge must survive a restart, or it cries wolf every deploy.

    ``BACKUP_LAST_SUCCESS`` lives in the process. Without seeding it
    from disk at startup it resets to 0 on every restart, so
    SiegeBackupStale fires after each deploy and stays firing until the
    next 02:30 run — and an alert that is wrong daily gets muted.
    """

    def test_seeds_from_the_newest_dump_on_disk(
        self, sched, tmp_path, monkeypatch
    ):
        import os

        old = tmp_path / "siege-20260101T000000Z.sql.gz"
        new = tmp_path / "siege-20260102T000000Z.sql.gz"
        old.write_bytes(b"x" * 10)
        new.write_bytes(b"y" * 4096)
        os.utime(old, (1000, 1000))
        os.utime(new, (9000, 9000))

        monkeypatch.setattr(
            "app.config.get_settings",
            lambda: SimpleNamespace(BACKUP_DIR=str(tmp_path)),
        )
        sched.BACKUP_LAST_SUCCESS.set(0)

        sched.seed_backup_heartbeat()

        assert _read(sched.BACKUP_LAST_SUCCESS) == 9000
        assert _read(sched.BACKUP_BYTES) == 4096

    def test_leaves_gauge_at_zero_when_no_dumps_exist(
        self, sched, tmp_path, monkeypatch
    ):
        # Zero is the sentinel SiegeBackupNeverSucceeded keys on, so an
        # empty directory must NOT be seeded with anything else.
        monkeypatch.setattr(
            "app.config.get_settings",
            lambda: SimpleNamespace(BACKUP_DIR=str(tmp_path)),
        )
        sched.BACKUP_LAST_SUCCESS.set(0)

        sched.seed_backup_heartbeat()

        assert _read(sched.BACKUP_LAST_SUCCESS) == 0

    def test_never_raises_on_a_bad_backup_dir(self, sched, monkeypatch):
        # Startup must not be blocked by an unreadable path.
        monkeypatch.setattr(
            "app.config.get_settings",
            lambda: SimpleNamespace(BACKUP_DIR="/nonexistent/nope"),
        )
        sched.seed_backup_heartbeat()


class TestAlertRules:
    """Rules are only useful if they name metrics we actually emit."""

    @pytest.fixture(scope="class")
    def exprs(self) -> list[str]:
        rules = yaml.safe_load(_RULES.read_text(encoding="utf-8"))
        return [r["expr"] for g in rules["groups"] for r in g["rules"]]

    def test_rules_reference_emitted_metric_names(self, exprs):
        joined = " ".join(exprs)
        emitted = {
            "siege_backup_last_success_timestamp_seconds",
            "siege_backup_failures_total",
            "siege_backup_last_size_bytes",
        }
        missing = {name for name in emitted if name not in joined}
        assert not missing, (
            f"{missing} are exported by the scheduler but referenced by no "
            "rule — an unmonitored metric is just overhead"
        )

    def test_no_rule_uses_absent(self, exprs):
        # Regression guard: prometheus_client registers these gauges at
        # import, so a sample always exists once the api is up and
        # ``absent()`` can never fire. The never-succeeded case has to
        # key on the zero sentinel instead.
        assert not any("absent(" in e for e in exprs), (
            "absent() can never fire for an always-registered gauge"
        )
