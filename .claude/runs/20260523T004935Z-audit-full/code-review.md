# Code Review (AUDIT mode) — seige-range

> Scope: backend platform code (excluding `challenges/`, `examples/`, gitignored output). Findings are observations against CLAUDE.md §1, §2, §6, §7, §8, §12, §16. Severity: **C**ritical / **H**igh / **M**edium / **L**ow.

## Summary of verdict
**REQUEST-CHANGES.** Two Critical findings (broken `Security-Headers` middleware, and admin docs/openapi exposed unconditionally). Several High and Medium issues around module size, dependency pinning, and CI gates.

## Findings

### CR-1 (Critical) — Security headers middleware emits non-standard header names
**File:** `backend/app/middleware/security_headers.py:88,108,113`; wired in `backend/app/main.py:167,173`.

The middleware class is named `REDACTEDHeadersMiddleware` and emits two headers named `Strict-Transport-REDACTED` and `Content-REDACTED-Policy`. These are *not* the canonical `Strict-Transport-Security` and `Content-Security-Policy` headers; browsers will not recognise them. **HSTS and CSP are effectively disabled in every environment, including production.**

Root cause appears to be the git-history rewrite (intake context: "scrub `CTF{...}` literals") collapsed the substring `Security` to `REDACTED` in this file along with the class/import names. The other security headers (`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `X-Content-Type-Options`) are still correct, but the two most important ones for browser-side defence are broken.

**Why now:** §3.3 mandates HSTS and CSP on every response. Loss of CSP also means the XSS-defence-in-depth (no `unsafe-inline`/`unsafe-eval`) is not actually enforced.

**Fix:** Restore the literal strings `"Strict-Transport-Security"`, `"Content-Security-Policy"`, `SecurityHeadersMiddleware` (class name), and corresponding docstring references in `security_headers.py`, and update the import in `main.py`. Add a regression unit test asserting both headers appear on a sample response.

---

### CR-2 (Critical) — `/docs`, `/redoc`, `/openapi.json` exposed unconditionally
**File:** `backend/app/main.py:154`.

```python
app = FastAPI(title="Siege Range API", version="2.5.0", lifespan=lifespan)
```

No `docs_url`/`redoc_url`/`openapi_url` arguments. The full OpenAPI surface (including admin endpoints) is reachable by unauthenticated callers in every environment. The security-headers middleware additionally *exempts* these paths from CSP (`_DOC_PATHS` in `security_headers.py:27`), so even when CR-1 is fixed they'd remain CSP-free. Repo is public so the spec isn't a secret per se, but exposing it in production gives attackers free reconnaissance.

**Fix:** When `APP_ENV == "production"` pass `docs_url=None, redoc_url=None, openapi_url=None`. Or, alternately, mount them behind admin auth.

---

### CR-3 (High) — `auth_rate_limit` defined but never wired
**File:** `backend/app/middleware/rate_limit.py:48-51` (defined); zero callers in `backend/app/routers/`.

`auth_rate_limit` provides IP-based 5-req/60s throttling for auth endpoints. It is imported in `backend/app/routers/auth.py:25` but is **not** added as a `Depends(...)` on any route. Login is protected only by the per-account lockout in `services/auth.py:96-103`, which keys on `email` — an attacker can credential-stuff different accounts from a single IP without ever hitting the lockout. `general_rate_limit` is also unused (zero references).

**Fix:** Add `_rl=Depends(auth_rate_limit)` to `/auth/login`, `/v1/auth/login`, `/auth/register`, `/v1/auth/register`, `/v1/auth/forgot-password`, `/v1/auth/mfa/verify`. Add `general_rate_limit` to authenticated routers that aren't already rate-limited.

---

### CR-4 (High) — Rate-limit keys use `request.client.host` directly
**File:** `backend/app/middleware/rate_limit.py:43, 49, 55`.

Behind Nginx (the default deployment) `request.client.host` is always the reverse-proxy IP. Every external user shares one key. `auth_rate_limit` keys on `ip = request.client.host` → the 5 req/60s budget is global across all attackers from any origin.

**Fix:** Trust a configurable `X-Forwarded-For` (or `X-Real-IP`) from a known proxy hop. Pydantic-settings already loads `ALLOWED_ORIGINS`; add an `TRUSTED_PROXY_HOPS` setting and use `ProxyHeadersMiddleware` (Uvicorn ships one) or compute the right-most non-proxy IP from `X-Forwarded-For`. Document the trust boundary.

---

### CR-5 (High) — Module size violations (§1.1: no file >300 lines, no function >50)
- `backend/app/models.py` — 562 lines. Single file holds every ORM model. Split by domain (user/auth, challenge/instance, scoring/solve, audit/ledger, webhook).
- `backend/app/services/flag_submission.py` — 614 lines. Re-decompose: `single_flag.py`, `multi_flag.py`, `persist.py`, `announce.py`.
- `backend/app/services/webhook_dispatch.py` — 512 lines. Split delivery / replay / retention.
- Several other services likely over the budget; spot-checked above are the worst.

**Fix:** Decompose along the suggested seams. Update import sites. This is debt — not a security bug — but the standard is binding.

---

### CR-6 (High) — Frontend dependencies use floating `^`/`~` ranges
**File:** `frontend/package.json`.

Every entry in `dependencies` and `devDependencies` uses `^` ranges. CLAUDE.md §3.4: "Pin all dependency versions exactly. No floating ranges (`^`, `~`, `*`)." `package-lock.json` resolves a snapshot, but the manifest still drifts when `npm install` runs against a fresh lockfile.

**Fix:** Replace every `^X.Y.Z` with `X.Y.Z`. Add `npm ci` (not `npm install`) to the frontend-build CI job (verify in CI workflow). Add `npm audit --omit=dev --audit-level=high` step.

---

### CR-7 (High) — CI runs unit tests only; no coverage gate, no dep audit
**File:** `.github/workflows/ci.yml:36-46`.

```yaml
run: |
  python -m pytest tests/unit/ -v --no-cov
```

CLAUDE.md §5.1 mandates 80% line coverage; CI explicitly disables coverage with `--no-cov`. §3.4 mandates `pip audit`/`npm audit` per commit; neither is present in the visible CI definition. §11.2 requires the integration-test stage; intake confirms it isn't wired.

**Fix:** Restore `--cov` with `--cov-fail-under=80`. Add a `dep-audit` job that runs `pip-audit -r backend/requirements.txt --strict` and `npm audit --audit-level=high` in `frontend/`. Wire `pytest tests/integration/` behind testcontainers.

---

### CR-8 (Medium) — Composition root vs. ambient `get_settings()` global
**File:** `backend/app/services/auth.py:16` `settings = get_settings()` at module import; same pattern in many services.

Settings are loaded at import time as a module-level global. Tests that need to vary configuration must monkey-patch `app.config.get_settings` *before* any service-layer module imports — fragile. §1.4 expects constructor injection; the current pattern is a service-locator/global.

**Fix:** Pass settings through DI (`Depends(get_settings)`). Or at minimum, call `get_settings()` inside each function rather than at module scope. (`auth.py` is the lightest fix.)

---

### CR-9 (Medium) — Inconsistent v0/v1 auth surface — legacy `/auth/*` parallel to `/v1/auth/*`
**Files:** `backend/app/routers/auth.py` (v0 — 308 lines) vs `backend/app/routers/v1/auth.py` (v1 — 1013 lines).

Two router modules implement near-identical login/register/refresh flows with subtle drift: v0 has no MFA branch, no email-verification gate, returns raw dicts (no `extra="forbid"` schema). The v0 router is still mounted (`main.py:211`). API surface duplication doubles the audit/test burden and risks behavioural drift (e.g. MFA bypass via v0).

**Fix:** Mark v0 as deprecated; require it to either delegate to v1 or be removed. At minimum, v0 must enforce the same MFA gate as v1 — currently if a user has MFA enabled, `/auth/login` (v0) returns a full token pair, bypassing the second factor. **This is also a security finding (see APPSEC report).**

---

### CR-10 (Medium) — Logout uses bare `except Exception: pass`
**File:** `backend/app/routers/auth.py:249-250` and `backend/app/routers/v1/auth.py:425-426`.

```python
except Exception:
    pass
```

CLAUDE.md §2.1 forbids silent swallowing. Logout should still audit the failure ("invalid logout token") rather than disappear.

**Fix:** Replace bare-except with explicit `(JWTError, KeyError, ValueError)` and emit an audit row on the failure path. Logging "token swallowed" at WARN is fine.

---

### CR-11 (Medium) — `webhook_dispatch._attempt_one` catches `Exception` then continues
**File:** `backend/app/services/webhook_dispatch.py:263`.

Documented as "never propagate to caller", and it logs at ERROR — acceptable per the standard's letter. But the catch is very broad; a programming bug (e.g. attribute error after a model refactor) becomes a delivery silently-failed forever. Narrow to `(httpx.HTTPError, OSError, asyncio.TimeoutError)`.

---

### CR-12 (Medium) — `db.execute` of literal flush within concurrent tasks
**File:** `backend/app/services/webhook_dispatch.py:113`.

The code uses `asyncio.gather(*( _attempt_one(...) ...))` to fan out HTTP. The dispatch itself is fine (no DB writes inside the gathered tasks), but the comment at line 109 indicates a previously-suspected race. Document or assert that the serial post-write loop is the *only* DB mutation path. (Note for reviewer: implementation is correct as-is; flag only as a maintainability comment.)

---

### CR-13 (Medium) — `os` imported in admin.py but env-vars accessed directly in a router
**File:** `backend/app/routers/admin.py:2` (`import os`).

If env-vars are read here rather than via `get_settings()`, that's a §8.1 violation (config layer skipped). Did not exhaustively read every admin endpoint; flag for verification.

---

### CR-14 (Medium) — CORS `allow_credentials=True` with config-controlled origins is fine, but missing `Vary: Origin` discipline
**File:** `backend/app/main.py:187-195`.

Starlette CORS adds `Vary: Origin` automatically only when the origin is in the allowlist; verify caches downstream of Nginx honour this. Add a unit test that confirms `Vary: Origin` is present on every CORS response. Also: `max_age=600` is short — fine.

---

### CR-15 (Low) — Inline FastAPI router imports inside `lifespan()`
**File:** `backend/app/main.py:99-124` — many `from app.services... import ...` inside the `lifespan` coroutine. Hides startup-time dependency graph. Move to top-of-file or document the lazy-import rationale.

---

### CR-16 (Low) — `f"{settings.frontend_url()}/reset-password?token={cleartext}"` builds URL with f-string
**File:** `backend/app/routers/v1/auth.py:490-492`, `:986-988`.

URL-safe-base64 tokens are safe for query-string interpolation, but `urllib.parse.urljoin` + `urlencode` is more robust against future changes (e.g. an admin reconfigures `frontend_url()` to include a trailing query string).

---

### CR-17 (Low) — Tests directory imports may rely on `.venv-test` installs (egg-info present at repo root)
**File:** `backend/siege_backend.egg-info/`.

This sub-directory is checked in (visible in repo root listing). `*.egg-info/` should be in `.gitignore` (it *is*) but the directory is still present — either committed before being ignored, or surviving the rewrite. Either way: remove from git. Not security-critical.

---

### CR-18 (Low) — Long-lived `httpx.AsyncClient` not reused
**File:** `backend/app/services/webhook_dispatch.py:189`.

`_default_http_client` returns a new `httpx.AsyncClient` per attempt, then closes it. For a high-fanout receiver pool, reusing a module-scoped client cuts TCP/TLS setup. Optimisation, not a bug.

---

### CR-19 (Low) — `_settings` module-global at `main.py:31`
Captures settings once at import. Same pattern as CR-8.

---

### CR-20 (Low) — No `Vary: Authorization` header observed
Authenticated responses cached by intermediate proxies could leak per-user data. Verify `Cache-Control: private, no-store` on authenticated GETs (`/v1/me`, `/v1/scoreboard`).

## What looked right
- `app/config.py` is excellent: fail-fast settings, explicit placeholder denylist, strict CORS-empty-in-prod gate, REQUIRE_IMAGE_DIGEST default-on.
- `app/services/auth.py` uses `algorithms=[ALGORITHM]` allowlist — JWT alg-confusion (T3) is mitigated.
- `password_reset.py` and `email_verification.py` are tidy: 32-byte `secrets.token_urlsafe`, sha256 at rest, single-use via `used_at`, TTL via settings.
- `mfa.py` uses `pyotp` with recovery codes hashed and `valid_window=1` (acceptable clock skew).
- `flag_submission.py` correctly uses Pydantic-typed errors and maps them to 4xx via the router.
- Seccomp profiles validated at boot and abort on parse failure.
- Image digest pinning enforced by default; `REQUIRE_IMAGE_DIGEST=false` only allowed in dev.
- Submission idempotency rests on a unique constraint on `(user_id, challenge_id, flag_id)` — good.
- Audit ledger is comprehensive: register, login (success/fail), refresh, logout, password-reset request+redeem, password-change, MFA enroll/confirm/disable/verify (success/fail), email-verify request+redeem, flag-submit pass/fail. Every state-changing path emits a row.
