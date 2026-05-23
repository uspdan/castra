# Inventory — seige-range

## Project layout (top level)
- `backend/` — FastAPI app (Python 3.10+, ~126 source files in `app/`).
- `frontend/` — React + Vite SPA (~39 JS/JSX files in `src/`).
- `challenges/` — 62 CTF challenge containers (OUT-OF-SCOPE: training material).
- `examples/` — Illustrative vulnerable code (OUT-OF-SCOPE).
- `docker/` — egress-proxy, egress-sidecar sidecar configs.
- `docker-compose.{yml,dev.yml,prod.yml}` — three compose profiles.
- `nginx/` — reverse proxy config.
- `infra/workstation/` — student workstation infra.
- `packages/` — bluerange-spec internal path-dep package.
- `scripts/` — bootstrap, build, seal-flags, seal-answers, seed, backup, restore.
- `secrets/` — `flags.json` and `answers/` (gitignored content).
- `docs/`, top-level `*.md` (BACKLOG, CHANGELOG, LEARNINGS, README, WORK_PLAN, CLAUDE.*).
- `.github/workflows/ci.yml` — single CI workflow file.

## Toolchain versions
- Python: 3.10+ required (`pyproject.toml`), CI runs 3.11.
- Node: 20 in CI.
- Docker: required (DinD for challenge orchestration).

## Backend dependency highlights (pinned exactly — good)
- Web: `fastapi==0.109.2`, `uvicorn[standard]==0.27.1`.
- ORM: `sqlalchemy[asyncio]==2.0.27`, `asyncpg==0.29.0`, `alembic==1.13.1`.
- Validation: `pydantic==2.6.1`, `pydantic-settings==2.1.0`.
- Auth/crypto: `python-jose[cryptography]==3.3.0`, `passlib[bcrypt]==1.7.4`, `bcrypt==4.0.1`, `pyotp==2.9.0`.
- Docker: `docker==7.1.0`.
- Cache/queue: `redis==5.0.1`, `hiredis==2.3.2`, `apscheduler==3.10.4`.
- Templating / PDF: `jinja2==3.1.6`, `weasyprint==61.0`.
- Sanitisation: `bleach==6.1.0`.
- Regex: `google-re2==1.1.20240702` (ReDoS-resistant matcher with stdlib fallback).
- Detection libs: `pysigma==1.3.3`, `yara-python==4.5.4`.
- Email: `aiosmtplib==3.0.1`.
- Observability: `structlog==24.1.0`, `prometheus-client==0.20.0`, OpenTelemetry 1.27.x suite.
- Total: ~30 top-level pinned.
- **Known CVE flags to verify in appsec phase:**
  - `python-jose==3.3.0` has a stale-known CVE around algorithm confusion if `none` is not explicitly rejected — needs verification in `app/security/`.
  - `python-multipart==0.0.9` had a DoS CVE; 0.0.9 is the fixed version, but worth re-checking.
  - `jinja2==3.1.6` is current.

## Frontend dependency highlights (FLOATING ranges — violates section 3.4)
- `axios ^1.6.7`, `react ^18.2.0`, `react-router-dom ^6.22.1`, `recharts ^2.12.2`, `zustand ^4.5.1`, `clsx ^2.1.0`, `lucide-react ^0.344.0`.
- Dev: `@playwright/test ^1.59.1`, `@tailwindcss/vite ^4.0.0`, `vite ^5.1.4`.
- **Finding (provisional, to hand to appsec):** every frontend dep uses `^` ranges. CLAUDE.md §3.4 forbids floating ranges.

