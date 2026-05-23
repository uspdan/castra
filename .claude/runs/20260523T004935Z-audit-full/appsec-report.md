# AppSec Review (AUDIT mode) — seige-range

> Scope: platform code (everything outside `challenges/` and `examples/`). Maps findings to STRIDE threats from `threat-model.md`. Severity: **C**ritical / **H**igh / **M**edium / **L**ow. Verdict: **FINDINGS-MUST-FIX**.

## Critical

### AS-1 (Critical, T11/T24) — CSP and HSTS are not emitted (header names corrupted to `*-REDACTED`)
**File:** `backend/app/middleware/security_headers.py:8-9, 88, 108, 113`, wired at `backend/app/main.py:167,173`.

The middleware sets `response.headers["Strict-Transport-REDACTED"]` and `response.headers["Content-REDACTED-Policy"]`. Browsers do not recognise these header names; the headers are effectively absent. The strict CSP that the file *constructs* (`script-src 'self'`, no `unsafe-eval`, etc.) is therefore never enforced — XSS in any user-rendered surface (writeups markdown, hint markdown, display names, notification text) lacks the browser-side defence-in-depth required by §3.3. HSTS is similarly broken in production, leaving first-visit users vulnerable to TLS downgrade.

Confirmed via `git show HEAD:backend/app/middleware/security_headers.py` — not a render artefact. The same scrub mangled `app/main.py:167,173` (`REDACTEDHeadersMiddleware`) and the docstring of `app/security/__init__.py` (cosmetic — the package still imports as `security`).

**Affected paths:** every HTTP response except `/docs`, `/redoc`, `/openapi.json`.

**Fix:** Replace `Strict-Transport-REDACTED` → `Strict-Transport-Security`, `Content-REDACTED-Policy` → `Content-Security-Policy`, and rename `REDACTEDHeadersMiddleware` → `SecurityHeadersMiddleware`. Add a regression unit test asserting both headers are present on a sample 200, and that CSP contains `default-src 'self'`. Cross-cutting: enable the `/csp-report` endpoint testing while you're there.

### AS-2 (Critical, T19) — Legacy `/auth/login` issues full token pair when MFA is enabled
**File:** `backend/app/routers/auth.py:106-186` (no MFA check).

The v0 router doesn't consult `user.mfa_enabled`. If a user has MFA fully enabled but logs in via `/auth/login` (still mounted at `main.py:211`), they bypass the second factor. The v1 router (`v1/auth.py:309-327`) correctly short-circuits to a pending-token response, but the legacy router is parallel-mounted and reachable.

**Fix:** Either (a) delete the v0 login route, (b) make it 410 Gone for accounts with `mfa_enabled=True`, or (c) port the MFA short-circuit in. The legacy register route also predates email-verification gating (`REQUIRE_EMAIL_VERIFIED`) and similarly bypasses it.

### AS-3 (Critical, T5/T25) — Webhook dispatch has no SSRF guard
**File:** `backend/app/services/webhook_dispatch.py:79-153` and `backend/app/routers/v1/webhooks.py:42-58`, schema `backend/app/schemas/v1/webhooks.py` (uses `HttpUrl` only).

`target_url` is admin-supplied and dispatched verbatim. The schema validates URL shape but does not block:
- `http://127.0.0.1:<any port>` — pivot into the API container itself, the orchestrator, Redis (`6379`), Postgres (`5432`), `/metrics`, internal admin endpoints if any bind on loopback.
- `http://169.254.169.254/latest/meta-data/...` — IMDS exposure if deployed on AWS/GCP.
- `http://10.x.x.x` / `192.168.x.x` / `172.16.x.x` / `[::1]` — sibling services on the internal network.
- DNS-rebinding: a `target_url` that resolves to a public IP at validation time and a private IP at dispatch time.

Yes, only admins can create webhooks — but the platform allows operator-supplied webhook URLs as a feature, and an admin account compromise becomes a host-network pivot via `webhook_dispatch.deliver_event`. The httpx call doesn't even set `follow_redirects` (default False — small mercy), but the initial GET still hits whatever the admin types.

**Fix:** In a single helper `_validate_outbound_url(url)`:
1. Parse with `urlsplit`. Require `scheme in {"http","https"}` and a hostname.
2. Resolve the hostname with `socket.getaddrinfo`; reject if any resulting IP is in `ipaddress.ip_address(x).is_private`, `.is_loopback`, `.is_link_local`, `.is_multicast`, `.is_reserved`, or `169.254.0.0/16`.
3. Pass the resolved IP back to httpx by binding the socket to that IP (`httpx.AsyncClient` with a custom `transport`), or by passing an `Host` header and connecting to the IP literal. This defeats DNS rebinding.
Apply at create time (immediate UX feedback) AND at dispatch time (DNS rebinding defence). Verify TLS by default.

