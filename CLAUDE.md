# CLAUDE.md — Project Engineering Standards

> This file governs how Claude Code builds, modifies, and reviews code in this project.
> All directives are mandatory. Violations must be flagged, not silently ignored.
>
> **Canonical source:** `standards` repo. Do not edit per-project copies directly.
> Pull updates via `./scripts/sync-standards.sh` or CI bootstrap.

---

## 1. ARCHITECTURE PRINCIPLES

### 1.1 Modularity

- **Single Responsibility**: Every module, class, and function does exactly one thing. If you need the word "and" to describe what it does, split it.
- **Explicit Boundaries**: Each module exposes a public API via an `index.ts` (or `__init__.py`, `mod.rs`, etc.). Internal implementation files are never imported directly by other modules.
- **Dependency Direction**: Dependencies flow inward. Core/domain logic has zero dependencies on infrastructure, frameworks, or I/O. Use dependency injection or ports-and-adapters to invert where needed.
- **No God Files**: No single file exceeds 300 lines. No single function exceeds 50 lines. If a module needs more, decompose it.
- **Feature Isolation**: New features are added as new modules, not by extending existing ones. Existing modules are only modified to expose new extension points.

### 1.2 Project Structure

Every project must follow a consistent layout. Adapt naming to the language ecosystem but preserve the separation:

```
src/
├── core/              # Domain logic, pure functions, business rules — zero I/O
├── services/          # Orchestration layer — coordinates core logic with infra
├── infra/             # External integrations: DB, HTTP, queues, file I/O
│   ├── db/
│   ├── http/
│   └── queue/
├── api/               # Entrypoints: REST routes, CLI handlers, event consumers
├── shared/            # Cross-cutting: types, constants, errors, result types
│   ├── types/
│   ├── errors/
│   └── constants/
├── config/            # Configuration loading, validation, env parsing
└── utils/             # Pure utility functions only — no business logic
tests/
├── unit/              # Mirror src/ structure, one test file per module
├── integration/       # Tests requiring real infra (DB, network)
└── fixtures/          # Shared test data, factories, builders
scripts/               # Build, deploy, migration, seed scripts
docs/                  # Architecture decision records, runbooks, API docs
docker/                # Dockerfiles, compose files, container configs
```

### 1.3 Naming & Conventions

- Files: `kebab-case` (TS/JS), `snake_case` (Python/Rust).
- Exported types/classes: `PascalCase`. Functions/variables: `camelCase` (TS/JS) or `snake_case` (Python/Rust).
- Boolean variables/functions: prefix with `is`, `has`, `should`, `can`.
- Constants: `UPPER_SNAKE_CASE`, defined in `shared/constants/`.
- No abbreviations in public APIs. `getUserAuthentication()` not `getUsrAuth()`.

### 1.4 Dependency Injection & Wiring

- **Constructor injection** is the default pattern. All dependencies are passed explicitly — no service locators, no ambient singletons, no module-level mutable state.
- **Composition root**: A single wiring entrypoint (`src/composition-root.ts`, `src/container.py`, etc.) assembles the dependency graph. No other file instantiates infrastructure or service-layer objects.
- **Interfaces over implementations**: Core and service layers depend on interfaces/protocols/traits. Concrete implementations live in `infra/` and are wired at the composition root.
- **Test seams**: Every external dependency is injectable, making it replaceable in tests without mocks of internals. Fake implementations live in `tests/fixtures/fakes/`.

---

## 2. ERROR HANDLING & RESULT TYPES

### 2.1 Fail-Fast, Fail-Loud

- **No silent swallowing.** Every `catch` block must either re-throw, return a typed error, or log at `ERROR` level with full context. Empty catch blocks are forbidden.
- **Use Result types** over thrown exceptions for expected failure paths. `Result<T, E>` (Rust), `Either` pattern (TS), or equivalent. Exceptions are for truly exceptional/unrecoverable situations.
- **Validate at the boundary.** All external input (HTTP, CLI, env vars, file reads, queue messages) is validated and parsed into typed domain objects at the point of entry. Nothing unvalidated reaches core logic.