## Backend module map (the in-scope assessment surface)
- `app/main.py` — FastAPI composition root.
- `app/config.py` — settings via pydantic-settings.
- `app/database.py` — async SQLAlchemy engine/session.
- `app/models.py` — ORM models (single file — may exceed 300-line rule; flag for code review).
- `app/middleware/` — `logging_mw.py`, `metrics.py`, `rate_limit.py`, `security_headers.py`.
- `app/security/` — auth + `seccomp/` profiles for sandboxed validators.
- `app/services/` (~30 modules): `auth`, `mfa`, `email`, `email_verification`, `password_reset`, `cheat_detector`, `flag_dispatch`, `flag_submission`, `scoring`, `scoreboard_cache`, `orchestration/`, `orchestrator`, `workstation`, `validator_sandbox`, `validator_subprocess_runner`, `validator_registry`, `webhook_dispatch`, `notifications`, `ws_manager`, `audit/`, `backup`, `scheduler`, `hints`, `challenge_browse`, `challenge_loader/`, `api_v1`, `test_harness/`.
- `app/routers/` — 18 router modules. v0 path: `auth`, `admin`, `competitions`, `instances`, `leaderboard`, `notifications`, `stats`, `writeups`, `health`, `ws`, `challenges/`. v1 path: `auth`, `admin`, `me`, `challenges`, `hints`, `leaderboard`, `progress`, `scoreboard`, `submit`, `webhooks`, `workstation`, `attack_coverage`.
- `app/validators/` — `exact`, `regex`, `multi_part`, `sigma_rule`, `yara_rule`, `chain_of_custody`, `attack_chain`, `cloud_misconfig`, `llm_signal` (registered via setuptools entry-points).
- `app/observability/` — tracing/metrics adapters.
- `app/tools/`, `app/templates/`.

## Entrypoints summary
- HTTP: ~92 route declarations across routers — REST API at `/api/v1/...` plus legacy `/api/...`. Health: `/healthz`, `/readyz`. Metrics: `/metrics` (Prometheus).
- WebSocket: `app/routers/ws.py`, plus `app/services/ws_manager.py`.
- Scheduler: APScheduler in `app/services/scheduler.py` for periodic jobs.
- CLI / scripts: `scripts/seige` (ops wrapper), `scripts/seal-flags.py`, `scripts/seal-answers.py`, `scripts/seed_challenges.py`, `scripts/backup.sh`, `scripts/restore.sh`.

## External surfaces
- PostgreSQL (via `asyncpg`).
- Redis (cache, rate-limit state, scoreboard cache).
- Docker daemon (DinD) for challenge orchestration — high privilege surface.
- SMTP (outbound, password reset + verification).
- OpenTelemetry OTLP/HTTP exporter (opt-in).
- ttyd-backed browser shells (frontend connects to per-instance shell containers).
- Webhook dispatch (outbound HTTP to operator-configured URLs).

## Infrastructure
- Backend `Dockerfile`, frontend `Dockerfile`.
- `docker/egress-proxy/`, `docker/egress-sidecar/` — outbound egress control for challenge containers.
- `docker-compose.yml` (default), `docker-compose.dev.yml`, `docker-compose.prod.yml`.
- `nginx/` reverse proxy config (TLS termination, `certs/` gitignored).

## Database / migrations
- Alembic. 14 migration files under `backend/migrations/versions/`.
- Models in a single `app/models.py` (check for size & SRP in code-review phase).

## CI / supply chain
- Single workflow `.github/workflows/ci.yml`.
- Jobs (per intake context): backend-tests (unit only — `pytest tests/unit/ -v --no-cov`), frontend-build, secret-scan (trufflehog), flag-leak guard.
- **Gaps:**
  - Coverage is explicitly `--no-cov` in CI — violates §5.1 80% gate.
  - Integration tests NOT wired in CI.
  - No `pip-audit` / `npm audit` step (§3.4 / §6.2).
  - No lint/typecheck job visible from sampled file (need to verify in appsec/code-review).
  - CI hard-codes test secrets in plaintext (`SECRET_KEY: ci-test-secret-...`, `ADMIN_PASSWORD: CIAdminPasswordA1!`). Acceptable for CI ephemeral env but worth a code-review note.

## Secrets handling
- `secrets/flags.json` — sealed (SHA-256 hashes) — gitignored.
- `secrets/answers/` — per-question sealed answers — gitignored.
- Recent history rewrite scrubbed plaintext `CTF{...}` literals; trufflehog enforces forward-going.

## Counts at a glance
- Backend Python files (excluding `__pycache__`): ~126
- Frontend JS/JSX files: ~39
- HTTP endpoints (router decorators): ~92
- Alembic migrations: 14
- Top-level backend deps: ~30 (all pinned)
- Top-level frontend deps: 14 (all floating — finding)

## Out-of-scope volume (informational)
- `challenges/` — 62 challenge dirs; explicitly excluded.
- `examples/` — illustrative; excluded.