### AS-4 (Critical, T11) — Audit ledger logs the email submitted on `AUTH_LOGIN_FAILED`
**File:** `backend/app/routers/v1/auth.py:258-262, 295`; same in `routers/auth.py:132-135`.

The ledger row's `payload` includes `"email": payload.email` on every failed login — including the *attempted* email when no user exists. A typo by a real user leaks their actual email + the misspelled candidate into the audit DB. More importantly, an attacker enumerating accounts gets a clean "did this email exist?" oracle by reading the audit ledger if any admin/observer endpoint exposes it (verify by checking `app/routers/admin.py /audit` reads). Even without disclosure to the attacker, storing the typed-in cleartext on a *failed* login arguably violates §3.3 ("PII and sensitive fields are encrypted at rest and masked in logs").

**Fix:** On the `AUTH_LOGIN_FAILED` row, hash the email (`sha256`) before storing or store only the user_id (None if no match). Same applies to the `forgot-password` no-match path which also stores the cleartext email.

## High

### AS-5 (High, T1/T15) — No IP-based rate limit on auth endpoints
**File:** `backend/app/middleware/rate_limit.py:48-51` (defined, unused).

`auth_rate_limit` exists but is wired into zero routes. Defense-in-depth against credential stuffing relies entirely on the per-email lockout (`services/auth.py:96-103`), which an attacker bypasses by rotating emails. Combined with AS-6 (`request.client.host`) this is doubly broken.

**Fix:** Add `_rl=Depends(auth_rate_limit)` to login, register, forgot-password, reset-password, mfa/verify, and mfa/disable.

### AS-6 (High, T1) — Rate limiter trusts the wrong client IP behind Nginx
**File:** `backend/app/middleware/rate_limit.py:43, 49, 55`.

`request.client.host` is the upstream-hop IP (Nginx) when the API runs behind the reverse proxy, which is the default deployment (`nginx/` is in repo, prod compose mounts it). Every external client shares one rate-limit bucket; once any bucket fills, *all* legitimate traffic is throttled.

**Fix:** Run uvicorn with `--forwarded-allow-ips=<nginx-ip>` (or set `FORWARDED_ALLOW_IPS` env) so Starlette uses `X-Forwarded-For`'s left-most entry. Or write a small middleware that extracts the rightmost-trusted hop. Add a `TRUSTED_PROXY_HOPS` setting.

### AS-7 (High, T2) — MFA pending token TTL of 5 min, but no re-issue limit
**File:** `backend/app/services/mfa.py:40, 235-253`.

After password success, the user gets a 5-minute pending JWT. If an attacker steals or guesses the pending token (it's a JWT; if they have the SECRET_KEY they're already compromised, but the *user* may also leak the token via paste/screen) they have 5 minutes to brute-force the 6-digit TOTP. With `valid_window=1` that's ~30 candidate codes per second of clock window and no per-pending-token rate limit. 1 million TOTP candidates / 30 valid at any instant ≈ 33k tries to maybe hit. Realistic? Marginal. Worth adding a "max attempts per pending token" counter.

**Fix:** Persist a counter keyed on the pending token (or, better, on `user_id + iat`); cap at 5 wrong codes and invalidate. Also reduce pending TTL to 90 s.

### AS-8 (High, T1) — `forgot-password` has no rate limit
**File:** `backend/app/routers/v1/auth.py:452-542`.

Despite the `429` mentioned in the route's `responses=` dict, the endpoint never raises 429 — there's no rate-limit `Depends(...)`. An attacker can email-bomb any user by replaying `POST /api/v1/auth/forgot-password` with their address. Also enables SMTP-billing attacks against the operator and enumeration if SMTP delivery timing differs between match/no-match.

**Fix:** Per-IP and per-email rate limit (e.g. 1/min, 5/hour). Use the existing Redis sorted-set pattern.

### AS-9 (High, T12) — `FastAPI()` constructed without disabling docs in prod
**File:** `backend/app/main.py:154`.

`docs_url`, `redoc_url`, `openapi_url` all default to enabled. The OpenAPI spec lists every admin endpoint. Repo is public, so the spec isn't inherently sensitive — but exposing it in production handles attackers a complete API map plus error-code probabilities and schema details for free.

**Fix:** In production, pass `docs_url=None, redoc_url=None, openapi_url=None`, or mount them behind `require_admin`.

