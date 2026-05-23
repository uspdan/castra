# Threat Model — seige-range (project-wide, AUDIT mode)

> AUDIT-mode threat model. Scope is the whole platform (everything in `backend/`, `frontend/`, `infra/`, `nginx/`, `docker*`, `scripts/`, `packages/`, `.github/`) excluding `challenges/` and `examples/` (intentionally-vulnerable training material). Section 5 is repurposed from "Builder Contract" to "Expected controls". Section 6 (reuse audit) is omitted per the audit role doc.

## 1. Task & Assets

**Restated scope.** Assess the security posture of the seige-range CTF platform: a FastAPI + SQLAlchemy backend, React/Vite SPA, Nginx fronting, PostgreSQL/Redis stores, a Docker-in-Docker challenge orchestrator, and ttyd-backed browser shells. The platform authenticates users, accepts flag submissions, runs validators (some via subprocess sandboxes), enforces rate limits, dispatches webhooks, sends email (password reset/MFA), records audit events, and exposes a Prometheus `/metrics` endpoint. The repo is **public**; ~62 intentionally-vulnerable challenge containers live alongside platform code.

**Assets (sensitivity in parens).**
- A1. User credentials — bcrypt-hashed passwords, MFA TOTP secrets, password-reset tokens, email-verification tokens. (**regulated** — auth)
- A2. Session/JWT signing key (`SECRET_KEY`) and admin bootstrap credentials. (**regulated**)
- A3. Sealed flag hashes (`secrets/flags.json`) and sealed per-question answers (`secrets/answers/`). (**confidential** — integrity-critical; disclosure devalues scoring)
- A4. User PII — email, display name, IP-keyed audit rows, submission history. (**regulated** — PII)
- A5. Submission/scoring ledger (append-only audit + scoring records). (**confidential** — integrity-critical)
- A6. Validator subprocess sandboxes (seccomp-protected) executing untrusted-ish manifest-driven logic. (**internal** — privilege boundary)
- A7. Docker daemon socket / DinD orchestrator (`DOCKER_HOST=tcp://orchestrator:2376`) used to launch challenge containers. (**regulated** — full host-level escalation if abused)
- A8. Challenge container egress (via `docker/egress-proxy`, `docker/egress-sidecar`). (**confidential** — outbound network policy)
- A9. ttyd browser-shell endpoints attached to per-instance containers. (**confidential** — interactive RCE inside a sandbox)
- A10. Outbound channels: SMTP, webhooks (operator-configured URLs), OpenTelemetry OTLP. (**confidential** — SSRF / data-exfil surface)
- A11. CI/CD pipeline + GitHub Actions secrets. (**regulated**)
- A12. Public README / docs / commit history. (**public**)

## 2. Trust Boundaries

- B1. Public internet → Nginx (TLS termination) → FastAPI.
- B2. FastAPI router → service layer (authenticated identity carried in `Request.state` / dependency-injected `current_user`).
- B3. Service layer → PostgreSQL (asyncpg) — must be parameterised everywhere.
- B4. Service layer → Redis (rate-limit state, scoreboard cache).
- B5. Service layer → Docker socket via `tcp://orchestrator:2376` (privileged action). Crossing here is an *escalation*.
- B6. Service layer → validator subprocesses (`validator_subprocess_runner`, `validator_sandbox`) executing under seccomp profiles.
- B7. Service layer → outbound HTTP (webhooks, OTLP) — SSRF boundary.
- B8. Service layer → SMTP relay.
- B9. Frontend SPA → Backend API — CORS-controlled.
- B10. Browser → ttyd over reverse-proxied WS — user effectively gets a shell inside a *challenge* container.
- B11. CI runner (GitHub-hosted) → repo (Actions tokens, branch-protection rules).

## 3. STRIDE Analysis