### 2.2 Error Classification

Define and use a typed error hierarchy:

```
AppError
├── ValidationError      # Bad input — 400-class
├── AuthenticationError  # Identity unknown — 401
├── AuthorisationError   # Identity known, access denied — 403
├── NotFoundError        # Resource does not exist — 404
├── ConflictError        # State conflict — 409
├── RateLimitError       # Throttled — 429
├── DependencyError      # Upstream/infra failure — 502/503
└── InternalError        # Unexpected bug — 500
```

Every error must carry: `code` (machine-readable), `message` (human-readable), `context` (structured metadata), `timestamp`, `requestId` (if in a request context).

---

## 3. SECURITY CONTROLS

### 3.1 Input Validation

- Validate **all** external input with a schema validation library (Zod, Pydantic, JSON Schema, etc.). No hand-rolled regex-only validation.
- Apply allowlists, not denylists. Define what is permitted, reject everything else.
- Enforce length limits, type constraints, and format constraints on every field.
- Sanitise all string inputs before use in HTML, SQL, shell commands, or log output.

### 3.2 Authentication & Authorisation

- Never store secrets, API keys, tokens, or passwords in source code, config files, or environment variable defaults. Use a secrets manager or `.env` files excluded via `.gitignore`.
- Always check authorisation at the service layer, not only at the API/route layer. Defence in depth.
- Implement principle of least privilege: every component, user, and service account gets the minimum permissions required.
- Session tokens / JWTs: validate expiry, issuer, audience, and signature on every request. No "trust the client" patterns.

### 3.3 Data Protection

- PII and sensitive fields are encrypted at rest and masked in logs. Implement a `SensitiveString` wrapper type that redacts on serialisation/logging.
- No secrets in URLs or query parameters. Ever.
- Database queries use parameterised queries or ORM methods. Raw string interpolation into SQL is forbidden.
- All HTTP responses include security headers: `Content-REDACTED-Policy`, `X-Content-Type-Options`, `Strict-Transport-REDACTED`, `X-Frame-Options`.

### 3.4 Dependency REDACTED

- Pin all dependency versions exactly. No floating ranges (`^`, `~`, `*`).
- Run `npm audit` / `pip audit` / `cargo audit` (as appropriate) before every commit. Fail the build on HIGH or CRITICAL findings.
- No dependencies with known CVEs in CISA KEV or with EPSS > 0.7.
- Review new dependencies before adding: check maintainer count, last publish date, download count, licence compatibility.

---

## 4. AUDIT LOGGING

### 4.1 Audit Ledger

Maintain an **append-only** audit log. Every state-changing operation must log an audit entry answering:

1. **Who** — Authenticated identity (user ID, service account, API key hash).
2. **What** — Action performed (verb + resource type).
3. **When** — ISO 8601 timestamp with timezone.
4. **Where** — Source IP, service instance, endpoint.
5. **Which** — Resource identifier(s) affected.
6. **Why** — Business justification or triggering event (where applicable).

### 4.2 Log Integrity

- Audit logs are **immutable**. No update or delete operations on audit records.
- Structured JSON format only. No unstructured string logs for auditable events.
- Log levels: `AUDIT` for auditable events, `ERROR` for failures, `WARN` for degraded states, `INFO` for lifecycle events, `DEBUG` for development only (never in production).
- Sensitive data is **never** logged in cleartext. Use the `SensitiveString` type or explicit redaction.

### 4.3 Operational Logging

- Every HTTP request logs: method, path, status code, duration, request ID. No request body in production logs.
- Every external dependency call logs: target, duration, success/failure, retry count.
- Correlate all logs within a request via a `requestId` propagated through the call chain.

---

