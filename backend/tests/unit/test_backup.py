"""Sprint 12 Phase A — DB backup helper.

The real ``pg_dump`` invocation is exercised in operations
(``make backup``); these tests cover the URL parsing, prune
logic, and the no-op / error paths without spawning a real
subprocess.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.backup import _parse_async_url, _prune, run_backup


# ---------------------------------------------------------------------------
# _parse_async_url
# ---------------------------------------------------------------------------
class TestParseAsyncUrl:
    def test_strips_asyncpg_driver(self):
        env = _parse_async_url(
            "postgresql+asyncpg://siege:secret@db:5432/siege_range"
        )
        assert env["PGUSER"] == "siege"
        assert env["PGPASSWORD"] == "secret"
        assert env["PGHOST"] == "db"
        assert env["PGPORT"] == "5432"
        assert env["PGDATABASE"] == "siege_range"

    def test_no_password(self):
        env = _parse_async_url("postgresql://anon@db/x")
        assert "PGPASSWORD" not in env
        assert env["PGUSER"] == "anon"


# ---------------------------------------------------------------------------
# _prune
# ---------------------------------------------------------------------------
class TestPrune:
    def test_drops_old_files(self, tmp_path: Path):
        old = tmp_path / "siege-old.sql.gz"
        new = tmp_path / "siege-new.sql.gz"
        old.write_bytes(b"old")
        new.write_bytes(b"new")
        # Backdate ``old`` to 60 days ago.
        backdated = (datetime.now(timezone.utc) - timedelta(days=60)).timestamp()
        import os
        os.utime(old, (backdated, backdated))

        pruned = _prune(tmp_path, retention_days=30)
        assert pruned == 1
        assert not old.exists()
        assert new.exists()

    def test_ignores_non_matching_files(self, tmp_path: Path):
        unrelated = tmp_path / "something-else.tar.gz"
        unrelated.write_bytes(b"x")
        # Backdate.
        import os
        backdated = (datetime.now(timezone.utc) - timedelta(days=60)).timestamp()
        os.utime(unrelated, (backdated, backdated))

        pruned = _prune(tmp_path, retention_days=30)
        assert pruned == 0
        assert unrelated.exists()


# ---------------------------------------------------------------------------
# run_backup
# ---------------------------------------------------------------------------
class TestRunBackup:
    @pytest.mark.asyncio
    async def test_disabled_when_dir_empty(self):
        result = await run_backup(
            database_url="postgresql+asyncpg://x@y/z",
            backup_dir="",
            retention_days=30,
        )
        assert result.ok is True
        assert result.error == "disabled"

    @pytest.mark.asyncio
    async def test_pg_dump_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "app.services.backup.shutil.which", lambda _name: None
        )
        result = await run_backup(
            database_url="postgresql+asyncpg://x@y/z",
            backup_dir=str(tmp_path),
            retention_days=30,
        )
        assert result.ok is False
        assert "pg_dump" in (result.error or "")

    @pytest.mark.asyncio
    async def test_subprocess_success(self, tmp_path, monkeypatch):
        # Fake the pg_dump | gzip pipeline by writing the target
        # file ourselves and returning rc=0.
        out_files: list[Path] = []

        async def _fake_create_subprocess_shell(cmd, **kwargs):
            # Extract target path from the cmd: "pg_dump ... | gzip -c > '<path>'"
            target = cmd.split("> '")[-1].rstrip("'")
            Path(target).write_bytes(b"--fake-dump--")
            out_files.append(Path(target))
            proc = MagicMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            return proc

        monkeypatch.setattr(
            "app.services.backup.shutil.which", lambda _name: "/usr/bin/pg_dump"
        )
        monkeypatch.setattr(
            "app.services.backup.asyncio.create_subprocess_shell",
            _fake_create_subprocess_shell,
        )

        result = await run_backup(
            database_url="postgresql+asyncpg://siege:secret@db:5432/siege_range",
            backup_dir=str(tmp_path),
            retention_days=30,
        )
        assert result.ok is True
        assert result.path is not None
        assert result.path.exists()
        assert result.bytes_written > 0
        assert result.path.name.startswith("siege-")
        assert result.path.suffix == ".gz"

    @pytest.mark.asyncio
    async def test_subprocess_failure_cleans_partial_file(
        self, tmp_path, monkeypatch
    ):
        async def _fake_create_subprocess_shell(cmd, **kwargs):
            target = cmd.split("> '")[-1].rstrip("'")
            Path(target).write_bytes(b"partial")
            proc = MagicMock()
            proc.returncode = 1
            proc.communicate = AsyncMock(
                return_value=(b"", b"connection refused")
            )
            return proc

        monkeypatch.setattr(
            "app.services.backup.shutil.which", lambda _name: "/usr/bin/pg_dump"
        )
        monkeypatch.setattr(
            "app.services.backup.asyncio.create_subprocess_shell",
            _fake_create_subprocess_shell,
        )

        result = await run_backup(
            database_url="postgresql+asyncpg://siege:secret@db:5432/siege_range",
            backup_dir=str(tmp_path),
            retention_days=30,
        )
        assert result.ok is False
        # Partial file deleted on failure.
        assert list(tmp_path.glob("siege-*.sql.gz")) == []
        assert "connection refused" in (result.error or "")
