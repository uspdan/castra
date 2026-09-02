# Castra

[![CI](https://github.com/uspdan/castra/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/uspdan/castra/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/uspdan/castra)](https://github.com/uspdan/castra/releases)
[![License: BUSL-1.1](https://img.shields.io/badge/license-BUSL--1.1-blue)](LICENSE)

**A cyber range you run yourself.** Castra is a self-hosted platform for
security-operations drills: red-team and blue-team challenges running in
isolated, hardened Docker containers, with live scoreboards, a hash-chained
audit ledger, and evidence packs that turn every exercise into
audit-ready proof your team trains.

Website: [castra.sh](https://castra.sh) *(launching soon)* · License:
[Business Source License 1.1](LICENSE) (source-available; converts to
Apache-2.0 per version) · Status: **pre-launch, pilots welcome** —
[hello@castra.sh](mailto:hello@castra.sh)

## Why Castra

- **The blue team is first-class.** Nine validator plugins including
  `sigma_rule`, `yara_rule`, `chain_of_custody`, `attack_chain`,
  `cloud_misconfig`, and `llm_signal` for prompt-injection hunts — not just
  flag matching.
- **Authoring is the core workflow.** A locked
  [challenge manifest spec](docs/challenge-spec-v1.md), the `castra` CLI
  (`new` / `validate` / `test`), and artifact-only challenges that need no
  container at all.
- **Drills become audit evidence.** Every submission and launch lands in an
  append-only, hash-chained ledger; `GET /admin/reports/drill` assembles
  participants, ATT&CK techniques, timeline, and a chain-verification
  result into a fingerprinted evidence pack (JSON + PDF) for ISO 27001,
  SOC 2, and DORA/NIS2 resilience-testing obligations.
- **Self-hosted, by design.** One compose stack, your hardware, your data.
  Air-gapped play is supported via the offline runner and bundle builder.
- **Built to the standard it teaches.** Digest-pinned images, seccomp +
  dropped caps + read-only root by default, ACL'd Docker socket proxy,
  per-instance egress allowlists, strict input validation at every boundary.

## Quick start (development)

```bash
git clone https://github.com/uspdan/castra.git
cd castra
cp .env.example .env

# Fill in REQUIRED secrets — the api boot rejects placeholders:
python -c "import secrets; print(secrets.token_hex(32))"  # SECRET_KEY
# Pick a strong ADMIN_PASSWORD (≥12 chars, no obvious placeholder).
# Edit .env: set SECRET_KEY + ADMIN_PASSWORD.

make dev
make seed         # load examples/challenges/* into the DB
```

Dashboard: <http://localhost:3000> · default admin from `.env` · API at
`/api/*` proxied by nginx.

**System requirements:** 4+ cores / 16 GB RAM / 50 GB SSD minimum
(8 cores / 32 GB / 200 GB recommended), Docker 24+ with Compose v2.

## Installation & manuals

| Guide | Audience |
|---|---|
| **[Operator handbook](docs/operator-handbook.md)** — installation: Day-1 deploy (bootstrap, TLS, bring-up) and Day-2 ops (monitoring, backups, MFA, upgrades, secret rotation) | Whoever runs the range |
| **[Player handbook](docs/player-handbook.md)** — user manual: UI flow, analyst workstation, offline runner, syncing offline solves | People taking the drills |
| **[Author handbook](docs/author-handbook.md)** — writing challenges with the Castra SDK, manifest anatomy, container profiles, authoring checklist | People building drills |
| [Production smoke checklist](docs/runbooks/prod-smoke.md) — post-deploy verification matrix | Operators |
| [Runbooks](docs/runbooks/) — one file per known failure mode, incl. [air-gapped play](docs/runbooks/offline-workstation.md) | Operators |
| [Analyst workstation](infra/workstation/README.md) — in-range forensics container, deploy + tuning | Operators |

Full documentation index: [`docs/`](docs/README.md)

## Reference

| Path | What |
|---|---|
| [`docs/challenge-spec-v1.md`](docs/challenge-spec-v1.md) | Locked challenge manifest spec (v1.1, artifact-only supported). |
| [`docs/security-model.md`](docs/security-model.md) | Container isolation, seccomp profiles, capability drops. |
| [`docs/adr/`](docs/adr/) | Architectural decision records. |
| [`docs/alerts/`](docs/alerts/) | Drop-in Prometheus rules: 5xx rate, p99 SLO, audit tamper, liveness. |
| [`docs/privacy.md`](docs/privacy.md) / [`docs/dpia.md`](docs/dpia.md) | Privacy notes and GDPR Art. 35 assessment for operators. |
| [`CHANGELOG.md`](CHANGELOG.md) | Keep-a-Changelog format, current release 2.5.0. |
| [`docs/ci-templates/`](docs/ci-templates/) | Reference CI workflows for forks/derivatives. |

## The SDK and CLIs

- **`castra-spec`** (Python ≥3.10) — the authoring SDK and manifest schema.
  Ships the `castra` CLI (`castra new`, `castra validate`, `castra test`)
  and the `castra.validators` entry-point group for custom validators.
  *PyPI publication is in progress; until then install from source:*
  `pip install ./packages/castra-spec`.
- **`scripts/seige`** — the offline player runner (single-file, stdlib-only):
  run any live-shell challenge as a standalone container on a laptop, fully
  air-gapped, then `seige sync --upstream URL` to credit solves back to the
  range. (Keeps its legacy name for existing offline bundles.)

## What's in the box

**Player surface** — locked `/api/v1/*` API, catalogue + scoreboard +
leaderboard, multi-flag challenges with per-flag hints, WebSocket live
updates, full account self-service (TOTP MFA, recovery codes, GDPR export).

**Challenge isolation** — five container profiles (`default-strict`,
`malware-sandbox`, `egress-proxied`, `egress-proxied-sidecar`,
`llm-sandbox`), image digest pinning, hot-reloaded egress allowlists with
optional per-instance sidecars.

**Operator surface** — admin UI (users, challenges, competitions, webhooks
with delivery replay, audit log, system info), hourly ledger
tamper-detection, Prometheus RED metrics, opt-in OpenTelemetry tracing,
nightly DB backups with retention pruning, CSP violation reporting.

**Player connectivity** — browser + in-range analyst workstation (SSH or
in-browser ttyd, one-shot passwords, per-player persistent home) or the
offline runner. No VPN required.

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

## By the numbers

47 challenges in the catalogue (25 blue, 22 red) · 16 live-shell
device-forensics scenarios · 14/14 ATT&CK tactics covered by mini-campaigns ·
9 validator plugins · 5 container profiles · 8 runbooks · 637 backend tests
at ~86% coverage.

## Contributing, security, licensing

- **Contributing:** see [CONTRIBUTING.md](CONTRIBUTING.md). Pilot feedback
  shapes the authoring workflow — [hello@castra.sh](mailto:hello@castra.sh).
- **Security:** please report vulnerabilities privately — see
  [SECURITY.md](SECURITY.md).
- **License:** [BUSL-1.1](LICENSE). Free to run for your own (or your
  clients') training; each version converts to Apache-2.0 four years after
  release. Offering Castra itself as a competing hosted service requires a
  commercial license.

> **A note on names:** Castra began life as *seige-range*. The legacy name
> survives in Docker network/image names and the offline runner script on
> existing deploys; everything user-facing is Castra.