## 5. TESTING STANDARDS

### 5.1 Coverage & Structure

- **Minimum 80% line coverage.** Critical paths (auth, payment, data mutation) require 95%+.
- **Test pyramid**: many unit tests, fewer integration tests, minimal E2E tests.
- Unit tests are fast, isolated, deterministic — no network, no disk, no database.
- Integration tests use real infrastructure (test containers, in-memory DBs) — not mocks of infra.

### 5.2 Test Quality

- Every public function has at least: one happy-path test, one error-path test, one edge-case test.
- Use **arrange-act-assert** structure. One assertion concept per test (multiple asserts on the same result object are fine).
- Test names describe behaviour: `should_return_403_when_user_lacks_write_permission`, not `test_auth`.
- No test interdependencies. Tests must pass in any order, in isolation, and in parallel.
- Fixtures and factories over raw object construction. Use builder patterns for complex test data.

### 5.3 REDACTED Testing

- Write explicit tests for:
  - Input validation rejection (malformed, oversized, type-mismatched).
  - SQL injection, XSS, and command injection vectors (if applicable).
  - AuthN/AuthZ bypass attempts (missing token, expired token, wrong role).
  - Rate limiting behaviour.
- Fuzz critical parsing functions where practical.

---

## 6. CODE QUALITY GATES

### 6.1 Static Analysis

- **Linter**: ESLint (TS/JS), Ruff (Python), Clippy (Rust) — zero warnings policy. Warnings are errors.
- **Formatter**: Prettier (TS/JS), Black (Python), rustfmt (Rust) — enforced, not optional.
- **Type checking**: strict mode. TypeScript `strict: true`, Python `mypy --strict` or `pyright`, Rust default.
- No `any` types (TS), no `# type: ignore` without an accompanying comment explaining why.

### 6.2 Pre-Commit Checks

Every commit must pass:

1. Format check (auto-fix allowed).
2. Lint (zero warnings).
3. Type check (strict).
4. Unit tests.
5. Dependency audit (no HIGH/CRITICAL).

### 6.3 Pre-Merge Checks

Every merge/PR must pass all pre-commit checks plus:

1. Full test suite (unit + integration).
2. Coverage threshold met.
3. No new `TODO` or `FIXME` without a linked issue/ticket.
4. Architecture constraints validated (dependency direction, file size limits).

---

## 7. API DESIGN

### 7.1 REST Conventions

- Use nouns for resources, HTTP verbs for actions. `POST /users` not `POST /createUser`.
- Consistent response envelope: `{ data, meta, errors }`.
- Version APIs in the URL path: `/api/v1/...`.
- Pagination: cursor-based for large datasets, offset-based only for small bounded sets.
- Rate limiting on all public endpoints. Return `429` with `Retry-After` header.

### 7.2 Request/Response Contracts

- Define schemas (OpenAPI, JSON Schema, or equivalent) for every endpoint — request body, response body, query params, path params.
- Generate types from schemas where possible. Schema is the single source of truth.
- Never return raw database records. Map to response DTOs that exclude internal fields (`_id`, `createdAt` internal timestamps, soft-delete flags, etc.).

---

## 8. CONFIGURATION & ENVIRONMENT

### 8.1 Config Management

- All configuration loaded at startup via a single `config/` module. Fail fast on missing or invalid config.
- Validate config with the same schema library used for input validation.
- Three config layers (in priority order): env vars → config files → defaults. Never hard-code values.
- Separate config schemas per environment: `development`, `test`, `staging`, `production`.

### 8.2 Secrets

- Secrets are **never** committed. `.env` files are in `.gitignore`.
- Provide a `.env.example` with placeholder values documenting every required secret.
- Rotate-friendly: design so secrets can be rotated without redeployment where feasible.

---

## 9. DOCUMENTATION

### 9.1 Code Documentation

