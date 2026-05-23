# Project Security Audit — seige-range

## Status
**FINDINGS**

## Scope
- Audit type: project-wide (read-only)
- Run id: `20260523T004935Z-audit-full`
- Project: `/data/projects/seige-range`
- Commit: `117eb3e1c919f71ef7bbd2efdcaaa6a80559a42f` (branch `main`, clean tree)
- Mode: AUDIT (no source files modified)
- Exclusions: `challenges/`, `examples/` (intentionally-vulnerable training material — by design); `frontend/node_modules/`, `frontend/dist/`, `frontend/test-results/`, `frontend/playwright-report/`, `__pycache__/`, `.venv*/`, `dist/`, `build/`, `dind_data/`, `backups/`, `nginx/certs/`, `siege_backend.egg-info/` (gitignored output / sealed-secrets content).
- Live target: pre-existing `seige-range-api-1` container at `http://localhost:8000` (red-team PoCs ran here).

## Summary
- Critical: **4** (R1, R3, R5, R-RT1)
- High: **15**
- Medium: **9**
- Low: **5**
- Exploited (red-team, live): **8**
- Silent (blue-team — exploited with no log trace): **1** (CSP/HSTS broken — A1)
- Indeterminate (red-team, requires admin in this run): **1** (webhook SSRF — A4)

## Top fixes (prioritised)