| ID  | Boundary/Asset | Threat | Likelihood | Impact | Status |
|-----|----------------|--------|------------|--------|--------|
| T1  | B1/A1,A4 | **S** — credential stuffing / password spraying against `/auth/login` and `/v1/auth/login` | H | H | needs C1 (rate limit + lockout) |
| T2  | B1/A1 | **S** — bypassing MFA by replaying or pre-MFA-bound session tokens | M | H | needs C2 (state machine; partial token until MFA complete) |
| T3  | B2/A1 | **S** — JWT algorithm confusion (`alg: none`, RS256↔HS256 swap) via `python-jose` if not pinned to a single algorithm | M | H | needs C3 (explicit `algorithms=[...]`; reject `none`) |
| T4  | B1/A1 | **S** — password-reset token guessing / leakage in email logs / SMTP-in-the-middle | M | H | needs C4 (cryptographically random tokens, short TTL, single use, masked logs) |
| T5  | B1/A12 | **S** — phishing via webhook URLs / SSRF using webhook delivery to internal targets | M | H | needs C5 (URL allowlist or denylist of private ranges; loopback/link-local blocked) |
| T6  | B3/A5,A4 | **T** — SQL injection through any router that builds queries from request data | M | C | needs C6 (parameterised queries everywhere; ORM only; ban f-string SQL) |
| T7  | B6/A6,A7 | **T** — sandbox escape from validator subprocess (file write, ptrace, fork-bomb, network) | M | C | needs C7 (seccomp profile coverage; no `CAP_*`; read-only FS; ulimits; cgroup CPU/mem caps; net=none) |
| T8  | B5/A7 | **T/E** — challenge container escapes DinD into host or sibling containers | L | C | needs C8 (digest-pinned images; rootless or strict cap-drop; per-instance user-namespace; CIS docker checks) |
| T9  | B1/A5 | **T** — flag-tampering via submission replay, off-by-one in scoring, race on first-blood crediting | M | H | needs C9 (idempotent submissions; tx-level locking; sealed-flag compare in constant time) |
| T10 | B2/A5 | **R** — submission/audit log gaps (delete, update, or untraceable identity rotation) | L | H | needs C10 (append-only ledger; immutable rows; admin actions audited) |
| T11 | B2/A4 | **I** — PII / sensitive-string leak in structured logs (passwords, tokens, OTP seeds) | M | H | needs C11 (SensitiveString wrapper; redaction at log layer; review of `structlog` processors) |
| T12 | B1/A1,A2 | **I** — secret leakage via stack traces / `/docs` swagger / verbose 500s | L | H | needs C12 (generic 500 in prod; disable docs in prod; sanitised error envelope) |
| T13 | B7/A10 | **I** — webhook dispatch leaks bearer tokens or PII to operator-controlled URL without TLS verification | M | H | needs C13 (TLS verify on outbound; explicit redact list; signed HMAC instead of bearer) |
| T14 | B11/A2,A11 | **I** — secrets exposed via plaintext echo in CI logs, or via PR-fork workflow runs | L | H | needs C14 (use `::add-mask::`; `pull_request_target` discipline; secrets segregated) |
| T15 | B1 | **D** — login endpoint flooded; bcrypt CPU exhaustion | M | H | needs C15 (rate limit + concurrency cap on `/auth/*`; pre-bcrypt cheap reject) |
| T16 | B1 | **D** — ReDoS via regex validators | L | H | mitigated by `google-re2` (verify all regex paths actually go through re2; stdlib `re` fallback is risk) |
| T17 | B6 | **D** — validator subprocess hang / fork bomb takes down orchestrator worker | M | M | needs C7 (timeouts, ulimits) — same control |
| T18 | B5 | **D** — challenge launcher exhausts host-port window (`INSTANCE_PORT_MIN..MAX`) | L | M | needs C18 (port-window monitoring + GC of stale instances) |
| T19 | B2/A1 | **E** — privilege escalation from regular user → admin via missing service-layer authZ (route-only checks) | M | C | needs C19 (defence-in-depth: service layer re-checks role and ownership) |
| T20 | B1/A2 | **E** — bootstrap admin password reused / weak / leaked via CI logs | L | H | partly mitigated (`_PLACEHOLDER_VALUES` rejected at startup); verify no env-default reaches prod |
| T21 | B5 | **E** — DinD orchestrator socket reachable to non-orchestrator services (anyone who can talk to `tcp://orchestrator:2376` owns the host) | M | C | needs C21 (network policy restricts who can dial 2376; mTLS on socket) |
| T22 | B10 | **E** — ttyd shell escapes the challenge container via missing seccomp/caps drop, or session is hijacked through predictable URL | M | H | needs C22 (signed short-TTL access token per shell; container cap-drop + seccomp) |
| T23 | B9 | **T** — CSRF on state-changing endpoints if session-cookie auth is used; or origin-confusion if CORS too broad | M | H | needs C23 (SameSite=Strict on cookies, or bearer-only with explicit origin allowlist; double-submit token for cookie flows) |
| T24 | B1 | **D/I** — XSS via writeups, hint markdown, display name, or any user-rendered content | M | H | partly mitigated (`bleach==6.1.0` present); verify it's applied at every render path; CSP header in `security_headers.py` must be non-trivial |
| T25 | B7/A8 | **I/T** — SSRF from `flag_dispatch` or webhook to cloud metadata IMDS (169.254.169.254), AWS task creds | M | C | needs C25 (block private/link-local; egress proxy enforces) |
| T26 | B11 | **T** — supply-chain compromise: an unpinned/typosquatted dep (frontend `^` ranges) injects a malicious version | M | H | needs C26 (pin exact; npm `--frozen-lockfile`; `npm audit` in CI; SBOM) |
| T27 | B2/A3 | **I/T** — sealed-flags file readable by non-platform processes inside container (mode/owner wrong) | L | H | needs C27 (chmod 0400; root:root or app user; not bind-mounted to challenge containers) |
| T28 | B2 | **R** — admin-impersonation: any "act-as" / "view-as" admin tool that doesn't write an audit event | L | H | needs C10 same — verify admin routers in `app/routers/admin.py` and `v1/admin.py` |
| T29 | B1 | **I** — public repo + 62 plaintext flags inside `challenges/` means scoring is non-competitive (intake context); not a *platform* finding, but worth recording as out-of-scope observation | n/a | n/a | out-of-scope |
| T30 | B2 | **T** — race conditions on first-blood crediting, hint unlocking, scoring transactions | M | M | needs C30 (SELECT ... FOR UPDATE / advisory locks; unique constraints) |