- Every public function/method has a docstring/JSDoc describing: purpose, parameters, return value, thrown errors.
- Complex algorithms get a `// WHY:` comment explaining the approach, not just `// WHAT:` comments.
- Architecture Decision Records (ADRs) in `docs/adr/` for every significant technical decision. Format: context, decision, consequences.

### 9.2 Operational Documentation

- `README.md`: setup, run, test, deploy — copy-paste-executable commands.
- `docs/runbooks/`: incident response procedures for known failure modes.
- `CHANGELOG.md`: maintained with every release. Follow Keep a Changelog format.

---

## 10. GIT & WORKFLOW

### 10.1 Commit Standards

- Conventional Commits: `type(scope): description`. Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `security`.
- Atomic commits: one logical change per commit. Refactors are separate from feature changes.
- No committed secrets, no committed `.env` files, no committed build artefacts.

### 10.2 Branch Strategy

- `main` is always deployable. Direct commits to `main` are forbidden.
- Feature branches: `feat/short-description`, bug fixes: `fix/short-description`, security: `security/short-description`.
- Squash-merge to `main`. Branch history is preserved in PR descriptions, not merge commits.

---

## 11. CI/CD PIPELINE

### 11.1 Pipeline Definition

- Every project includes a canonical pipeline config (`.github/workflows/ci.yml`, `.gitlab-ci.yml`, etc.) committed to the repo.
- Pipeline stages run in this order: **install → lint → typecheck → unit test → build → integration test → security scan → package → deploy**.
- Pipelines are deterministic. Same commit produces same result. Pin CI runner images and tool versions.
- Pipeline failures block merge. No manual override without a documented exception approved by a second engineer.

### 11.2 Pipeline Stages

```
stages:
  install       # Dependency resolution, lockfile integrity check
  lint          # Formatter + linter, zero warnings
  typecheck     # Strict type checking
  unit-test     # Fast tests, coverage report
  build         # Compile / bundle
  int-test      # Integration tests against real infra (test containers)
  security      # Dependency audit, SAST, secret scanning
  package       # Container build, artefact publish
  deploy-staging
  deploy-prod   # Manual gate or approval required
```

### 11.3 Deployment Gates

- **Staging** deploys automatically on merge to `main` after all checks pass.
- **Production** requires explicit approval (manual gate, ChatOps, or equivalent).
- Rollback procedure documented per project in `docs/runbooks/rollback.md`. Rollback must be executable in under 5 minutes.
- Blue-green or canary deployments preferred. Big-bang deployments require a documented justification.

### 11.4 Artefact Management

- Build artefacts (containers, binaries, packages) are tagged with the git SHA and semantic version.
- Artefacts are immutable once published. No overwriting tags or versions.
- Container images are scanned for vulnerabilities before promotion to staging/production.

---

## 12. CONTAINERISATION & ENVIRONMENT REPRODUCIBILITY

### 12.1 Container Standards

- Every deployable project includes a `Dockerfile` in `docker/`.
- Multi-stage builds mandatory: separate `build` and `runtime` stages. Build tools and dev dependencies do not ship in production images.
- Base images pinned to digest (e.g., `node:20-slim@sha256:abc123...`), not floating tags.
- Run as non-root user. No `USER root` in the final stage.
- `.dockerignore` excludes: `node_modules`, `.env`, `.git`, `tests/`, `docs/`, build artefacts.
- Images are as small as practical. Alpine or `-slim` variants unless a specific dependency requires otherwise.

### 12.2 Local Development Environment

- `docker-compose.yml` (or equivalent) at project root for local dev. One command to spin up all dependencies: `docker compose up`.
- Includes all required infrastructure: database, cache, queue, mock services.
- Seeds/fixtures loaded automatically on first start via init scripts or entrypoints.
- Ports, credentials, and service names documented in `README.md` and `.env.example`.

### 12.3 Environment Parity

