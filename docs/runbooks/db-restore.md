# Runbook — Restore the database from a backup

## When to use

- Disk failure / volume corruption
- Catastrophic migration that downgrade can't undo
- Audit ledger tampering (`python -m app.tools.audit_verify` exits 1)
- Deliberate operator action (e.g. competition reset)

## Prerequisites

- A recent backup tarball under `backups/` (see `backup.sh`).
- Service window communicated to users (the API will be down ~5 min).

## Step-by-step

### 1. Snapshot the current state (safety belt)

Even when you're sure the current DB is bad, take a snapshot before
overwriting it. You'll thank yourself later when the diagnosis turns
out to be wrong.

```bash
bash scripts/backup.sh
# Note the created file:
ls -la backups/ | head -3
```

### 2. Stop the API + scheduler so nothing writes during restore

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop api
```

Leave `db` and `redis` running.

### 3. Identify the backup to restore

```bash
ls -la backups/
# Pick the newest file BEFORE the failure window:
BACKUP_FILE=backups/siege-backup-2026-05-02.tar.gz
```

### 4. Run the restore script

```bash
bash scripts/restore.sh "${BACKUP_FILE}"
```

The script:

- Drops and recreates the `siege_range` database.
- Restores the dump.
- Re-applies any alembic migrations newer than the backup
  (`alembic upgrade head` runs as part of api boot).

### 5. Bring the API back up

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml start api
```

The api's entrypoint runs `alembic upgrade head` automatically before
uvicorn starts (Sprint 1 change). Watch the logs:

```bash
docker compose logs -f api | head -30
```

You should see:

```
[entrypoint] running alembic upgrade head
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade …
[entrypoint] migrations applied; exec 'uvicorn …'
```

### 6. Verify

```bash
curl -fsS https://localhost/healthz
curl -fsS https://localhost/readyz

# Confirm row counts make sense:
docker compose exec db psql -U siege siege_range -c \
    "SELECT count(*) FROM users;"
docker compose exec db psql -U siege siege_range -c \
    "SELECT count(*) FROM challenges;"

# Re-run the audit ledger verifier:
docker compose exec api python -m app.tools.audit_verify
```

The verifier must exit `0`. If it exits `1`, the restored backup is
also tampered — go further back.

### 7. Re-run the harness against examples

```bash
make test-challenges
```

Should pass 9/9 if the schema + data are healthy.

## What about Redis?

Redis is for ephemeral state (rate limit counters, lockouts,
leaderboard cache). The restore intentionally does NOT restore it —
the cache rebuilds itself within 60s. Leaderboard cache is rebuilt by
the scheduler's `cache_leaderboard` job.

If you need to clear Redis explicitly (rare):

```bash
docker compose exec redis redis-cli FLUSHDB
```

## Estimated time

**~10 minutes** for an in-place restore on a healthy host.
**~30 minutes** if the volume itself is corrupted and needs recreating.

## After action

- File the cause (disk failure, bad migration, operator error) in
  your incident tracker.
- If this was a corruption from a buggy release, update
  `rollback.md` so the next operator catches it earlier.
- Verify your backup cadence is still healthy (`ls -lt backups/`
  should show daily files).
