# Red-Team Report — seige-range full audit

> AUDIT mode. Live target: pre-existing `seige-range-api-1` container at `http://localhost:8000` (proxied via Nginx :3000 for SPA, but `/api/*` does not currently proxy in this deployment — PoCs target the API container directly via `docker exec`). Launch notes: `redteam/launch.md`.

## Scope
- Project: `/data/projects/seige-range`
- Surface tested: HTTP API at `:8000` — auth, MFA, password reset, webhook subscription create, docs/openapi exposure, audit ledger via direct DB.
- Out of scope: ttyd shells (separate trust boundary — flagged for follow-up), DinD socket pivot (no admin token captured during this run), challenge-container escape (intentional vulns).

## Attempts
| ID  | Threat | Class | PoC | Result | Severity |
|-----|--------|-------|-----|--------|----------|
| A1  | T11/T24 | CSP/HSTS header corruption | `redteam/poc/A1_csp_hsts_broken.sh.log` | **EXPLOITED** | Critical |
| A2  | T1/T15 | IP-rate-limit bypass on login | `redteam/poc/A2_no_ip_rate_limit.sh.log` | **EXPLOITED** | Critical |
| A3  | T1 | forgot-password email-bomb | `redteam/poc/A3_forgot_password_no_ratelimit.sh.log` | **EXPLOITED** | High |
| A4  | T5/T25 | Webhook SSRF (admin needed) | `redteam/poc/A4_webhook_ssrf.sh.log` | INDETERMINATE | — |
| A5  | T2/T19 | MFA bypass via legacy `/auth/login` | `redteam/poc/A5_mfa_bypass_legacy_login.sh.log` | **EXPLOITED** | Critical |
| A6  | T12 | `/docs`, `/redoc`, `/openapi.json` exposed | `redteam/poc/A6_docs_exposed.sh.log` | **EXPLOITED** | Medium |
| A7  | T2 | MFA-pending-token brute-force (no per-token cap) | `redteam/poc/A7_mfa_pending_token_no_cap.sh.log` | **EXPLOITED** | High |
| A8  | T1/T11 | Login-timing user enumeration | `redteam/poc/A8_login_timing_enumeration.sh.log` | **EXPLOITED** | High |
| A9  | T1 | Account-lockout case-bypass | `redteam/poc/A9b_case_bypass_fresh.sh.log` | MITIGATED | — |
| A10 | T11 | Audit ledger stores cleartext attempted email | `redteam/poc/A10_audit_email_leak.sh.log` | **EXPLOITED** | High |

## Exploited findings (deep-dive)

### A1 — Critical — Browser-side defences (CSP, HSTS) disabled by header-name corruption
- PoC: `redteam/poc/A1_csp_hsts_broken.sh.log`.
- Reproduction: any request to the running API returns `content-redacted-policy:` instead of `content-security-policy:`. Browsers ignore unknown header names; CSP is therefore inactive.
- Root cause: prior git-history rewrite collapsed substrings of `Security` to `REDACTED` in `backend/app/middleware/security_headers.py:88,108,113`. Class is `REDACTEDHeadersMiddleware`; emitted strings are `Strict-Transport-REDACTED` and `Content-REDACTED-Policy`.
- Recommended fix: rewrite to `SecurityHeadersMiddleware`, `Strict-Transport-Security`, `Content-Security-Policy`. Add a regression unit test that asserts the canonical header names appear on a sample response.

### A2 — Critical — No IP-based rate limit on `/api/v1/auth/login`
- PoC: 30 distinct emails from a single source, all 401, zero 429.
- Root cause: `auth_rate_limit` is defined in `backend/app/middleware/rate_limit.py:48-51` but wired into zero routers. Per-email lockout (`services/auth.py:96`) is the only throttle and is trivially bypassed by rotating emails. Doubly broken because the IP key would have been Nginx's IP anyway (AS-6).
- Recommended fix: `Depends(auth_rate_limit)` on `/api/v1/auth/login`, `/api/v1/auth/register`, `/api/v1/auth/forgot-password`, `/api/v1/auth/mfa/verify`. Trust `X-Forwarded-For` left-most after configuring `--forwarded-allow-ips` for uvicorn.

### A3 — High — Password-reset email-bomb
- PoC: 20 `forgot-password` requests against the same address, all 202.
- Root cause: the v1 router declares `429` in `responses=` but no rate-limit dependency. An attacker can mail-bomb any valid email or burn through the operator's SMTP budget.
- Recommended fix: per-IP and per-email rate limits (1/min, 5/hour) backed by the existing Redis sorted-set pattern.

### A5 — Critical — MFA bypass via the legacy v0 login endpoint
- PoC: register user → enrol MFA → confirm with valid TOTP → `mfa_enabled=true` → `POST /api/v1/auth/login` returns `mfa_required:true` (correct) → `POST /auth/login` returns a **full access + refresh token pair** with no second factor.
- Root cause: `backend/app/routers/auth.py:106-186` predates MFA and has no `if user.mfa_enabled` short-circuit. Both routers are still mounted (`backend/app/main.py:211`).
- Recommended fix: either remove the v0 login endpoint (cleanest), or port the MFA check + email-verification gate into v0, or hard-deprecate v0 with a 410. Any user with MFA enabled today is effectively unprotected against an attacker who has captured the password.