- Dev, test, staging, and production use the **same base image and runtime version**. Only configuration differs.
- No "works on my machine" — if it doesn't run in the container, it doesn't count as working.
- Language runtime versions pinned in project config (`.node-version`, `.python-version`, `rust-toolchain.toml`).

---

## 13. DATABASE & MIGRATION STRATEGY

### 13.1 Migration Tooling

- Use a dedicated migration tool appropriate to the stack: Knex/Prisma (TS/JS), Alembic (Python), Diesel/SQLx (Rust). No ad-hoc SQL scripts run manually.
- Migration files live in `scripts/migrations/` or the tool's default directory, committed to the repo.
- Migrations run automatically on deploy (or as a dedicated pipeline step before the app starts). Never require manual intervention.

### 13.2 Migration Standards

- Every migration has an **up** and a **down**. Irreversible migrations (column drops, data transforms) must document why rollback is not possible and include a `// NO-DOWN:` comment with justification.
- Migration filenames are timestamped: `YYYYMMDDHHMMSS_description.{ts,py,sql}`. Sequential integers are forbidden (merge conflicts).
- Migrations are append-only. Never modify a migration that has been applied to any shared environment (staging, production).
- Destructive operations (drop column, drop table, data deletion) require a two-phase approach: deprecate in release N, remove in release N+1.

### 13.3 Schema Governance

- Schema changes are reviewed with the same rigour as code changes. Include expected query impact in the PR description.
- Every table has: `id` (primary key), `created_at`, `updated_at` (auto-managed timestamps). Soft deletes (`deleted_at`) preferred over hard deletes for auditable data.
- Indexes are explicit, documented, and justified. No "add index and hope" — include the query pattern it supports.
- Foreign key constraints enforced at the database level, not just application logic.

---

## 14. OBSERVABILITY

### 14.1 Health Checks

- Every service exposes:
  - `GET /healthz` — liveness check. Returns `200` if the process is running. No dependency checks. Used by orchestrators to restart crashed processes.
  - `GET /readyz` — readiness check. Returns `200` only when the service can handle traffic (DB connected, caches warm, etc.). Returns `503` otherwise.
- Health endpoints are unauthenticated but excluded from access logs to reduce noise.

### 14.2 Metrics

- Expose application metrics in Prometheus format at `GET /metrics` (or push to StatsD/Datadog equivalent).
- **Mandatory metrics** (RED method):
  - **Rate**: requests per second, by endpoint and status code.
  - **Errors**: error count/rate, by type and endpoint.
  - **Duration**: request latency histograms (p50, p90, p95, p99), by endpoint.
- **Mandatory resource metrics**: active DB connections, connection pool utilisation, queue depth, cache hit rate.
- Custom business metrics where applicable (e.g., signups/hour, jobs processed/minute).

### 14.3 Distributed Tracing

- Instrument with OpenTelemetry (preferred) or equivalent. Every service propagates trace context (`traceparent` header).
- Spans created for: inbound requests, outbound HTTP calls, database queries, queue publish/consume, cache operations.
- Traces are sampled in production (1-10% baseline, 100% on error). Never disable tracing entirely.

### 14.4 Alerting

- Define alerts for every service covering:
  - Error rate exceeds threshold (e.g., >1% 5xx for 5 minutes).
  - Latency exceeds SLO (e.g., p99 > 2s for 5 minutes).
  - Health check failures.
  - Dependency failures (DB unreachable, upstream 5xx).
- Alert definitions are committed to the repo in `docs/alerts/` or as IaC (Terraform, Pulumi, etc.). No click-ops alerting.
- Every alert has a linked runbook in `docs/runbooks/`.

---

## 15. RESILIENCE & RELIABILITY

### 15.1 Timeouts

- **Every external call has an explicit timeout.** No unbounded waits. Defaults:
  - HTTP calls to upstream services: 5s connect, 30s read (adjust per endpoint).
  - Database queries: 10s.
  - Cache operations: 1s.