1. **`backend/app/middleware/security_headers.py:108,113` + `app/main.py:167,173` — restore canonical CSP/HSTS header names.** Replace `Strict-Transport-REDACTED` → `Strict-Transport-Security`, `Content-REDACTED-Policy` → `Content-Security-Policy`, class `REDACTEDHeadersMiddleware` → `SecurityHeadersMiddleware`. **Why now:** browsers ignore the corrupted names; CSP and HSTS are silently disabled on every response — verified live. Single hour of work plus a regression unit test.
2. **`backend/app/routers/auth.py:106-186` — kill or gate the legacy `/auth/login` route.** It bypasses both MFA (verified live — full token pair returned to an MFA-enabled user) and the `REQUIRE_EMAIL_VERIFIED` gate. Cleanest fix: delete the v0 login (and the parallel v0 register/refresh/logout while you're there). Alternative: 410 Gone, or port the v1 short-circuits in.
3. **`backend/app/middleware/rate_limit.py` + auth/forgot-password/MFA-verify routes — wire IP-based rate limits and trust `X-Forwarded-For` from Nginx.** Add `_rl=Depends(auth_rate_limit)` to `POST /api/v1/auth/login`, `/register`, `/forgot-password`, `/mfa/verify`. Set `--forwarded-allow-ips` on uvicorn or compute the real client IP from `X-Forwarded-For`. Verified live: 30 logins from one source produced zero 429s; 20 forgot-password requests produced zero 429s.

## Risk register

| ID | Severity | Area | File:line | Finding | Source | Recommended fix |
|----|----------|------|-----------|---------|--------|-----------------|
| R1  | Critical | browser security | `backend/app/middleware/security_headers.py:88,108,113` | HSTS + CSP emitted under corrupted names (`Strict-Transport-REDACTED`, `Content-REDACTED-Policy`); browsers ignore them. **Silent compromise** — confirmed live. | appsec AS-1, code-review CR-1, red-team A1, blue-team B1 | Restore canonical header names; rename middleware class; add a regression unit test on canonical names; add startup self-check that emits a Prometheus gauge `siege_security_headers_ok`. |
| R2  | Critical | reconnaissance | `backend/app/main.py:154` | `FastAPI()` constructed without `docs_url=None/redoc_url=None/openapi_url=None`. `/docs`, `/redoc`, `/openapi.json` exposed in every environment (verified live; 200 + 94 KB spec). | appsec AS-9, code-review CR-2, red-team A6 | In production set `docs_url=None`, etc., or mount behind `Depends(require_admin)`. |
| R3  | Critical | auth | `backend/app/routers/auth.py:106-186` | Legacy v0 login route bypasses MFA and email-verification gate. Verified live: enrolled MFA, then v0 returned full token pair. | appsec AS-2, red-team A5, codex pass-1 F3, codex C-M2 | Delete v0 router (preferred) or port MFA + email-verification gates. |
| R4  | Critical | SSRF | `backend/app/services/webhook_dispatch.py:79-153`, `backend/app/schemas/v1/webhooks.py` | Admin-supplied `target_url` accepted unfiltered. Loopback / `169.254.x.x` / private CIDRs / DNS-rebinding all reachable from the dispatch worker. Code-confirmed; live-confirmation requires admin token (A4 INDETERMINATE). Codex downgraded to High citing admin-only create; audit retains Critical because an admin-token compromise becomes a network pivot. | appsec AS-3, red-team A4, codex pass-1 F6 (downgrade noted) | At create + dispatch time: reject hostnames resolving to private/loopback/link-local; bind outbound socket to the resolved public IP to defeat DNS-rebinding; set `verify=True` and `follow_redirects=False` explicitly. |
| R5  | Critical | auth | `backend/app/middleware/rate_limit.py:48-51` (defined, unused) | No IP-based rate limit on `/api/v1/auth/login` (or `/register`, `/forgot-password`, `/mfa/verify`). Live: 30 logins from one source → zero 429s. Per-email lockout is bypassed by rotating emails. | appsec AS-5, code-review CR-3, red-team A2 | Wire `Depends(auth_rate_limit)` into every auth-write route. |
| R6  | High | auth | `backend/app/middleware/rate_limit.py:43,49,55` | Rate-limit key is `request.client.host` — behind Nginx this is the proxy IP; all external traffic shares one bucket. | appsec AS-6, code-review CR-4, red-team B2 | `--forwarded-allow-ips=<nginx>` on uvicorn or middleware that reads the rightmost trusted hop from `X-Forwarded-For`. Add `TRUSTED_PROXY_HOPS` setting. |
| R7  | High | auth | `backend/app/routers/v1/auth.py:452-542` (forgot-password) | No rate-limit dependency despite `responses={429:…}`. Live: 20 password-reset requests to one address all returned 202 → email-bomb / SMTP-budget burn. | appsec AS-8, red-team A3, blue-team B5 | Per-IP and per-email limiter; reuse the Redis sorted-set pattern. |
| R8  | High | auth | `backend/app/services/mfa.py:176-206` | MFA pending-token has no per-token attempt counter; pending JWT TTL 300 s. Live: 20 wrong codes accepted on one pending token. | appsec AS-7, red-team A7, blue-team B4 | Redis counter `mfa_pending:fails:<jti>` capped at 5; revoke pending token on cap; reduce TTL to 90 s. |
| R9  | High | auth | `backend/app/routers/v1/auth.py:248`, `backend/app/routers/auth.py:122` | bcrypt only runs when the user exists → 30× timing oracle for account enumeration (`186 ms` vs `6 ms` measured live). | red-team A8 | Pre-compute `_DUMMY_HASH`; always call `pwd_context.verify(payload.password, _DUMMY_HASH)` on the no-match branch. |
| R10 | High | auth | `backend/app/routers/v1/auth.py:687-722`, `backend/app/services/mfa.py:106-133` | MFA enroll + confirm rotates a user's MFA secret on a *bare access token* — no current-password or current-TOTP re-auth. A stolen access token can hijack the second factor. | codex C-M1 | Require `current_password` + (if `mfa_enabled`) a valid current TOTP on `mfa/enroll` and `mfa/confirm`. |
| R11 | High | sensitive-data-in-logs | uvicorn access log (`/ws?token=eyJ…`), `frontend/src/hooks/useWebSocket.js` | WebSocket auth tokens carried in URL query strings appear verbatim in container stdout (observed live). | blue-team B11, codex F14 | Move WS auth to a custom header during the HTTP upgrade, or use a short-lived one-shot WS-only token. Strip query strings from uvicorn access log. |
| R12 | High | privacy / detection-overshoot | `backend/app/routers/v1/auth.py:258-262, :515, :530`, `backend/app/routers/auth.py:133` | Cleartext attempted-email stored in `audit_ledger.payload` on `AUTH_LOGIN_FAILED` and `AUTH_PASSWORD_RESET_REQUEST`, including unknown-user rows from anonymous traffic. Verified via direct DB query. | appsec AS-4, red-team A10, blue-team B8, compliance CP-3, codex F10 (downgrade to Medium noted) | Hash `payload.email` with sha256 when `actor_id` is null; drop the field when `actor_id` is set. |
| R13 | High | CI / coverage | `.github/workflows/ci.yml:36-46` | CI overrides `pytest.ini`'s 80% gate with `--no-cov`; integration tests not wired; no `pip-audit` / `npm audit` step. | qa QA-1 / QA-2 / QA-10, code-review CR-7, appsec AS-10, codex F13 | Drop `--no-cov`; restore `--cov-fail-under=80`; add integration-tests job using GitHub Actions service containers (Postgres + Redis); add `pip-audit` and `npm audit --audit-level=high` jobs. |
| R14 | High | supply chain | `frontend/package.json` | Every dependency uses `^X.Y.Z` (CLAUDE.md §3.4 forbids floating ranges). No `npm audit` gate. | code-review CR-6, appsec AS-10, codex F12 | Pin exact versions; use `npm ci`; add `npm audit` step. |
| R15 | High | CI / secrets | `.github/workflows/ci.yml` | `SECRET_KEY` and `ADMIN_PASSWORD` echoed inline as plaintext env vars in workflow file. CI-only credentials but normalises "secret in YAML". | appsec AS-11 | Use `secrets.*` or generate ephemeral values per job. |
| R16 | High | privacy / GDPR | `audit_ledger.payload` retention undocumented | No documented retention; GDPR Art. 5(1)(e) storage-limitation. | compliance CP-2 | Document a retention period (e.g. 365 d) and implement an `audit_ledger_pruner` job analogous to `prune_old_deliveries`. |
| R17 | High | privacy / GDPR | `audit_ledger.payload` immutability vs Art. 17 erasure | Immutable ledger means anonymise-on-delete leaves PII (email, IP) inside ledger rows. | compliance CP-1 | Hash personal data at write time so anonymisation propagates by construction. |
| R18 | High | privacy / GDPR | webhook fan-out includes PII-bearing events (`auth.*`, `auth.data.export`) | No DPA framework for operator-configured receivers; processor responsibility unstated. | compliance CP-4 | Document receivers as Processors; require DPA before subscription; restrict `*` event subscription; warn admin on PII-bearing events. |
| R19 | High | sandbox | `backend/app/services/validator_sandbox.py`, `backend/app/services/validator_subprocess_runner.py` | Sandbox escape-attempt coverage is shallow; no explicit tests that `socket(AF_INET)`, `unshare`, file-write outside allowed dir, memory-burst, or wall-clock overflow are blocked under the seccomp profile. | appsec AS-12, qa QA-6 | Add explicit "should-be-blocked" unit tests for each escape primitive; consider one-shot container per validator run. |
| R20 | High | sandbox / ttyd | `backend/app/services/workstation.py`, `infra/workstation/` | Per-shell auth path, mount surface, and capability drop not audited end-to-end in this run; risk of session hijack or platform-secret exposure. | appsec AS-13 | Trace and document (a) shell token issue + verify, (b) container mounts, (c) cap-drop + seccomp profile applied to the shell container. |
| R21 | Medium | auth | `backend/app/services/auth.py:50-58` | `jose.jwt.decode` is called without `audience=` or `issuer=`. Algorithm allowlist defends against alg-confusion; aud/iss confusion would still cross-validate a token from any other product sharing `SECRET_KEY`. | codex C-M3 | Set `iss`/`aud` claims on issued tokens; pass `audience=`/`issuer=` to `decode_token`. |
| R22 | Medium | observability | `backend/app/main.py:154` (no docs gate) + Prometheus / OTel coverage | `/docs` reachable in prod (R2); no Prometheus alert config in repo (`docs/alerts/` absent); no startup self-check on canonical security-header names. | blue-team B1/B6/B10 | Add `docs/alerts/*.yml` starter rules; add the security-headers self-check (also covers R1 regression). |
| R23 | Medium | logging | `backend/app/routers/auth.py:249`, `backend/app/routers/v1/auth.py:425` | Bare `except Exception: pass` on the logout-token-decode path; §2.1 forbids silent swallowing. | code-review CR-10, appsec AS-14 | Narrow to `(JWTError, KeyError, ValueError)`; log + audit on the fall-through. |
| R24 | Medium | TLS / webhook | `backend/app/services/webhook_dispatch.py:189-190` | `httpx.AsyncClient(timeout=5.0)` doesn't pass `verify=True` or `follow_redirects=False` explicitly. | appsec AS-17 | Be explicit (`verify=True`, `follow_redirects=False`); both are defaults today but easy to lose. |
| R25 | Medium | structure | `backend/app/models.py:562`, `backend/app/services/flag_submission.py:614`, `backend/app/services/webhook_dispatch.py:512` | Files exceed CLAUDE.md §1.1's 300-line limit. | code-review CR-5, appsec AS-21, codex F11 (downgrade to Low noted) | Decompose along documented seams (models by domain; submission by single-flag / multi-flag / persist / announce; webhook by delivery / replay / retention). |
| R26 | Medium | network policy | `app/config.py:DOCKER_HOST`, `docker-compose.prod.yml` | `tcp://orchestrator:2376` is plaintext TCP; verify network segmentation so only the API container can dial it. | appsec AS-18 | Audit prod compose; switch to mTLS if reachable from a wider trust boundary. |
| R27 | Medium | regex | `requirements.txt` (`google-re2` + stdlib fallback) | If `google-re2` import fails the code silently falls back to stdlib `re` — ReDoS exposure on validator regex paths. | appsec AS-22 | Document the fallback as a release blocker, or remove it (require re2). |
| R28 | Medium | privacy / dependency | `backend/app/services/auth.py` (`python-jose==3.3.0`) | `python-jose` has a stale history of weakly-typed JWT issues; migration to `PyJWT` removes a class of risk. Pinned alg defends today. | appsec AS-15 | Track upgrade path; consider `PyJWT 2.x`. |
| R29 | Medium | privacy / docs | `docs/` missing privacy policy + DPIA | GDPR Art. 35 — high-risk processing typically requires a DPIA; no privacy policy in repo. | compliance CP-5, CP-8 | Author `docs/privacy.md` and `docs/dpia.md`. |
| R30 | Low | structure | `backend/app/services/auth.py:16`, `backend/app/main.py:31` and many services | Module-level `settings = get_settings()` global; tests must monkey-patch before import. §1.4 expects DI. | code-review CR-8, CR-19 | Move `get_settings()` calls inside functions or use `Depends(get_settings)`. |
| R31 | Low | repo hygiene | `backend/siege_backend.egg-info/` | Committed despite `.gitignore`. Leaks package metadata. | code-review CR-17, appsec AS-26 | `git rm -r --cached`; ensure CI fails if reappears. |
| R32 | Low | observability | `backend/app/services/webhook_dispatch.py:189` | New `httpx.AsyncClient` per attempt; reusing a module-scoped client would cut TCP/TLS setup at high fan-out. | code-review CR-18 | Module-scoped `httpx.AsyncClient`. |
| R33 | Low | caching | authenticated GETs (`/v1/me`, `/v1/scoreboard`, etc.) | Verify `Cache-Control: private, no-store` is set so intermediate proxies don't cache per-user data. | code-review CR-20, appsec AS-23 | Confirm header in `security_headers.py` (or per-route response model). |
| R-RT1 | Critical | composite | (all of R1, R3, R5 verified live against `seige-range-api-1`) | Three Critical findings demonstrated end-to-end against the running platform during the audit window. | red-team verdict EXPLOITS-FOUND | See top-3 fixes. |

## Phases executed
| Phase | Specialist | Verdict | Artifact |
|-------|------------|---------|----------|
| 1 Intake | — | recorded | `intake.md` |
| 2 Inventory | — | recorded | `inventory.md` |
| 3 Architect | security-architect | APPROVED-FOR-AUDIT-CONTINUE | `threat-model.md` |
| 4 Code review | code-reviewer | REQUEST-CHANGES | `code-review.md` |
| 4 AppSec | appsec-reviewer | FINDINGS-MUST-FIX | `appsec-report.md` |
| 4 QA | qa-engineer | INSUFFICIENT-TESTS | `qa-report.md` |
| 5 Red team | red-team | EXPLOITS-FOUND | `redteam-report.md` + `redteam/launch.md`, `redteam/launch.log`, `redteam/poc/*` |
| 6 Blue team | blue-team | SILENT-COMPROMISE | `blueteam-report.md` |
| 7 Compliance | compliance-reviewer | REQUIRES-FIX | `compliance-note.md` |
| 8 Codex | codex-liaison | APPROVED-WITH-ADDITIONS (1 iteration) | `codex/codex-summary.md` + `codex/codex-transcript-1.md` |
| 9 Report | — | this file | `audit-report.md` |

## Residual risks accepted

- **Webhook SSRF (R4) retained at Critical despite Codex downgrade to High.** Justification: an admin-token compromise plus a single webhook subscription is sufficient for an internal-network pivot (Redis, Postgres, IMDS). Severity tracks the impact of compromise, not the likelihood; admin tokens are not a strong perimeter here given R3 and R5.
- **Live red-team did not exercise `/admin/*` endpoints, the DinD socket (T21), the ttyd shell trust boundary (T22), or challenge-container escape from the platform's perspective.** No admin token was captured in this run; these are residual unknowns that a follow-up `/secure-build` run should clear.
- **Frontend XSS surfaces were not browser-tested.** With CSP broken (R1), any XSS sink (writeups, hint markdown, display names) lacks defence-in-depth. Bleach sanitisation is in place at the write path but a sink-level audit was not exhaustive.
- **The audit did not load-test bcrypt CPU exhaustion (T15).** R5 + R9 strongly suggest the surface is vulnerable; no SLO breach was demonstrated.

## Out-of-scope observations (informational)

- The deployed Nginx (`seige-range-nginx-1`) returns 404 for `/api/v1/*` against direct probes — appears to route only the SPA in this build. Verify reverse-proxy config matches the production intent. Out-of-scope deployment quirk, not a code finding.
- 62 plaintext flags inside `challenges/**` make scoring non-competitive (intake context); this is by design for a public training repo, but worth keeping in mind for any future "competitive event" framing.
- `seige_backend.egg-info/` is in the working tree despite being gitignored (R31).
- The audit ledger has a hash-chain (`prev_hash`/`this_hash` with length check constraints) — strong integrity property worth highlighting positively. No `UPDATE`/`DELETE` paths to the ledger were observed in code review.

## Suggested next-step run
A follow-up `/secure-build` against the prioritised fixes (R1 → R3 → R5 → R6 → R7 → R8 → R9 → R10 → R11 → R12 → R13 → R14) would close the Critical/High findings in one cycle. R4 (webhook SSRF), R19 (validator sandbox), and R20 (ttyd) deserve their own scoped builds since they touch network-policy and container-runtime concerns beyond the single-file fixes the rest involve.