## 4. Mitigations / Controls

- **C1** — Authentication rate limiting and progressive lockout. Per-IP and per-account counters in Redis (`app/middleware/rate_limit.py`). Satisfies §3.2. *Expected location:* `app/services/auth.py`, `app/routers/v1/auth.py`.
- **C2** — MFA state machine: a partial token after password success, full token only after TOTP verify. Reject any access-token issuance that skips the MFA step when MFA is enabled. *Location:* `app/services/mfa.py`, `app/services/auth.py`.
- **C3** — JWT verify with explicit `algorithms=[...]` allowlist (single algorithm). Reject `none`. Verify `aud`, `iss`, `exp`. *Location:* wherever `jose.jwt.decode` is called.
- **C4** — Password-reset tokens: 32 bytes from `secrets.token_urlsafe`, store hash, TTL ≤ 30 min, single-use, mask in logs. *Location:* `app/services/password_reset.py`.
- **C5** — SSRF defence on webhook dispatch and any outbound URL the operator controls: deny `127.0.0.0/8`, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`, `::1`, link-local; resolve hostname pre-request and re-check post-resolution to defeat DNS rebinding. *Location:* `app/services/webhook_dispatch.py`, `app/services/flag_dispatch.py`.
- **C6** — All DB access via SQLAlchemy Core/ORM with bound parameters. No `text(f"...{var}...")`. *Location:* every router and service.
- **C7** — Validator sandbox controls: seccomp profile (in `app/security/seccomp/`), `--cap-drop=ALL`, `--read-only`, `--network=none`, `--memory`, `--cpus`, `--pids-limit`, wall-clock timeout, kill-on-timeout. *Location:* `app/services/validator_sandbox.py`, `validator_subprocess_runner.py`.
- **C8** — Image digest pinning (`REQUIRE_IMAGE_DIGEST=true` in prod). Verify the launcher refuses to run any image whose post-pull `RepoDigests` doesn't include the pin. *Location:* `app/services/orchestration/launcher.py`.
- **C9** — Idempotent flag submission: `(user_id, challenge_id, flag_hash)` unique constraint; constant-time compare on sealed hash; FOR-UPDATE on the scoring row.
- **C10** — Append-only audit ledger: ORM model with no UPDATE/DELETE methods; admin actions (impersonation, role grant, manual scoring) recorded. *Location:* `app/services/audit/`.
- **C11** — Structured logger redacts `password`, `token`, `secret`, `seed`, `otp`, `mfa`, `cookie` keys. SensitiveString wrapper in `app/shared/` if not present. *Location:* `app/middleware/logging_mw.py` + structlog processors.
- **C12** — `/docs` and `/redoc` disabled when `APP_ENV=production`. 500 responses sanitised. *Location:* `app/main.py`.
- **C13** — Outbound HTTP verifies TLS, no `verify=False`. Webhooks signed with HMAC-SHA256 (shared secret per webhook) rather than a bearer token.
- **C14** — CI secrets handled via `${{ secrets.* }}` only; no `echo $SECRET`. Use `pull_request` (not `pull_request_target`) for unsafe checkout. Confirm with workflow file.
- **C15** — Pre-bcrypt fast-reject: if account doesn't exist or has been locked, return generic error without hashing; rate-limit the login endpoint per-IP and per-account.
- **C18** — Track instance count vs. `INSTANCE_PORT_MIN..MAX`; reap idle instances; alert at 80% utilisation.
- **C19** — Every service-layer entry point that mutates state re-checks ownership/role. Route guards alone are insufficient.
- **C21** — Network policy / firewall rule: only the API container can reach `orchestrator:2376`. mTLS if reachable from a wider trust boundary.
- **C22** — Per-shell signed token (JWT or HMAC) with short TTL; ttyd auth proxied through the API; cap-drop + seccomp + no `--privileged` on shell containers.
- **C23** — Auth via bearer in `Authorization` header (no cookie session). Explicit `ALLOWED_ORIGINS` allowlist; reject `*` in production (verified in `app/config.py`).
- **C24** — Bleach-sanitise all user markdown; CSP header without `unsafe-inline`/`unsafe-eval`; render display-name with text-only sinks.
- **C25** — Same as C5; in addition, all outbound from validators/challenge containers passes through `docker/egress-proxy` with an explicit allowlist.
- **C26** — Pin frontend deps exactly (drop all `^`/`~`). Add `npm audit --omit=dev --audit-level=high` to CI. Add `pip-audit` to CI. Generate SBOM.
- **C27** — `secrets/flags.json` mode 0400 owned by API service user; not mounted into challenge containers; not present in challenge image build context.
- **C30** — DB-level uniqueness + transactional locking for first-blood and scoring; idempotency keys.

## 5. Expected Controls (per area)

(Repurposed from "Builder Contract" — what we expect to see when reviewers look.)

- **Public surface (HTTP):** ~92 endpoints. Every state-changing endpoint behind auth + authZ + audit. Generic 4xx/5xx envelope. CORS allowlist non-empty in prod. CSP, HSTS, X-Frame-Options, X-Content-Type-Options on every response (`app/middleware/security_headers.py`).
- **Validation schemas:** Pydantic v2 models at the boundary of every router. No raw dict passing through to services.
- **Error types:** typed hierarchy (CLAUDE.md §2.2). Every router maps to consistent HTTP status. No bare `except Exception: pass`.
- **Audit events:** who/what/when/where/which/why for every state change. Auth events (login success/fail, MFA success/fail, password reset request, password change, role change), submission events, admin events, instance lifecycle (launch, stop, kill).
- **Timeouts / retries / breakers:** explicit on every outbound (`httpx.Timeout`, configurable in `app/config.py`). Retry with backoff+jitter. Circuit breaker on webhook/SMTP/Docker daemon calls.
- **Fail-closed behaviour:** auth failure → deny; MFA misconfig → deny; sealed-flag file unreadable → deny submissions, surface a maintenance error.
- **Secrets:** all from `pydantic-settings`; placeholders rejected at boot (`_PLACEHOLDER_VALUES` set in `config.py` — good); production refuses empty `ALLOWED_ORIGINS`; `REQUIRE_IMAGE_DIGEST=true` in prod.
- **Containers:** non-root user, multi-stage Dockerfile, base images pinned to digest, `.dockerignore` excludes secrets and `tests/`.
- **CI:** lint + typecheck + unit + integration + dep audit + secret scan + container scan + flag-leak guard, all blocking. **Currently missing: integration step, coverage gate, dep audit.**

## 6. Reuse Decisions
N/A (audit mode).

## 7. Verdict

**APPROVED-FOR-AUDIT-CONTINUE.** The project is modellable; no condition warrants `BLOCK-AT-DESIGN`. Proceed with reviewers, red team, blue team, compliance, Codex.

### Residual risks to verify in later phases
- **R-A.** All JWT decode paths use an explicit `algorithms=[...]` list (T3).
- **R-B.** Every router that mutates state has a service-layer re-check (T19).
- **R-C.** Outbound webhook + flag-dispatch implements SSRF guardrails (T5, T25).
- **R-D.** `python-jose` is not exposed to attacker-controlled algorithm selection (T3).
- **R-E.** Frontend dependency floating ranges (T26) — confirm and quantify.
- **R-F.** DinD socket exposure: who can reach `orchestrator:2376` on the docker network (T21).
- **R-G.** ttyd shell auth path (T22).
- **R-H.** Submission idempotency + first-blood race (T9, T30).

### Open questions for the orchestrator
- None blocking. Proceed to Phase 4.

### Notes for downstream reviewers
- `challenges/` and `examples/` are explicitly out of scope (training material). Reviewers should not flag intentional vulns there as findings, but they **should** flag any path that lets challenge code reach platform secrets, the host Docker socket, or sibling-instance internals — that crosses a real platform boundary.
- The repo is public; treat readability of the code as a given (no security-through-obscurity).
- Backup secret-handling (`scripts/backup.sh`, `scripts/restore.sh`) is in-scope.