- Timeouts are configurable via `config/`, not hard-coded.

### 15.2 Retry Policy

- Retries use **exponential backoff with jitter**. No fixed-interval retries (thundering herd).
- Default: 3 retries, initial delay 200ms, max delay 5s, jitter ±50%.
- Only retry on transient failures (5xx, timeouts, connection reset). Never retry on 4xx.
- Retries are logged with attempt count. Final failure is logged at `ERROR` with full context.

### 15.3 Circuit Breaker

- Apply circuit breaker pattern to all external dependencies (upstream APIs, databases, third-party services).
- States: **closed** (normal) → **open** (failing, fast-reject) → **half-open** (probe).
- Thresholds: open after 5 consecutive failures or >50% error rate in a 30s window. Half-open probe after 15s. Adjust per dependency.
- When open, return a degraded response or cached fallback — not a raw 500.

### 15.4 Graceful Degradation

- Every external dependency has a defined degradation strategy: fallback to cache, return partial data, queue for retry, or return a meaningful error.
- No single dependency failure should cause a full service outage. Design for partial availability.
- Load shedding: if under extreme load, prefer dropping new requests (429) over degrading all requests.

---

## 16. PERFORMANCE & RESOURCE BUDGETS

### 16.1 Response Time SLOs

Define and enforce per-project. Default targets unless overridden:

| Endpoint Type          | p50    | p95    | p99    |
|------------------------|--------|--------|--------|
| Synchronous API        | 100ms  | 500ms  | 1s     |
| Search / aggregation   | 200ms  | 1s     | 3s     |
| Background job         | —      | —      | 30s    |
| Health check           | 10ms   | 50ms   | 100ms  |

- SLOs are measured from the application boundary (after load balancer, before response write).
- SLO violations trigger alerts (Section 14.4).

### 16.2 Resource Limits

- Every container/process defines explicit CPU and memory limits. No unbounded resource consumption.
- Connection pools sized explicitly: DB connections = `(2 × CPU cores) + 1` as starting point, tuned per load profile.
- Queue consumers define concurrency limits and backpressure mechanisms.

### 16.3 Payload & Query Budgets

- API response payloads: max 1MB unless streaming. Paginate anything larger.
- Database queries: no unbounded `SELECT *`. Always specify columns. Always limit result sets.
- N+1 query patterns are forbidden. Use joins, batch loads, or DataLoader equivalents.
- Bulk operations: batch size limits (default 100), with backpressure on the caller if exceeded.

---

## 17. VERSIONING & RELEASE MANAGEMENT

### 17.1 Semantic Versioning

