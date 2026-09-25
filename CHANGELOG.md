# Changelog

All notable user- and operator-facing changes are documented here in
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.
Per-commit implementation detail lives in `git log`.

## [2.6.0] - 2026-09-04

This release reconciles all changes merged after the `v2.5.0` tag.

### Added
- Artifact-only challenges with authenticated, hash-verified downloads;
  manifest specification v1.1 makes the challenge container optional.
- The standalone `castra-spec` authoring SDK and `castra` CLI for
  scaffolding, validating and testing challenges without the platform.
- Per-instance exact flags, minted at launch and stored as hashes, so
  players cannot share answers and challenge images need not contain them.
- Audit-grade drill evidence packs in JSON and PDF with ledger sequence,
  chain verification and report fingerprints.
- Deployed Prometheus and Alertmanager services, tested alert rules,
  persistent database backups and stale-backup detection.
- The `castra.sh` landing page, product screenshots, role-based
  documentation indexes and public contribution and security policies.

### Changed
- Renamed the authoring package and validator entry-point namespace from
  `bluerange-spec` to `castra-spec` before third-party publication.
- Updated visible product and API branding to Castra while preserving
  deployment identifiers whose rename would break existing installations.
- Licensed Castra under Business Source License 1.1, with each version
  converting to Apache-2.0 four years after release.
- Expanded the public author, player and operator documentation for
  artifact-only exercises, per-instance flags and operational recovery.

### Fixed
- Repaired a backup path that had never succeeded: the runtime now has a
  matching `pg_dump`, backups persist across container replacement and
  failures produce actionable monitoring signals.
- Fixed challenge hints that did not render, production image pull and
  digest validation failures, an unwired scoreboard cache setting and an
  incorrect frontend API base path.
- Made frontend lint, backend lint, strict type checking, SDK tests and
  dependency audits execute as real CI gates rather than pass vacuously.
- Fixed a production startup logging crash and a conditional React hook
  that could fail when an instance appeared after initial render.

### Security
- Removed the rate-limit bypass header and replaced it with bounded,
  environment-aware test budgets.
- Denied validator subprocess network access with a fail-closed seccomp
  filter, removing an exfiltration and server-side request forgery path.
- Removed cleartext challenge flags and answers from public source and
  added CI checks to prevent their reintroduction.
- Updated affected Python and JavaScript dependencies to clear the known
  high-severity advisories blocking the security gates.
- Removed internal working documents, audit-run reports and agent
  scaffolding from the public repository.

## [2.5.0] - 2026-05-17

The workstation and content release: a full live-shell challenge
catalogue, an in-range analyst workstation, and an offline player
runner for air-gapped exercises.

### Added — player experience
- **In-range analyst workstation.** A per-player hardened Linux
  container with a curated forensics and networking toolchain,
  launched from the UI and reachable over SSH or an in-browser
  terminal. Sessions use one-shot credentials that are never
  persisted server-side, and each player keeps a private home
  volume across restarts.
- **Offline player runner.** A single-file CLI that runs any
  live-shell challenge as a standalone container on the player's
  own machine, then synchronises earned solves back to a central
  range. Idempotent per challenge, so repeated syncs are safe.
- **Offline bundle builder.** Packages the challenge images, the
  player CLI and a runbook into one compressed archive for
  disconnected delivery.
- Challenge browsing gained category, difficulty and status
  filters with a result count and a clear-filters control.

### Added — content
- **47 live-shell challenges**, 25 blue-team and 22 red-team.
  - ATT&CK mini-campaigns covering all 14 tactics, Reconnaissance
    through Impact.
  - Network device forensics across 10 vendor platforms in both
    static-log and live-CLI form, modelled on publicly documented
    edge-device intrusions.
  - Windows and Active Directory intrusion scenarios spanning
    domain controller, workstation and file-server compromise.
  - Linux host intrusion and post-exploitation persistence.
  - Red-team packs covering the OWASP Web and API Top 10.

Challenge internals, objectives and solution paths are deliberately
not documented here. Authors should consult the author handbook.

### Added — operations
- Nightly automated database backups with retention pruning;
  failures surface as operator notifications.
- Prometheus metrics with per-route request, error and duration
  instrumentation, plus alert rules carrying runbook links.
- Hourly audit-ledger tamper detection that raises an operator
  notification and a structured error on any finding.
- Optional OpenTelemetry tracing, enabled by configuration.
- A scheduled reaper for idle workstations and a startup sweep
  that reconciles instance records whose containers no longer
  exist, so stale records cannot block a re-launch.
- Browser CSP violation reporting endpoint with structured logging.

### Added — accounts and administration
- Account settings covering profile, email, password and data.
- TOTP multi-factor authentication with recovery codes.
- Email verification, with an optional policy requiring it at login.
- Password reset by emailed, time-limited, hashed token.
- Data portability and erasure endpoints for GDPR Articles 15 and
  17, preserving audit-ledger immutability.
- Admin challenge authoring, webhook subscription management with
  one-time secret reveal and delivery replay, and audit-log
  pagination with action and user filters.
- Outbound webhooks with HMAC signing, exponential-backoff retry
  and retention pruning.

### Added — platform
- A locked public API v1 surface covering the catalogue,
  scoreboard, ATT&CK coverage, flag submission, multi-flag
  progress and webhook management.
- Redis-backed scoreboard caching that degrades gracefully to live
  computation on any cache failure.
- Real-time notification delivery over WebSocket.
- Per-instance egress filtering via a proxy sidecar profile with
  hot-reloadable rules.
- Operator, author and player handbooks, and runbooks for rollback,
  database restore, secret rotation and scheduler recovery.
- Architecture decision records for the workstation security
  posture, validator network isolation and the AI honeypot
  challenge category.

### Fixed
- Removed a brief network disconnect when a challenge launched, by
  establishing the container's network alias before start.
- Corrected instance records left stale after an orchestrator
  recreate.
- Hardened the workstation image: pinned base image digest and
  unprivileged interactive shell sessions.

### Security
- Hash-chained audit ledger with integrity verification.
- Fail-fast secret validation, CORS policy, security headers and
  TLS termination with HSTS.
- Container profile hardening and orchestrator isolation controls.
- Reset tokens stored hashed at rest with short expiry.

### Earlier history

Releases before 2.5.0 covered the initial platform build and a
hardening program: the audit ledger, security control baseline,
readiness probes, the `castra-spec` manifest format and validator
plugin system, container profiles, blue-team validators and the
challenge testing harness. Per-commit detail remains in `git log`.

[2.6.0]: https://github.com/uspdan/castra/compare/v2.5.0...v2.6.0
[2.5.0]: https://github.com/uspdan/castra/releases/tag/v2.5.0
