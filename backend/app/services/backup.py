"""Automated DB backups.

Sprint 12 Phase A. The scheduler invokes :func:`run_backup`
nightly. The function:

1. Resolves ``settings.BACKUP_DIR``; if empty, returns a no-op
   result (operator opted out — perhaps an external backup
   system handles it).
2. Builds a ``pg_dump`` subprocess against
   ``settings.DATABASE_URL``. Output is gzipped to
   ``siege-{utc-iso}.sql.gz`` under ``BACKUP_DIR``.
3. Prunes any ``siege-*.sql.gz`` files older than
   ``settings.BACKUP_RETENTION_DAYS`` from ``BACKUP_DIR``.

A run produces a structured JSON log line via structlog so
log-shippers can dashboard the success / failure / size /
duration. Failures don't crash the scheduler — the operator
sees the WARN log + a global ``Notification(type="backup_failed")``
on the admin drawer.

Tests stub the subprocess so we never spawn a real ``pg_dump``;
the integration test only exercises the pruning logic against a
temp directory.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import structlog


logger = structlog.get_logger()


_BACKUP_FILENAME_GLOB = "siege-*.sql.gz"


@dataclass(frozen=True)
class BackupResult:
    ok: bool
    path: Optional[Path] = None
    bytes_written: int = 0
    duration_s: float = 0.0
    pruned_count: int = 0
    error: Optional[str] = None


def _parse_async_url(url: str) -> dict[str, str]:
    """Strip the SQLAlchemy ``+asyncpg`` driver suffix and pull
    out the libpq fields ``pg_dump`` needs as env vars.

    Input: ``postgresql+asyncpg://user:pw@host:5432/dbname``
    Output: ``{"PGUSER": ..., "PGPASSWORD": ..., "PGHOST": ...,
              "PGPORT": ..., "PGDATABASE": ...}``.
    """

    plain = url.replace("+asyncpg", "")
    p = urlparse(plain)
    out = {
        "PGHOST": p.hostname or "localhost",
        "PGPORT": str(p.port) if p.port else "5432",
        "PGDATABASE": (p.path or "/").lstrip("/") or "postgres",
    }
    if p.username:
        out["PGUSER"] = p.username
    if p.password:
        out["PGPASSWORD"] = p.password
    return out


def _prune(dir_path: Path, retention_days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    pruned = 0
    for f in dir_path.glob(_BACKUP_FILENAME_GLOB):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                f.unlink()
                pruned += 1
            except OSError as exc:
                logger.warning(
                    "backup.prune_failed",
                    path=str(f),
                    error=f"{type(exc).__name__}: {exc}",
                )
    return pruned


async def run_backup(
    *,
    database_url: str,
    backup_dir: str,
    retention_days: int,
    pg_dump_path: str = "pg_dump",
) -> BackupResult:
    """Run pg_dump → gzip into ``backup_dir`` and prune old files.

    Returns a :class:`BackupResult` describing the outcome. Never
    raises — the scheduler caller logs + notifies on
    ``ok=False``.
    """

    if not backup_dir:
        return BackupResult(ok=True, error="disabled")

    target_dir = Path(backup_dir)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return BackupResult(
            ok=False, error=f"mkdir failed: {type(exc).__name__}: {exc}"
        )

    if shutil.which(pg_dump_path) is None:
        return BackupResult(
            ok=False, error=f"{pg_dump_path!r} not found on PATH"
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = target_dir / f"siege-{timestamp}.sql.gz"

    env = os.environ.copy()
    env.update(_parse_async_url(database_url))

    started = datetime.now(timezone.utc)
    try:
        # ``pg_dump`` writes SQL to stdout; we shell-pipe to gzip
        # via a single ``sh -c`` so we don't need a Python gzip
        # buffer for multi-GB dumps. The double quotes around
        # the path are safe — ``out_path`` is built from ASCII
        # timestamp.
        cmd = (
            f"{pg_dump_path} --no-owner --no-privileges "
            f"| gzip -c > '{out_path}'"
        )
        proc = await asyncio.create_subprocess_shell(
            cmd,
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
    except (OSError, asyncio.CancelledError) as exc:
        return BackupResult(
            ok=False, error=f"subprocess error: {type(exc).__name__}: {exc}"
        )

    duration = (datetime.now(timezone.utc) - started).total_seconds()

    if proc.returncode != 0:
        # Clean up the partial file so it can't be confused for a
        # good backup later.
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass
        return BackupResult(
            ok=False,
            duration_s=duration,
            error=(stderr.decode("utf-8", errors="replace")[-500:] or "exit-nonzero"),
        )

    size = out_path.stat().st_size if out_path.exists() else 0
    pruned = _prune(target_dir, retention_days)

    logger.info(
        "backup.completed",
        path=str(out_path),
        bytes=size,
        duration_s=round(duration, 2),
        pruned=pruned,
    )
    return BackupResult(
        ok=True,
        path=out_path,
        bytes_written=size,
        duration_s=duration,
        pruned_count=pruned,
    )


__all__ = ["BackupResult", "run_backup"]
