# Siege Range

A self-hosted CTF platform for security operations training.
Players compete on red-team and blue-team challenges running in
isolated, hardened Docker containers; operators get live
scoreboards, an immutable audit ledger, Prometheus metrics,
nightly DB backups, and per-instance egress isolation.

## What's in the box

### Player surface
- **Locked v1 API** at `/api/v1/*` — every response a Pydantic
  model with `extra="forbid"` so internal columns can't leak.
- **Catalogue + scoreboard + leaderboard** with team / weekly
  filters and a Redis-cached scoreboard for big events.
- **Multi-flag challenges** with per-flag progress chips.
- **Per-flag hints** that deduct points on unlock.
- **Real-time updates** via WebSocket (`flag_captured`,
  `challenge_released`, in-product notifications).
- **Account self-service**: password reset, email verification,
  TOTP MFA + recovery codes, profile / team edit, GDPR data
  export, account deletion.

### Challenge isolation
- **Five container profiles** that fully determine the launch
  envelope: `default-strict`, `malware-sandbox`,
  `egress-proxied`, `egress-proxied-sidecar`, `llm-sandbox`.
- **Image digest pinning** — launcher refuses any image
  reference without `sha256:…`.
- **Seccomp + dropped caps + read-only root + tmpfs** by
  default. Per-profile bundled seccomp JSON, content-hashed
  and verified at boot.
- **Hot-reloaded egress allowlist** — the api process renders
  the union of every active instance's allowlist to a shared
  volume and SIGHUPs tinyproxy. Per-instance sidecars are
  available when allowlists shouldn't bleed across challenges.

### Validators (`bluerange.validators` entry-point group)
- `exact`, `regex`, `multi_part` (red-team baseline)
- `sigma_rule`, `yara_rule`, `chain_of_custody`,
  `attack_chain`, `cloud_misconfig` (blue-team)
- `llm_signal` — regex-match an LLM transcript for
  prompt-injection / jailbreak signals (ADR 0001)
- Custom plugins ship via the same entry-point.

### Operator surface
- **Admin web UI** with tabs for users, challenges (full
  create/edit modal), competitions, webhooks (CRUD + delivery
  viewer + replay), audit log (paginated + filtered), and
  system info (live readiness probes + DB row counts).
- **Hash-chained audit ledger** with hourly tamper-detection
  scheduler — broken chain shows up immediately in the admin
  notification drawer + WARN log.
- **Prometheus `/metrics`** endpoint emitting RED metrics per
  route template + the audit-verify heartbeat / finding
  counter.
- **Drop-in alert rules** at `docs/alerts/*.yml` covering 5xx
  rate, p99 SLO, in-flight saturation, `up` liveness, audit
  tamper, audit-verify staleness.
- **OpenTelemetry tracing** (opt-in via
  `OTEL_EXPORTER_OTLP_ENDPOINT`) for FastAPI / SQLAlchemy /
  httpx spans.
- **Nightly automated DB backups** with retention pruning.
- **CSP violation reporting** at `/csp-report` with structured
  log output.

## System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 16 GB | 32 GB |
| Disk | 50 GB SSD | 200 GB SSD |
| Docker | 24+ with Compose v2 | 28+ |

## Quick start (development)

```bash
git clone https://github.com/Uspdan/seige-range.git
cd seige-range
cp .env.example .env

# Fill in REQUIRED secrets — the api boot rejects placeholders:
python -c "import secrets; print(secrets.token_hex(32))"  # SECRET_KEY
# Pick a strong ADMIN_PASSWORD (≥12 chars, not "Admin123!@#" or any
# obvious placeholder).
# Edit .env: set SECRET_KEY + ADMIN_PASSWORD.

make dev
make seed         # load examples/challenges/* into the DB
```

Dashboard: <http://localhost:3000> · default admin from `.env` ·
API at `/api/*` proxied by nginx.

## Production deploy

See [`docs/operator-handbook.md`](docs/operator-handbook.md) for
the full Day-1 / Day-2 guide. Post-deploy verification matrix in
[`docs/runbooks/prod-smoke.md`](docs/runbooks/prod-smoke.md).

## Documentation map

| Path | What |
|---|---|
| [`WORK_PLAN.md`](WORK_PLAN.md) | Sprint-by-sprint history (Phase 0–12 + Sprints 1–12). |
| [`CHANGELOG.md`](CHANGELOG.md) | User-facing change log. |
| [`docs/operator-handbook.md`](docs/operator-handbook.md) | Day-1 deploy + Day-2 ops guide. |
| [`docs/author-handbook.md`](docs/author-handbook.md) | How to write challenges. |
| [`docs/runbooks/`](docs/runbooks/) | One file per known failure mode. |
| [`docs/alerts/`](docs/alerts/) | Prometheus rule files + load instructions. |
| [`docs/adr/`](docs/adr/) | Architectural Decision Records. |
| [`docs/security-model.md`](docs/security-model.md) | Container isolation, seccomp profiles, capability drops. |
| [`docs/challenge-spec-v1.md`](docs/challenge-spec-v1.md) | Locked manifest spec. |
| [`docs/ci-templates/`](docs/ci-templates/) | Parked CI workflows (re-activate when GitHub Actions is on). |

## Architecture

```
                       :80 / :443
                          |
                       [nginx]    TLS termination, rate limits
                       /     \
                      /       \
              [dashboard]   [api] ─── [redis]
                (Vite SPA)  (FastAPI) ─ [db] (PostgreSQL + alembic)
                              |
                              ├─── [scheduler] (apscheduler in-process)
                              │       cleanup, leaderboard cache,
                              │       webhook retry/prune,
                              │       audit verify (hourly),
                              │       db backup (nightly 02:30 UTC)
                              │
                              └─── [docker-proxy] ─── [orchestrator]
                                      ACL'd            (DinD)
                                                          |
                                                  [challenge containers]
                                                          |
                                          ┌──── per-instance bridge ────┐
                                          │                             │
                                  [shared egress-proxy]       [per-instance sidecar]
                                  (egress-proxied)            (egress-proxied-sidecar
                                                                  / llm-sandbox)
```

| Network | Type | Purpose |
|---------|------|---------|
| `siege-frontend` | bridge | nginx ↔ dashboard ↔ api |
| `siege-backend` | internal | api ↔ db ↔ redis ↔ docker-proxy |
| `siege-challenges` | internal | orchestrator ↔ challenge containers ↔ vpn |
| `siege-egress` | bridge | egress-proxy ↔ outside (FQDN-allowlisted) |

## Status

Phase 0–12 hardening program plus 12 follow-on sprints shipped.

| | Count |
|---|---|
| Backend tests | 618 @ 86.6% coverage |
| Spec-package tests | 38 |
| Playwright e2e tests | 16 |
| Container profiles | 5 |
| Validator plugins | 9 |
| Scheduled jobs | 7 |
| Runbooks | 7 |
| Alembic migrations | 13 |

Per-sprint detail in [`WORK_PLAN.md`](WORK_PLAN.md).
