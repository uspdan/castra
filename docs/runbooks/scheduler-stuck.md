# Runbook — Scheduler stuck / not firing

## Symptoms

One or more of:

- Expired challenge instances aren't getting cleaned up (look in
  `docker compose ps` — old `siege-<user>-<slug>-…` containers
  past their TTL still running).
- Webhook deliveries stuck in `timeout` / `network_error` status
  past the 30s/60s/120s/240s/480s retry window with no
  `attempt=N+1` row appearing.
- Leaderboard cache stale (Redis key `siege:leaderboard:*` has no
  recent expiry).
- Old `notifications` rows past the 30-day cutoff still present.

## Background

Sprint 1 leaves four scheduler jobs:

| Job | Cadence | What it does |
|---|---|---|
| `cleanup_expired` | every 5min | TTL reaper for expired instances |
| `cache_leaderboard` | every 60s | Top-50 leaderboard → Redis cache |
| `notification_cleanup` | daily 03:00 | Drop notifications > 30 days |
| `webhook_retry` | every 1min | Sweep retriable webhook failures |
| `webhook_prune` | daily 04:00 | Drop deliveries > 30 days |

All run inside the api container's `AsyncIOScheduler`. If the api
process is up but the scheduler isn't firing, something inside the
process is wedged.

## Diagnosis

### 1. Confirm the scheduler started

```bash
docker compose logs api | grep -i "Scheduler started"
```

Expect one line per api worker (default `UVICORN_WORKERS=4`). If
you see zero lines, the lifespan never reached `setup_scheduler()`
— check earlier in the logs for tracebacks during boot.

### 2. Check the scheduler's own job list

There's no admin endpoint that exposes this today. The cheapest probe
is to attach a debugger to a worker, but it's faster to just restart
the api process and watch the next cycle.

### 3. Look for a swallowed exception in a job

The jobs all wrap their work in `try/except` and log via structlog:

```bash
docker compose logs api | grep -E "cleanup_expired|webhook_retry|webhook_prune|cleanup_notifications" | tail -20
```

A job that's been throwing every cycle for hours will show up here.

## Fixes

### Fix A — Stuck process

Most common: a worker is wedged on a database call (e.g. blocked on
a row-level lock).

```bash
# Identify the wedged worker:
docker compose top api

# Restart the api (rolls all workers):
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    restart api
```

The scheduler comes back in <10 seconds. Verify:

```bash
docker compose logs -f api | grep -i "Scheduler started"
```

### Fix B — Jobs silently failing

If logs show repeated job failures:

1. Identify the offending job from the log line.
2. Run the job's helper directly to see the error:

   ```bash
   docker compose exec api python <<'PY'
   import asyncio
   from app.services.scheduler import retry_failed_webhooks
   asyncio.run(retry_failed_webhooks())
   PY
   ```

3. Common causes:
   - DB transaction left in an aborted state (look for
     `psycopg2.errors.InFailedSqlTransaction`).
   - Redis unreachable (check `docker compose logs redis`).
   - docker-socket-proxy ACL too tight (404 on a kill / list call).

### Fix C — DST / clock skew

apscheduler uses the host's clock. If host time jumped, jobs may be
"in the future" and not fire.

```bash
docker compose exec api date
date
```

If they disagree, fix host NTP and restart api.

## After action

- Capture the stuck condition in the incident tracker.
- If a specific job is repeatedly the culprit, file a backend issue
  to add an explicit timeout / circuit breaker around it.
- Verify the scheduler is firing for the next two cycles before
  considering the incident closed.

## Estimated time

5–15 minutes. Most cases resolve with an api restart.
