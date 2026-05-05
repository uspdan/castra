# Operator handbook

A Day-1 / Day-2 guide for running siege-range in production. If
something breaks, jump to `docs/runbooks/`. If something needs
to be deployed for the first time, read this end-to-end.

## Day 1 — first deploy

### Prereqs

- Linux host with docker (`docker compose version 2.x`).
- Public DNS pointing at the host.
- Outbound TCP/443 to your inference / SMTP / OTel collector
  endpoints (if used).

### Bootstrap

```bash
git clone https://github.com/uspdan/seige-range
cd seige-range
cp .env.example .env
# Generate real secrets:
python -c "import secrets; print(secrets.token_hex(32))"  # SECRET_KEY
# Pick a strong ADMIN_PASSWORD (min 12 chars, no placeholder values).
# Edit .env: SECRET_KEY, ADMIN_PASSWORD, ALLOWED_ORIGINS,
# POSTGRES_PASSWORD. Optional: SMTP_*, MAIL_FROM, FRONTEND_URL,
# REQUIRE_EMAIL_VERIFIED, BACKUP_DIR, OTEL_EXPORTER_OTLP_ENDPOINT.
```

### TLS certificates

`scripts/generate_certs.sh` self-signs a CA + leaf for staging
in 30s. Production should drop in `fullchain.pem` + `privkey.pem`
from Let's Encrypt / cert-manager at the same paths
(`nginx/certs/`).

### Bring it up

```bash
make prod
```

Then run the smoke matrix from `docs/runbooks/prod-smoke.md`.

## Day 2 — keeping it running

### Monitoring

The API exposes:

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness — always 200 |
| `GET /readyz` | readiness — 200 only when DB+Redis+docker reachable |
| `GET /metrics` | Prometheus exposition (RED metrics, in-flight gauge) |

Load `docs/alerts/*.yml` into Prometheus. Each rule's
`runbook_url` annotation points at the recovery procedure.

### Logging

The API emits structured JSON to stdout via structlog. Ship to
your log aggregator (Loki, ELK, Datadog) via the standard docker
log driver. Key event names to dashboard:

| Event | What it means |
|---|---|
| `request` | Per-request log: method, path, status, duration, user_id |
| `audit_ledger.tamper_detected` | Hourly verify found a problem — page on this |
| `csp.violation` | A browser CSP violation was reported |
| `backup.failed` | Nightly DB backup didn't complete |
| `webhook.delivery.failure` | Outbound webhook failed (will retry) |
| `instance.cleanup_failed` | TTL reaper couldn't tear an instance down |

### Tracing (opt-in)

Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318` in `.env`
to ship spans to Tempo / Jaeger / Honeycomb. The platform
auto-instruments inbound FastAPI, SQLAlchemy queries, and
outbound `httpx` calls.

### Backups

The scheduler runs `pg_dump` nightly at 02:30 UTC against
`BACKUP_DIR` (default `/var/lib/siege-range/backups`). Files
older than `BACKUP_RETENTION_DAYS` (default 30) are pruned.

To disable in favour of an external backup system:

```ini
# .env
BACKUP_DIR=
```

To restore: see `docs/runbooks/db-restore.md`.

### Webhooks

Admins manage subscriptions in the web UI under
**Admin → Webhooks**. Events are delivered with HMAC-SHA256
signatures over the body (header `X-Siege-Signature`); failed
deliveries are retried with exponential backoff for 24 hours
then dropped.

### Per-instance egress

Challenges using the `egress-proxied` profile route through a
shared tinyproxy with a hot-reloaded allowlist. See
`docs/runbooks/egress-allowlist.md`.

The `egress-proxied-sidecar` profile spawns one tinyproxy per
challenge instance — preferred when allowlists shouldn't bleed
across challenges. The launcher handles the lifecycle.

### MFA + email gates

- `REQUIRE_EMAIL_VERIFIED=true` blocks login until the user
  clicks their verification link. Default off so existing users
  aren't locked out.
- MFA is opt-in per user via Settings → REDACTED. Recovery codes
  are shown once at enrol; admins can DB-reset
  `users.mfa_enabled=False` if a user loses both their phone
  and their recovery codes.

## Failure modes

When in doubt, the runbooks index at
`docs/runbooks/README.md` has the decision tree. Common ones:

| Symptom | First page |
|---|---|
| 5xx spike on a single route | `runbooks/rollback.md` |
| TTL reaper / leaderboard cache stuck | `runbooks/scheduler-stuck.md` |
| Schema corruption / data loss | `runbooks/db-restore.md` |
| Tinyproxy reload fails | `runbooks/egress-allowlist.md` |
| Audit ledger tamper page fires | `runbooks/db-restore.md` |
| Just deployed and want to verify | `runbooks/prod-smoke.md` |
| Operating an LLM honeypot | `runbooks/llm-honeypot-operator.md` |

## Upgrade procedure

1. `git fetch && git log --oneline HEAD..origin/main` — review
   what's incoming.
2. Skim the most recent `## Sprint N` section in `WORK_PLAN.md`
   for breaking-change notes.
3. `git pull`.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    build api dashboard egress-proxy`.
5. The api container's entrypoint runs `alembic upgrade head`
   automatically before launching uvicorn. Migrations are
   append-only per CLAUDE.md §13.
6. `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`.
7. Run `docs/runbooks/prod-smoke.md`.

If a migration fails halfway: the api container keeps restarting
and `/readyz` returns 503. Inspect with
`docker compose logs api --tail 200`. The migration is wrapped
in a transaction so partial state doesn't reach the DB. Roll
back per `docs/runbooks/rollback.md`.

## Secret rotation

`docs/runbooks/secret-rotation.md` covers `SECRET_KEY`,
`ADMIN_PASSWORD`, and `POSTGRES_PASSWORD` with copy-paste
commands. Rotate quarterly even when nothing has leaked.

## Where to find things

| | Path |
|---|---|
| App code | `backend/app/` |
| Migrations | `backend/migrations/versions/NNN_*.py` |
| Frontend | `frontend/src/` |
| Compose files | `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.dev.yml` |
| Nginx | `nginx/nginx.conf` |
| Runbooks | `docs/runbooks/` |
| ADRs | `docs/adr/` |
| Alert rules | `docs/alerts/` |
| Sprint history | `WORK_PLAN.md` |
