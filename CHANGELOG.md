# Changelog

All notable changes to this project are documented here in
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.
Each entry summarises the user- and operator-facing surface changes
for one in-session sprint; per-commit detail lives in `git log`,
per-sprint detail lives in `WORK_PLAN.md`.

## [Unreleased]

Phase 0–12 hardening program + Sprints 1–12 in-session work
shipped. No version tagged yet — `git rev-parse HEAD` is the
canonical reference.

### Sprint 12 — 2026-05-05
#### Added
- Nightly automated DB backup scheduler job (`pg_dump | gzip`)
  with retention pruning. New env vars `BACKUP_DIR`,
  `BACKUP_RETENTION_DAYS`. Failures surface as a global
  Notification visible in the admin drawer.
- `POST /csp-report` endpoint that accepts browser CSP violation
  reports (both `report-uri` and `report-to` shapes), logs them
  as structured `csp.violation` JSON. CSP header now carries
  `report-uri /csp-report`.
- Operator handbook (`docs/operator-handbook.md`) covering
  Day-1 deploy and Day-2 ops.
- Author handbook (`docs/author-handbook.md`) covering manifest
  authoring, profile cheat-sheet, flag-type matrix, image
  digest pinning, authoring checklist.

### Sprint 11 — 2026-05-05
#### Added
- Prometheus alert rules at `docs/alerts/api.rules.yml` and
  `docs/alerts/audit.rules.yml`. Each rule carries a
  `runbook_url` annotation. Covers 5xx rate, p99 SLO, in-flight
  saturation, `up` liveness, audit-verify staleness, audit
  tamper count.
- Reference LLM honeypot container at
  `examples/challenges/llm-customer-pii/container/` —
  Dockerfile + FastAPI service that forwards prompts to a
  configurable inference endpoint with PII-leak system prompt.
- OpenTelemetry tracing (opt-in via
  `OTEL_EXPORTER_OTLP_ENDPOINT`). Auto-instruments FastAPI,
  SQLAlchemy, httpx. New deps:
  `opentelemetry-{api,sdk,exporter-otlp-proto-http}` and
  `opentelemetry-instrumentation-{fastapi,sqlalchemy,httpx}`.
- Audit-verify heartbeat gauge + tamper-finding counter so
  `audit.rules.yml` can fire correctly.

### Sprint 10 — 2026-05-05
#### Added
- Prometheus `/metrics` endpoint with the RED triad per route
  template (counter, latency histogram, in-flight gauge). New
  dep: `prometheus-client==0.20.0`.
- Hourly audit-ledger tamper-detection scheduler job. Failures
  emit a global `Notification(type="audit_tamper")` and a
  structured `ERROR` log line.
- `REQUIRE_EMAIL_VERIFIED` config flag (default off). When on,
  login returns 403 for users with `email_verified=False`.
- Redis-backed scoreboard cache with 60s TTL. Graceful
  degradation: any Redis failure logs WARN and falls through
  to live computation.

### Sprint 9 — 2026-05-05
#### Added
- Challenge author form in the Admin UI (modal for create +
  edit) backed by a new `GET /api/v1/admin/challenges/{slug}`
  detail endpoint that exposes docker fields the public
  catalogue hides.
- Email verification: `users.email_verified` column +
  `email_verification_tokens` table (24h TTL),
  `POST /api/v1/auth/{verify-email,resend-verification}`,
  `/verify-email` page, `Settings → Email` section.
  Register flow now best-effort sends a verification link.
- AI/LLM honeypot category implementation (ADR 0001):
  `app/validators/llm_signal.py`, `llm-sandbox` container
  profile, `LlmSignalFlag` in the spec, JSON schema
  regenerated, reference manifest at
  `examples/challenges/llm-customer-pii/`,
  `docs/runbooks/llm-honeypot-operator.md`.

### Sprint 8 — 2026-05-04
#### Added
- Webhooks tab in the Admin UI: subscription CRUD with
  one-time secret reveal, inline delivery viewer with replay.
- Audit log pagination + action / user filters in the Admin UI.
- System tab now wired to real `/admin/system` + `/readyz` data
  (was hardcoded "ok" tiles).
- Webhook event vocabulary picks up the 11 new audit event
  types added in Sprints 6 + 7.

### Sprint 7 — 2026-05-04
#### Added
- Account settings page (`/settings`) with Profile, Email,
  Password, MFA, and Data sections.
- `POST /api/v1/auth/change-password` and
  `PATCH /api/v1/auth/profile`.
- GDPR endpoints: `GET /api/v1/me/data` (Article 15 export) +
  `DELETE /api/v1/me` (Article 17 anonymisation; audit ledger
  immutability preserved).
- TOTP MFA + recovery codes. Migration 012 adds
  `users.{mfa_secret,mfa_enabled}` and `mfa_recovery_codes`.
  Four new endpoints: `mfa/{enroll,confirm,disable,verify}`.
  Login returns `MfaPendingResponse` for MFA-enabled users; the
  client exchanges the pending token via `/mfa/verify`.