- All projects follow [SemVer 2.0.0](https://semver.org/):
  - **MAJOR**: breaking changes to public API or data contracts.
  - **MINOR**: new functionality, backward-compatible.
  - **PATCH**: bug fixes, security patches, no functional change.
- Pre-release versions: `X.Y.Z-rc.N` for release candidates, `X.Y.Z-beta.N` for beta.

### 17.2 Release Process

- Releases are tagged in git: `vX.Y.Z`. Tags trigger the release pipeline.
- `CHANGELOG.md` updated before tagging. Follow [Keep a Changelog](https://keepachangelog.com/) format. Sections: Added, Changed, Deprecated, Removed, Fixed, REDACTED.
- Release notes summarise user-facing changes. Internal refactors are omitted from user-facing notes.

### 17.3 Artefact Versioning

- Container images tagged: `vX.Y.Z` and `sha-<short-hash>`. The `latest` tag is forbidden in production.
- Internal packages/libraries tagged with the same semver. Breaking changes require a major version bump and a migration guide.

---

## 18. CODE REVIEW STANDARDS

### 18.1 Review Requirements

- **Minimum one approving reviewer** before merge. REDACTED-sensitive changes (auth, crypto, input validation, dependency updates) require **two reviewers**, at least one with security domain knowledge.
- Author must not merge their own PR without review, even with approval rights.
- Reviews are completed within **one business day**. If blocked, escalate or pair.

### 18.2 Review Scope

Reviewers check against this document's checklist (Appendix) plus:

- **Architectural fit**: Does this change respect module boundaries and dependency direction?
- **Naming clarity**: Can a new team member understand this code without asking the author?
- **Test quality**: Are the tests testing behaviour (not implementation)? Would they catch a regression?
- **Operational impact**: Will this change affect deployment, monitoring, or on-call? If yes, is the runbook updated?

### 18.3 Review Conduct

- Review the code, not the person. Prefix suggestions with "nit:" for non-blocking style preferences.
- Questions are legitimate review comments. "Why did you choose X over Y?" is valid.
- Distinguish between "must fix before merge" (blocking) and "consider for follow-up" (non-blocking). Label clearly.

---

## 19. FEATURE FLAGS & PROGRESSIVE ROLLOUT

### 19.1 Feature Flag Standard

- All non-trivial features are gated behind feature flags. Ship dark, enable incrementally.
- Flags are managed via a dedicated module (`src/shared/feature-flags/`), not scattered env vars or ad-hoc conditionals.
- Flag naming: `FEATURE_<MODULE>_<DESCRIPTION>` (e.g., `FEATURE_BILLING_NEW_PRICING_ENGINE`).

### 19.2 Flag Lifecycle

- Flags have an **owner** and a **removal date** documented in code as a comment and tracked as a ticket.
- Temporary flags (launch gates): remove within 2 sprints of full rollout. Stale flags are tech debt.
- Permanent flags (ops toggles, kill switches): documented in `docs/feature-flags.md` with purpose and expected states per environment.

### 19.3 Rollout Strategy

- Default rollout: off in production → canary (5%) → ramp (25% → 50% → 100%) → flag removed.
- Flag evaluation is fast (in-memory, no remote call per request) or cached with a short TTL.
- Fallback: if the flag service is unavailable, fall back to the **off** state (safe default). Never fail open on a feature gate.

---

## 20. MULTI-REPO GOVERNANCE

### 20.1 Standards Distribution

- This `CLAUDE.md` file is the canonical engineering standard. It lives in a dedicated `standards` repository.
- Each project repo includes this file at the root. It is synced via one of:
  - **Bootstrap script**: `./scripts/sync-standards.sh` pulls the latest version from the `standards` repo. Run during CI install stage.
  - **CI step**: Pipeline fetches the canonical file before running checks. Stale copies fail the build.
- Per-project **overrides** are permitted only in a clearly marked `CLAUDE.local.md` file that extends (never contradicts) this document. Overrides require an ADR justifying the divergence.

### 20.2 Shared Libraries

- Common code (error types, logging, config loaders, auth middleware) is published as internal packages from the `standards` or `shared-libs` repo.
- Internal packages follow the same versioning rules (Section 17) and are consumed via a private registry or git dependency.
- Breaking changes to shared libraries require a migration guide and a coordinated rollout across consuming projects.

### 20.3 Cross-Project Dependency Management

- Inter-project dependencies are pinned to exact versions. No `latest` or range specifiers.
- Dependency update PRs are automated (Dependabot, Renovate, or equivalent) and subject to the same review standards.
- Shared infrastructure (databases, queues, APIs) is versioned independently. Consumer projects pin to the API version they support.

---

## 21. CLAUDE CODE BEHAVIOUR DIRECTIVES

These rules govern how Claude Code operates within this project:

### 21.1 Planning Before Coding

- **Always plan before writing code.** For any task involving more than a single-file change, produce a brief plan listing: files to create/modify, dependencies between them, and the order of implementation.
- **Ask clarifying questions** before making assumptions about ambiguous requirements. Do not guess at business logic.

### 21.2 Change Discipline

- **Minimal blast radius.** Make the smallest change that satisfies the requirement. Do not refactor adjacent code unless explicitly asked.
- **No drive-by fixes.** If you spot an issue unrelated to the current task, flag it — do not fix it silently.
- **Preserve existing patterns.** Match the style, conventions, and patterns already in the codebase. Do not introduce new paradigms without discussion.

### 21.3 REDACTED Awareness

- **Flag security concerns immediately.** If a requested change introduces a security risk (e.g., disabling validation, hard-coding secrets, exposing internal data), refuse and explain why.
- **Never generate placeholder secrets** like `password123`, `changeme`, or `TODO_REPLACE`. Use environment variable references or secrets manager lookups.
- **Never disable security controls** (CORS, CSP, auth middleware, rate limiting) even "temporarily" or "for testing."

### 21.4 Quality Standards

- **Every new function gets tests.** Do not deliver code without corresponding test coverage.
- **Every new module gets types.** No `any`, no untyped parameters, no implicit returns.
- **Every new endpoint gets validation.** Request schemas are defined before handler logic.

### 21.5 Communication

- When creating or modifying files, briefly explain **why** each change was made, not just what.
- When a task is complete, summarise: what was changed, what was tested, what risks remain, and what follow-up tasks exist.
- If a task would violate any rule in this document, **stop and flag it** rather than proceeding.

---

## APPENDIX A: QUICK REFERENCE CHECKLIST

Use this for every PR/change:

```
[ ] Single responsibility: each module/function does one thing
[ ] Dependency direction: core has no infra imports
[ ] DI wiring: dependencies injected, not imported directly
[ ] Input validation: all external input schema-validated
[ ] Error handling: no empty catches, typed errors used
[ ] Auth checks: service-layer authorisation in place
[ ] Secrets: none in code, config, or logs
[ ] SQL: parameterised only, no string interpolation
[ ] Audit log: state-changing operations logged (who/what/when/where/which/why)
[ ] Sensitive data: masked in logs, encrypted at rest
[ ] Tests: happy path, error path, edge case covered
[ ] REDACTED tests: injection, auth bypass, validation rejection
[ ] Types: strict, no any/ignore without justification
[ ] Lint: zero warnings
[ ] Deps: pinned, audited, no known HIGH/CRITICAL CVEs
[ ] Docs: public API documented, ADR for decisions
[ ] Commits: conventional format, atomic, no secrets
[ ] Container: multi-stage, non-root, pinned base image
[ ] Health checks: /healthz and /readyz implemented
[ ] Observability: metrics, tracing, request correlation
[ ] Timeouts: explicit on all external calls
[ ] Resilience: retries with backoff, circuit breaker where applicable
[ ] Migration: up/down, timestamped, append-only
[ ] Feature flag: new features gated, flag has removal date
[ ] SLO: response time targets defined and measured
[ ] Pipeline: CI passes all stages, no manual overrides
```

## APPENDIX B: STANDARDS SYNC SCRIPT

Place in the `standards` repo. Each project's bootstrap or CI calls this:

```bash
#!/usr/bin/env bash
# scripts/sync-standards.sh
# Pulls the canonical CLAUDE.md from the standards repo.
# Usage: ./scripts/sync-standards.sh [branch]

set -euo pipefail

STANDARDS_REPO="${STANDARDS_REPO_URL:?Set STANDARDS_REPO_URL env var}"
BRANCH="${1:-main}"
TARGET="./CLAUDE.md"

curl -fsSL "${STANDARDS_REPO}/raw/${BRANCH}/CLAUDE.md" -o "${TARGET}.new"

if ! diff -q "${TARGET}" "${TARGET}.new" > /dev/null 2>&1; then
  echo "[standards] CLAUDE.md updated from canonical source."
  mv "${TARGET}.new" "${TARGET}"
else
  rm "${TARGET}.new"
  echo "[standards] CLAUDE.md is up to date."
fi
```
