# QA Review (AUDIT mode) — seige-range

> Scope: test suite + CI config. Maps coverage to the threat model. Severity: **H**igh / **M**edium / **L**ow. Verdict: **INSUFFICIENT-TESTS** (relative to the standard, despite a generally strong test suite).

## Summary
- 21 unit tests, 33 integration tests under `backend/tests/`. Frontend Playwright E2E suite (`frontend/tests/e2e/`) targets the running stack.
- Backend `pytest.ini` enumerates ~30 `--cov` packages and enforces `--cov-fail-under=80` **locally**.
- **CI runs `tests/unit/` with `--no-cov`** (`.github/workflows/ci.yml:46`). The 80% gate is therefore *not* enforced by the merge gate. Integration tests do not run in CI (intake-confirmed).
- E2E suite present but not wired into CI.

The team's local testing rigour is real, but the standards in §5.1 and §6.3 require the 80% gate **and** the integration step on every merge. Today's CI does neither, which is the central QA finding.

## Findings

### QA-1 (High) — CI runs only `tests/unit/` with coverage disabled
**File:** `.github/workflows/ci.yml` (the `backend-tests` job step).

```yaml
run: |
  python -m pytest tests/unit/ -v --no-cov
```

`pytest.ini` is configured for the full standard (`--cov-fail-under=80`, 30+ covered packages), but the CI command line bypasses it with `--no-cov` and a narrowed `testpaths`. Result: the merge gate doesn't enforce coverage and runs only ~21 of 54 test files.

**Why now:** §5.1 (80% line coverage) and §11.2 (unit → integration → security all gating).

**Fix:** Drop `--no-cov` and `tests/unit/` from the CI step. Add a separate integration-tests job using a service-container Postgres + Redis (GitHub Actions supports services). Wire Playwright E2E as a third job using `docker compose up -d` against a built image.

### QA-2 (High) — Integration test path not wired in CI
**Source:** intake context confirms "Integration test path NOT yet wired in CI (testcontainers config pending)."

Integration tests are the only path that exercises real DB constraints, the rate-limit Redis flows, audit-ledger writes under concurrency, and the full router → service → infra cycle. Without them in CI, refactors that break, say, the unique constraint on `SolvedFlag` won't be caught at merge.

**Fix:** Either (a) commit a working testcontainers harness and gate on it, or (b) use a GitHub Actions `services:` block with Postgres + Redis sidecars and add a dedicated `integration-tests` job.

### QA-3 (High) — No regression test for the broken security headers (AS-1 / CR-1)
**Files searched:** `tests/integration/test_csp_report.py` exists but covers the `/csp-report` *intake* endpoint, not the *emitted* headers.

A unit test asserting `response.headers["Content-Security-Policy"]` exists and matches the expected directive would have caught AS-1 (the broken `Content-REDACTED-Policy` name) on the first run.

**Fix:** Add `tests/unit/test_security_headers.py` with assertions on canonical names: `Content-Security-Policy`, `Strict-Transport-Security` (prod only), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`. One test per header.

### QA-4 (High) — No test exercises the unused `auth_rate_limit` (AS-5)
The rate-limit module has no unit test confirming a 6th request within 60 s returns 429. Combined with the fact that the limiter is wired to *zero* routes, the missing coverage perfectly conceals the missing wire-up.

**Fix:** Add `tests/integration/test_auth_rate_limit.py` that posts 6 logins from the same IP within a minute and asserts the 6th is 429. The test will fail today — which is the desired outcome.

### QA-5 (High) — No SSRF test on webhook dispatch (AS-3)
No test exists that creates a webhook subscription with `target_url=http://127.0.0.1:6379` (or `http://169.254.169.254/`) and asserts the create returns 400 and/or the dispatch never connects. Today such a subscription is created and dispatched.

**Fix:** Add `tests/integration/test_webhook_ssrf.py` with cases for: loopback IPv4, loopback IPv6 (`::1`), link-local (`169.254.0.0/16`), private (`10/8`, `172.16/12`, `192.168/16`), DNS-rebinding (hostname resolves to a public IP once then a private IP at dispatch). Each must reject.

### QA-6 (Medium) — Validator sandbox tests don't probe escape attempts
**File:** `tests/unit/test_validator_sandbox.py`, `tests/unit/test_validator_subprocess_sandbox.py`.