### AS-10 (High, T26) — Frontend dependencies use floating ranges; no `npm audit` in CI
**File:** `frontend/package.json`; CI workflow.

Every entry uses `^`. `package-lock.json` pins, but the manifest invites drift on any fresh install. CI does not run `npm audit`. Section 3.4 requires both pinning and dep audit.

**Fix:** Replace `^X.Y.Z` with `X.Y.Z`. Add `npm audit --omit=dev --audit-level=high` to `frontend-build` job. Force `npm ci` (lockfile-driven) over `npm install`.

### AS-11 (High, T11) — `SECRET_KEY` and `ADMIN_PASSWORD` echoed into CI workflow as cleartext
**File:** `.github/workflows/ci.yml` (around step "run pytest").

```yaml
env:
  SECRET_KEY: ci-test-secret-do-not-use-in-prod-0123456789abcdef0123456789abcdef
  ADMIN_PASSWORD: CIAdminPasswordA1!
```

These are *test-only* and have no value outside the CI environment, so impact is limited — but they're committed in plaintext to a public repo and they make a tempting target for a copy-paste into a real deploy by mistake. They also normalise "secret in YAML" patterns.

**Fix:** Generate per-job ephemeral values: `SECRET_KEY: ${{ secrets.CI_TEST_SECRET_KEY }}` or `run: echo "SECRET_KEY=$(openssl rand -hex 32)" >> $GITHUB_ENV`. Update the placeholder denylist in `app/config.py` if you switch to a published pattern.

### AS-12 (High, T7/T8) — Validator-subprocess sandbox: profile coverage not audited end-to-end
**Files:** `backend/app/services/validator_sandbox.py`, `backend/app/services/validator_subprocess_runner.py`, `backend/app/security/seccomp/`.

Seccomp profiles validated at boot is good (`main.py:_validate_seccomp_profiles_or_exit`). But the validator process model — fork a Python subprocess running an entry-pointed validator — relies on Linux capabilities + seccomp + ulimits applied via subprocess args. Without a test that:
  - the subprocess cannot `open` a file outside its allowed directory,
  - cannot bind a socket,
  - cannot exceed its memory budget (cgroup-enforced, not soft),
  - is killed when it exceeds wall-clock time,
…the assumption is brittle. Code-level review didn't surface a `--network=none` analog or `setrlimit` calls (subprocess-runner is Python's own process, not a container).

**Fix:** Either run validators in a one-shot container (preferred — already have Docker), or add explicit `prlimit`/`setrlimit` + `unshare(CLONE_NEWNET)` calls + a thorough test in `tests/unit/test_validator_sandbox.py` that demonstrates each restriction triggers. Add a red-team-style probe (T7) in the QA suite.

### AS-13 (High, T22) — ttyd shell auth path not reviewed; risk of session hijacking
**File:** `backend/app/services/workstation.py` (not deep-read), `infra/workstation/`.

Intake says: "ttyd-backed browser shells". I did not trace the full path from "user clicks Open Shell" to "ttyd accepts the WS upgrade". If the per-shell URL embeds a session token without short TTL + per-instance scoping + binding to the user's primary JWT, a leaked URL grants RCE inside the challenge container (which itself isn't a platform escalation, but it lets one student paste-grief another's session). Worse, if the ttyd container shares any mount with the platform's `secrets/` it's a flag-leak.

**Fix:** Audit (a) how the shell URL/token is issued, (b) how ttyd verifies it, (c) what mounts the shell container has. Either confirm clean or surface as a separate finding.

## Medium

### AS-14 (Medium, T11) — Bare `except: pass` in logout paths (also flagged as CR-10)
**File:** `backend/app/routers/auth.py:249-250`, `backend/app/routers/v1/auth.py:425-426`.

Maps to §2.1 ("No silent swallowing").

### AS-15 (Medium, T3) — `python-jose==3.3.0` is on the watch list
`python-jose` has had a string of weakly-typed JWT issues. The platform's mitigation (explicit `algorithms=[ALGORITHM]`) handles alg-confusion, but **upgrading to `PyJWT` 2.x** is the modern recommendation and removes the entire class. Not blocking; track.

### AS-16 (Medium, T11) — Audit-ledger payloads include reasons that could include sensitive substrings
**File:** `backend/app/routers/v1/auth.py:580` (reset-redeem failure stores `reason=str(exc)`).

`InvalidResetToken` exceptions carry short reasons (`"token not found"`, `"token expired"`) — safe — but if the message ever evolves to include the cleartext token, the ledger leaks it. Document the contract.