### A6 — Medium — `/docs`, `/redoc`, `/openapi.json` exposed (dev build, would-be-exposed in prod with current code)
- PoC: 200 from all three on the running API. Spec is 94 KB and enumerates every admin endpoint.
- Root cause: `FastAPI(title=...)` (main.py:154) doesn't disable docs in production. Live target is dev (`is_production=False`) but the production code path is identical — there's no env-gate.
- Recommended fix: `FastAPI(..., docs_url=None if settings.is_production else "/docs", redoc_url=..., openapi_url=...)`.

### A7 — High — MFA pending-token brute-force window
- PoC: 20 wrong TOTP submissions against one pending token, all 401, token still alive.
- Root cause: `backend/app/services/mfa.py:_verify_or_raise` calls `pyotp.TOTP(...).verify(code_str, valid_window=1)` per request and does not consume any attempt counter on failure. Pending token TTL is 5 minutes — at ~200 req/s an attacker can submit ~60 000 codes per token.
- Recommended fix: per-pending-token attempt counter in Redis (`pending:fails:<jti>` or hash of token); cap at 5; revoke the pending token on cap. Reduce pending-token TTL to 90 s.

### A8 — High — Login-timing user enumeration
- PoC: existing user → ~186 ms response; non-existent user → ~6 ms response. 30× separation; usable as an oracle without ever triggering the lockout.
- Root cause: `verify_password` (bcrypt) runs only when the user exists (`backend/app/routers/v1/auth.py:248` and `backend/app/routers/auth.py:122`). Confirmed live.
- Recommended fix: when the email matches no user, still call `pwd_context.verify(payload.password, _DUMMY_HASH)` to consume the same bcrypt time. Pre-compute `_DUMMY_HASH` at startup. Optionally: short-circuit before bcrypt only when the per-IP rate-limit would have rejected anyway.

### A10 — High — Audit ledger stores cleartext attempted-email on failed login
- PoC: query the running Postgres `audit_ledger` table — `payload->>'email'` contains the verbatim string the user (or attacker) typed, including bogus emails from unknown-user attempts.
- Root cause: `backend/app/routers/v1/auth.py:259` and `backend/app/routers/auth.py:133` insert `"email": payload.email` into the ledger row regardless of match.
- Recommended fix: on `AUTH_LOGIN_FAILED` with no matched user, store only `sha256(payload.email)` or omit the email entirely. On matched-user failures, the `actor_id` already identifies the account — drop the email field there too. §3.3 ("PII … masked in logs") applies.

## Indeterminate

### A4 — Webhook SSRF
- Confirmed: schema layer accepts `http://127.0.0.1:6379` and `http://169.254.169.254/...` (no IP filtering in `backend/app/schemas/v1/webhooks.py:WebhookCreateRequest`). Dispatch code in `backend/app/services/webhook_dispatch.py:_attempt_one` POSTs verbatim with no filtering.
- Endpoint requires admin role (`require_admin` in `routers/v1/webhooks.py:48`). No admin credentials were captured during this run, so the actual outbound dispatch wasn't exercised end-to-end.
- An admin token is a one-step compromise away: with A2 (no IP rate limit on login) + A8 (enumeration) + a weak password, the path is realistic.
- Classification: **INDETERMINATE in live run**; **EXPLOITABLE in code review (AS-3, Critical)** — the SSRF schema gap and the missing dispatch-time guard are demonstrable from source.

## Mitigated

### A9 — Account-lockout case-sensitivity bypass — MITIGATED
- The lockout (5 wrong tries on `rt_case@example.com`) was observed to persist when the attacker varied case (`RT_CASE@example.com`). The lockout key in Redis is keyed on the submitted-email string, so the keys *should* differ — but the response was 429 for both forms.
- Inspection suggests the running Postgres column collation (or an asyncpg-side normalisation) is treating the email as case-insensitive, so the user-found path runs and the `429` originates from the prior key's lockout state propagating through the same `record_failed_login(email, ...)` call. Either way, the bypass did not succeed in this live build.
- Note for hardening: lockout key normalisation is *accidentally* protective. Be explicit — normalise email to lowercase before keying the redis bucket.

## Residual risks (unmitigated)
- Webhook SSRF (A4) — code-confirmed; live confirmation requires admin token.
- Frontend XSS surfaces are not browser-defended (A1's CSP-broken consequence). A live XSS test against `/writeups` or display-name rendering would benefit from a browser-side PoC; outside this read-only audit's bounds.
- DinD orchestrator socket reachability from non-API containers (T21) — not tested live.
- ttyd shell session token discipline (T22) — not tested live.

## Verdict
**EXPLOITS-FOUND.** Three Criticals, four Highs, one Medium confirmed against the running platform.