These almost certainly check happy-path validator execution. Missing: a fork-bomb attempt, a memory-burst, a wall-clock-overflow, a `socket(AF_INET)` attempt, a file write to `/`. Each should fail under seccomp/ulimits in a way the harness can observe.

**Fix:** Add explicit "should-be-blocked" tests for each of the named escape primitives. They double as the blue-team's detection corpus.

### QA-7 (Medium) — No test confirming the MFA login bypass through v0 (AS-2)
There's no integration test that: (a) creates a user, enrols MFA, then (b) hits `POST /auth/login` (v0) and asserts the response either errors or returns a pending token. Today it returns a full token pair.

**Fix:** Add the test. It will fail, then guide the fix.

### QA-8 (Medium) — Playwright E2E suite isn't run by CI
**File:** `frontend/playwright.config.js`.

A working E2E gate would catch UI-side issues (axios `^` upgrades changing behaviour, etc.). Today it only runs locally.

**Fix:** Wire `npx playwright test` as a CI job behind `docker compose up -d` of the published image.

### QA-9 (Medium) — No test enforces "no `*-REDACTED` substrings in canonical header names"
A lint-style check (e.g., grep + assertion in CI) would catch the AS-1 class of corruption from future history rewrites.

**Fix:** Add a CI step: `grep -rE 'REDACTED' backend/app/ frontend/src/ scripts/ nginx/ --exclude-dir=__pycache__ && exit 1 || true`. (Inverted: should fail if any REDACTED match shows up; tune to allow intentional ones in test fixtures or schema docs.)

### QA-10 (Medium) — `flag-leak guard` covers flags but no equivalent for secrets in CI YAML
Intake: trufflehog runs and `flag-leak` runs. Neither catches AS-11 (cleartext `SECRET_KEY` / `ADMIN_PASSWORD` in `ci.yml`) because both look semantically distinct from a secret. A regex check for `SECRET_KEY:` or `PASSWORD:` in workflow files would be cheap.

**Fix:** Add a `gitleaks` rule or a custom step.

### QA-11 (Medium) — `--strict-config` and `--strict-markers` good, but no `pytest-randomly` for order independence
`tests/integration/` references global rows ("admin actions touch global rows" — `playwright.config.js`). Order-dependent tests are §5.2 violations. Add `pytest-randomly` and let the suite flush out order coupling.

### QA-12 (Low) — Coverage list omits `app.middleware.security_headers`, `app.middleware.rate_limit`, `app.services.mfa`, `app.services.password_reset`, `app.services.email_verification`
**File:** `backend/pytest.ini`.

The `--cov=` list enumerates services but skips key middleware and several Sprint-7-era services. They are likely transitively exercised by integration tests, but the coverage gate doesn't count them. Add them so the gate measures what's actually critical.

### QA-13 (Low) — No load/perf test for `/v1/auth/login` (bcrypt CPU exhaustion, T15)
A baseline `vegeta`/`hey` run pinning latency under 100 concurrent login attempts would catch bcrypt-related DoS regressions.

### QA-14 (Low) — Frontend has no SCA gate
No `npm audit` or `npm outdated` task. Adding a CI step closes AS-10 and gives the team a regression signal for future upgrades.

### QA-15 (Low) — `tests/conftest.py` is the only conftest; no `tests/integration/conftest.py` for service fixtures
Worth splitting: a sandbox-conftest can pre-stand testcontainers once per session.

## What looked right
- `pytest.ini` is rigorous *locally* — strict markers, strict config, ~30 packages under `--cov`, 80% gate.
- Test directory layout follows §5.1 (unit + integration + e2e separation, fixtures in `tests/fixtures/`).
- Integration tests cover MFA, email verification, password reset, GDPR exports, webhook retry+prune, scoring, multi-flag scoring, CSP report intake, metrics endpoint.
- Unit tests cover seccomp profiles, validators (sigma/yara/llm-signal), orchestration profiles/launcher/forbidden lists, webhook dispatch.
- E2E suite present (Playwright) with retry-on-failure + screenshots.
- `--strict-markers`, `--strict-config` enabled.
- Test harness exists for re-running the platform's own validators (`app/services/test_harness/`) — good practice.
