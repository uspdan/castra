# Runbook — Restore the database from a backup

## When to use

- Disk failure / volume corruption
- Catastrophic migration that downgrade can't undo
- Audit ledger tampering (`python -m app.tools.audit_verify` exits 1)
- Deliberate operator action (e.g. competition reset)

## Prerequisites

- A recent backup — from **either** source below.
- Service window communicated to users (the API will be down ~5 min).

## Two backup sources — know which you have

There are two, and they land in different places. Check both before
concluding you have nothing to restore from.

| Source | Trigger | Location | Format |
|---|---|---|---|
| `scripts/backup.sh` | manual, on the host | `backups/` in the repo | `.tar.gz` |
| Scheduler `nightly_db_backup` | 02:30 UTC daily | `backup_data` volume, at `/var/lib/siege-range/backups` inside `api` | `siege-<ts>.sql.gz` (plain `pg_dump`) |

The step-by-step below covers the **manual tarball**. For the nightly
dump, see "Restoring from a nightly dump" at the end.

> **Check the automated backups are actually working.** They failed
> silently for an extended period — `pg_dump` was missing from the api
> image, and APScheduler still logged the job as "executed
> successfully" because the job swallows dump failures by design.
> The quick check:
>
> ```bash
> docker compose exec api ls -la /var/lib/siege-range/backups
> curl -s localhost:8000/metrics | grep siege_backup_last_success
> ```
>
> A `siege_backup_last_success_timestamp_seconds` of `0`, or an empty
> directory, means there is no automated backup to restore from.
> `docs/alerts/backup.rules.yml` alerts on exactly this.

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

---

## Restoring from a nightly dump

The scheduler's dumps are plain `pg_dump` output, gzipped — no tarball,
no wrapper script. Restore is a straight `psql` replay.

The procedure below was executed end-to-end against a live dump and
verified by row-count comparison; the numbers in step 4 are what a
correct restore looks like.

### 1. Find the dump

```bash
docker compose exec api ls -la /var/lib/siege-range/backups
# siege-20260731T134109Z.sql.gz
```

Pick the newest file dated **before** the failure window.

### 2. Stop the API so nothing writes mid-restore

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop api
```

Leave `db` running — you need it to accept the restore.

### 3. Replay into a scratch database first

Never restore straight over the live database. Prove the dump is good
first; a truncated or partial dump looks like a file either way.

```bash
DUMP=siege-20260731T134109Z.sql.gz

docker compose exec db psql -U siege -d postgres \
  -c "DROP DATABASE IF EXISTS restore_probe;" \
  -c "CREATE DATABASE restore_probe;"

docker compose exec api sh -lc "gunzip -c /var/lib/siege-range/backups/$DUMP" \
  | docker compose exec -T db psql -U siege -d restore_probe -v ON_ERROR_STOP=1 -q
```

`ON_ERROR_STOP=1` matters — without it `psql` reports success after
skipping failed statements.

### 4. Verify the scratch restore before committing to it

```bash
docker compose exec db psql -U siege -d restore_probe -tAc "
  select 'users='||(select count(*) from users)
      || ' challenges='||(select count(*) from challenges)
      || ' solves='||(select count(*) from solves)
      || ' audit_ledger='||(select count(*) from audit_ledger)
      || ' tables='||(select count(*) from information_schema.tables
                      where table_schema='public');"
```

Expect ~21 tables and row counts in the right order of magnitude for
your deployment. Then confirm the audit ledger survived intact:

```bash
docker compose exec db psql -U siege -d restore_probe -tAc \
  "select count(*) from audit_ledger where this_hash is null or prev_hash is null;"
# must be 0
```

If either check looks wrong, **stop** and try an older dump.

### 5. Promote the scratch database

```bash
docker compose exec db psql -U siege -d postgres \
  -c "ALTER DATABASE siege_range RENAME TO siege_range_broken;" \
  -c "ALTER DATABASE restore_probe RENAME TO siege_range;"
```

Renaming rather than dropping keeps the bad database available for
diagnosis. Drop `siege_range_broken` once you're satisfied.

### 6. Bring the API back and verify

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api
docker compose exec api python -m app.tools.audit_verify   # must exit 0
```

Then follow steps 6–7 of the tarball procedure above (row-count sanity
check, harness run against `examples/`).

### Cleanup

```bash
docker compose exec db psql -U siege -d postgres -c "DROP DATABASE restore_probe;"
```