- New runtime dep: `pyotp==2.9.0`.

### Sprint 6 — 2026-05-04
#### Added
- Notifications WebSocket fan-out: every `Notification` row
  creation now publishes a `{type:"notification"}` event the
  frontend `NotificationDropdown` consumes live.
- Password reset flow: `password_reset_tokens` table
  (sha256-at-rest, 1h TTL),
  `POST /api/v1/auth/{forgot-password,reset-password}`, two
  new pages on the frontend, `services/email.py` with three
  modes (production aiosmtplib / dev stderr / test capture).
- New runtime dep: `aiosmtplib==3.0.1`.
- ADR 0001 (AI honeypot category, status: Proposed).
- Production smoke runbook (`docs/runbooks/prod-smoke.md`).
- CI workflow files moved from `.github/workflows/` to
  `docs/ci-templates/` while GitHub Actions is disabled.

### Sprint 5 — 2026-05-03
#### Added
- Full Playwright lifecycle suite for the InstancePanel
  (LAUNCH → STOP and LAUNCH → RESET → port-changes), 3 specs.
  Skips cleanly when docker isn't available on the runner.

### Sprint 4 — 2026-05-03
#### Added
- Scheduler + ws_manager modules into the backend coverage
  gate. 27 new tests; both modules at 93% / 94% coverage.
- (Dead) GitHub Actions docker-images workflow template
  building `siege-egress-sidecar:latest`.

### Sprint 3 — 2026-05-03
#### Added
- v1 auth surface: `/api/v1/auth/{register,login,refresh,logout,me}`
  with locked DTOs.
- v1 leaderboard endpoints: `/api/v1/leaderboard/{teams,weekly}`.
- v1 admin write surface:
  `POST/PUT/DELETE /api/v1/admin/challenges`,
  `PUT /api/v1/admin/users/{id}`, `POST /api/v1/admin/seed`,
  `POST /api/v1/admin/challenges/{slug}/flags` (multi-flag
  authoring).
- Tinyproxy hot-reload pipeline wired into compose: shared
  `egress_filter` volume + `EGRESS_FILTER_PATH` env on api +
  egress-proxy entrypoint that touches the filter file on
  cold start.
- Per-instance egress-proxy sidecar profile
  (`egress-proxied-sidecar`) with new
  `services/orchestration/sidecar.py` + `users.sidecar_container_id`
  column (migration 009).
- Frontend Playwright tests for InstancePanel + ChallengeProgress.
- 412-prereqs hint UI: structured `detail.missing_slugs` from
  `/api/v1/challenges/{slug}/submit`; FlagSubmission renders
  the prereq list.
- Lifted instance into `instanceStore.byChallenge` so RESET
  reflects without a parent refetch.
- Legacy router modules (admin, competitions, health,
  instances, leaderboard, notifications, stats, writeups)
  added to the coverage gate. Fixed pre-existing
  `Writeup(title=…)` ORM bug along the way (migration 010).

### Sprint 2 — 2026-05-02 (Phase 12 follow-on)
#### Added
- Toast system, instance lifecycle panel, multi-flag progress
  strip — closes the broken-user-flow gaps surfaced in the
  ship-readiness review.

### Sprint 1 — 2026-05-02 (Phase 12 follow-on)
#### Added
- Backend pytest CI workflow (`.github/workflows/backend-tests.yml`).
- Alembic-on-boot via `backend/entrypoint.sh` (TCP-probes
  Postgres + runs `alembic upgrade head` before exec'ing
  uvicorn).
- Resource limits + image-digest discipline in
  `docker-compose.prod.yml`.
- TLS termination + HSTS / Permissions-Policy in `nginx.conf`.
- Critical runbooks: rollback, db-restore, secret-rotation,
  scheduler-stuck.

### Phase 12 — 2026-05-02
#### Added
- Locked public API v1 surface (`/api/v1/*`): scoreboard, ATT&CK
  coverage, `me`, challenges catalogue, hint unlock, flag
  submit, multi-flag progress, webhook subscriptions, webhook
  delivery history + replay, attack-coverage roll-up.
- Outbound webhook system (admin-managed via v1) with HMAC
  signing, exponential-backoff retry, retention prune.
- 21 in-session slices total — see `WORK_PLAN.md` for the
  per-slice breakdown.

### Phases 0–11 — 2026-05-01 to 2026-05-02
Hardening program: Pydantic schema wiring, hash-chained audit
ledger, secret fail-fast / CORS / security headers, `/readyz`
with dep probes, test infrastructure, router decomposition,
`bluerange-spec` package + manifest v1 + loader, validator
plugin system, container profiles + orchestrator hardening,
blue-team validators (sigma / yara / chain-of-custody /
attack-chain / cloud-misconfig), challenge testing harness.

Detailed phase notes in `WORK_PLAN.md`.

## Versioning

Not yet applied. When the first tagged release ships, future
entries will move from `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
sections per [SemVer 2.0.0](https://semver.org/) (CLAUDE.md
§17).