### AS-17 (Medium, T13) — Webhook dispatch sends bearer-equivalent secret as HMAC body sig — good — but TLS verification not explicit
**File:** `backend/app/services/webhook_dispatch.py:189-190`.

`httpx.AsyncClient(timeout=5.0)` — defaults to `verify=True`, which is correct, but make it explicit (`verify=True`) so a future refactor doesn't silently drop it. Add `follow_redirects=False` to prevent 302-to-internal-IP exfil.

### AS-18 (Medium, T21) — DinD orchestrator reachable on `tcp://orchestrator:2376`
**File:** `backend/app/config.py:DOCKER_HOST` default, `docker-compose.prod.yml` (not deep-read).

`tcp://orchestrator:2376` is plaintext TCP. Any container on the docker network can dial it. Network-policy review is required: only the API container should reach port 2376. If using `docker-socket-proxy` as alluded to in `main.py:101` ("`docker-socket-proxy`"), confirm its allowed-operations list excludes `POST /containers/create` from anything but the API, and excludes `--privileged` always.

**Fix:** Audit `docker-compose.prod.yml` for network segmentation. Convert to TLS mutual auth (`2376` is the canonical TLS port; verify certs are present in the orchestrator config).

### AS-19 (Medium, T13) — Webhook `events` allowlist includes `auth.data.export` — confirm the event payload isn't a privacy leak
**File:** `backend/app/schemas/v1/webhooks.py:_KNOWN_EVENTS`.

A subscription to `auth.data.export` (or `*`) means every PII export operation is mirrored to an operator-configured URL. Verify the event payload omits the PII itself and includes only "user_id requested export".

### AS-20 (Medium, T11) — `_PLACEHOLDER_VALUES` denylist is good but doesn't cover obvious variants
**File:** `backend/app/config.py:_PLACEHOLDER_VALUES`.

`"changeme"` but not `"changeme!"` / `"ChangeMe"` / `"Welcome1!"`. Improve with a `.lower()` comparison and add a few more entries from the OWASP top-passwords list.

### AS-21 (Medium, T11) — `models.py` 562-line single file — code-review concern doubles as audit-fatigue risk
Splitting reduces the chance a future change to one model accidentally widens another's surface (e.g. exposes a column in `User` that shouldn't ship in `me`).

### AS-22 (Medium, T16) — `google-re2` ships, but stdlib `re` is the documented fallback (`requirements.txt` comment).
A future deploy on an arch without a wheel silently falls back to ReDoS-vulnerable `re`. Document the fallback as a release-blocker — or remove it.

## Low

### AS-23 (Low) — Missing `Cache-Control: private, no-store` on authenticated GETs
Confirm header is set on `/v1/me`, `/v1/scoreboard`, `/v1/progress`, etc.

### AS-24 (Low) — `weasyprint` 61.0 / `Jinja2` 3.1.6 — both current as of this audit.
No CVEs flagged at the pinned versions. Re-run `pip-audit` regularly.

### AS-25 (Low) — `apscheduler==3.10.4` — scheduled jobs run in-process.
Confirm jobs do not handle untrusted data without re-validation; jobs are an internal trust boundary too.

### AS-26 (Low) — `egg-info/` committed to repo (`backend/siege_backend.egg-info/`) — leaks package metadata.
Should be in `.gitignore` AND removed from the working tree.

## What looked right
- JWT decode uses an explicit `algorithms=[...]` allowlist (T3 mitigated).
- Password reset tokens: random 32 bytes, sha256-hashed at rest, single-use via `used_at`, TTL configurable, generic 400 on failure.
- Email verification token follows the same pattern.
- MFA TOTP uses `valid_window=1` and recovery codes stored as sha256 hashes.
- Login response is uniform between "no such user" and "wrong password" (no timing-distinguishable path observed; bcrypt still runs only when user exists, which is a small timing oracle — see AS-1 in cheat-detector for the timing-attack debt).
- Refresh-token blacklist via Redis with TTL = remaining exp.
- Image-digest pinning gate (`REQUIRE_IMAGE_DIGEST=true` default) with post-pull `RepoDigests` verification (`launcher._verify_post_pull_digest`).
- Submission idempotency via DB unique constraints and a flush-then-recheck multi-flag pattern.
- Validator subprocess seccomp profiles validated at boot (`_validate_seccomp_profiles_or_exit`).
- Comprehensive audit ledger coverage on auth + MFA + flag + admin events.
- Writeups path uses `bleach.clean` with explicit `ALLOWED_TAGS` and `strip=True`.
- Webhook payload signed with HMAC-SHA256, delivery_id replay header, sorted-key canonical JSON.
