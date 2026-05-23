# Compliance Note — seige-range full audit

## Applicability
- **Regulated data touched: YES.**
  - Identity data: `users.email`, `users.username`, `users.display_name`, `users.hashed_password`, `users.mfa_secret`, `users.mfa_enabled`, `users.email_verified`, `users.last_login`.
  - Auth/session: JWT access + refresh tokens, password-reset tokens (`password_reset_tokens.token_hash`), email-verification tokens, MFA TOTP secrets, MFA recovery code hashes.
  - Behavioural / activity: `audit_ledger.payload` (per-event JSON often including `email`, `username`, `ip_address`), `solves`, `solved_flags`, `challenge_instances`, `writeups`, `hint_unlocks`.
  - Network metadata: `audit_ledger.ip_address`, `request_id`.
  - Outbound to operator-controlled webhooks (PII fan-out surface).
- **Frameworks in scope:**
  - **GDPR / UK-GDPR** — yes (email + IP + behavioural ledger are personal data under Art. 4(1); the public CTF repo could be used by EU residents).
  - **CCPA / CPRA** — yes if any California user.
  - **PCI-DSS** — no payment data observed.
  - **HIPAA** — no health data observed.
  - **COPPA** — *potential exposure*. CTF audiences sometimes include under-13s. There is **no age gate** in the registration flow (`schemas/v1/auth.py:AuthRegisterRequest` has no DOB / age-confirm). Treat as ADVISORY.

## Data inventory

| Field | Classification | Lawful basis (proposed) | Retention | Subject rights |
|-------|----------------|-------------------------|-----------|----------------|
| `users.email` | regulated PII | contract (Art. 6(1)(b)) | until account deletion + 90 d (audit ledger retains hashed actor reference) | export ✅ delete ✅ rectify ✅ |
| `users.username`, `display_name` | regulated PII (pseudonymous) | contract | same | export ✅ delete ✅ rectify ✅ |
| `users.hashed_password` | regulated (auth) | contract | same | export — *partial: redacted* ✅ delete ✅ rectify ✅ |
| `users.mfa_secret` | regulated (auth) | contract | same; cleared on disable | export ❌ (correct — should never export) delete ✅ rectify ✅ |
| MFA recovery codes (hashes) | regulated (auth) | contract | same | export ❌ delete ✅ |
| Password-reset tokens (hashes) | regulated (auth) | contract | 30 min TTL + retain until expiry | export ❌ delete via `delete_my_account_v1` ✅ |
| Email-verification tokens (hashes) | regulated (auth) | contract | 24 h TTL | export ❌ delete ✅ |
| JWT access (in-flight) | regulated (auth) | contract | TTL only; not persisted | n/a — refresh-token blacklist in Redis with TTL |
| `audit_ledger.payload` (incl. `email`, `username`, `ip_address`) | regulated (PII + activity log) | legal obligation / legitimate interest (security audit) | undocumented — **finding** | export ✅ (rows where `actor_id` matches) delete ❌ by design (immutable ledger) — **conflict with GDPR Art. 17** |
| `audit_ledger.ip_address` | regulated (PII per CJEU *Breyer*) | legitimate interest (security) | undocumented — **finding** | as above |
| `solves`, `solved_flags`, `instances`, `writeups`, `hint_unlocks` | confidential (pseudonymous after anonymise) | contract | retained post-anonymise as platform-aggregate (documented in `me.py:191-195`) | export ✅ delete: anonymised, not hard-deleted (documented) |
| `users.last_login`, `created_at` | confidential | contract | same | export ✅ |

## Findings

### Required (must address)

**CP-1 (Required) — GDPR Art. 17 vs. immutable audit ledger.**
The platform takes a defensible position: anonymise the `users` row on account-delete, leave audit-ledger rows intact (`backend/app/routers/v1/me.py:190-203`). The rationale is documented in code and matches CLAUDE.md §4.2 (audit ledger is immutable). **However**, the ledger payloads frequently include the *cleartext email* (see CP-3 below) — so anonymising the `users` row doesn't actually erase the personal data from the ledger.
- **Standard:** GDPR Art. 17 (Right to Erasure) with the Art. 17(3)(b)/(e) exemption for legal obligation / public interest archival.
- **Fix:** Either (a) explicitly hash personal data in the ledger payload at write time so anonymisation is propagated by construction, or (b) add a "ledger PII redaction on account-delete" step that overwrites the *personal-data fields inside the JSON payload* without touching `prev_hash`/`this_hash`. Recompute the row hash? — would break the chain. Cleanest: hash-at-write (option a).

**CP-2 (Required) — Audit-ledger retention period is undocumented.**
GDPR Art. 5(1)(e) — storage limitation. Section 4 of `CLAUDE.md` requires audit-ledger retention but doesn't specify a duration; the project has not picked one in `docs/`. Logs retained indefinitely violate storage-limitation.
- **Fix:** Document the retention period (recommendation: 365 days for security-audit logs; longer if a specific legal obligation applies). Implement a retention sweep job (similar to `prune_old_deliveries` in `webhook_dispatch.py:487`). Note in the privacy policy.

**CP-3 (Required) — Cleartext email in `audit_ledger.payload` on `auth.login.failed` and `auth.password.reset.request`.**
Confirmed live (red-team A10). Storing the *attempted* email (including misspellings from anonymous traffic) creates a long-lived store of unverified personal data with no clear lawful basis and no link to a user account.
- **Standard:** GDPR Art. 5(1)(c) (data minimisation), Art. 6(1)(f) (no clear legitimate interest in retaining unauth typed-in strings indefinitely).
- **Fix:** Store `sha256(payload.email)` instead. For matched users, drop `payload.email` (the `actor_id` already identifies the user).

**CP-4 (Required) — Outbound webhook PII fan-out, no Data Processing Agreement framework.**
`backend/app/services/webhook_dispatch.py` POSTs ledger event payloads to operator-configured URLs. If the operator subscribes to `auth.data.export`, `auth.register`, `auth.password.reset.request`, etc., the receiver is processing PII on the controller's behalf.
- **Standard:** GDPR Art. 28 (Processor agreements).
- **Fix:** Document in `docs/` that any webhook receiver is a Processor; require operators to maintain a DPA before adding subscriptions. Restrict the wildcard `*` event subscription to specific events that don't contain PII. Add an admin warning at create time if the subscription includes PII-bearing events.

**CP-5 (Required) — No documented Data Protection Impact Assessment.**
A new processing activity at this scale (user accounts, behavioural tracking, MFA, password resets, audit ledger) typically warrants a DPIA (GDPR Art. 35 — high risk via systematic monitoring + sensitive data processing).
- **Fix:** Author `docs/dpia.md` covering risks, mitigations, residual risk, and a sign-off.

### Advisory (recommended)

**CP-6 (Advisory) — Email-verification token cleartext flows through email body.**
The reset link includes the token as a query parameter (`backend/app/routers/v1/auth.py:490-492`). Email transit is best-effort encrypted (TLS) but mail-server logs may capture it. Acceptable industry practice; could note in privacy policy that the email is the trust boundary.

**CP-7 (Advisory) — IP-address logging in `audit_ledger.ip_address`.**
Per CJEU *Breyer* (C-582/14) the IP is personal data. Currently uses the unfiltered `request.client.host` (which behind Nginx is the proxy IP — accidentally privacy-protective, but also defeats AS-6's rate-limiting goal). Decide both rate-limit IP and audit-log IP together. If the audit ledger logs the real client IP, retention (CP-2) is even more important.

**CP-8 (Advisory) — Privacy policy / data-handling statement absent from repo.**
- **Fix:** Author `docs/privacy.md` with: controller identity, lawful bases, data categories, retention, subject-rights paths (export at `/api/v1/me/data`, delete at `DELETE /api/v1/me`, rectify at `PATCH /api/v1/auth/profile`), contact for DPO/data-protection queries.

**CP-9 (Advisory) — COPPA exposure if under-13s register.**
No age gate. If the operator targets minors knowingly, COPPA-style verifiable parental consent applies. If not, add an age-confirmation checkbox at registration with a hard floor (e.g. 16+ per GDPR Art. 8(1)).

**CP-10 (Advisory) — Data-export endpoint (`GET /api/v1/me/data`) is rate-limit-naked.**
A malicious script could mass-export an attacker's own account to consume API budget. Low-impact but worth a 1-per-hour limit.

**CP-11 (Advisory) — Cross-border data residency unstated.**
Postgres is local in the compose; production deployment hardness isn't documented. Operators should declare residency for transparency.

**CP-12 (Advisory) — Third-party processors and dependency licences.**
None observed in-repo (OTLP exporter, SMTP, webhook receivers are all operator-controlled). Document the dependency list with licence summary; nothing flagged today.

## What looked right
- **Subject-rights paths exist and are correct in structure**:
  - Right of access (Art. 15): `GET /api/v1/me/data` — full export, audit-logged.
  - Right to erasure (Art. 17): `DELETE /api/v1/me` — anonymises user row; documented rationale; requires current password (good defence against drive-by deletion).
  - Right to rectification (Art. 16): `PATCH /api/v1/auth/profile` (display_name + team only); password change is separate; email change path appears absent — **minor finding** (CP-13 below).
- Audit ledger is **hash-chained** (`prev_hash`/`this_hash`), satisfying CLAUDE.md §4.2 immutability with cryptographic backing.
- Passwords are bcrypt-hashed via `passlib` (`backend/app/services/auth.py:14`). MFA secrets present but never logged.
- Tokens (password reset, email verification, MFA recovery codes) are stored as `sha256` hashes, never cleartext.
- The `_PLACEHOLDER_VALUES` denylist refuses obvious default secrets at boot.
- `/v1/me/data` excludes `hashed_password` explicitly.

### Minor (CP-13 Advisory) — No documented email-change path.
The current flow requires a user to delete + re-register if they need to change email. Consider an admin-side flow or a verified self-service one (current email + new email + verify both).

## Verdict
**REQUIRES-FIX.** Five Required findings (CP-1 through CP-5) address PII inside the audit ledger, retention, processor contracts, and DPIA documentation. None require *legal review* in the orchestrator's sense — they are concrete engineering and documentation fixes the team owns. Proceed (do not escalate to legal); record the items in the audit report's risk register.

## What would have triggered REQUIRES-LEGAL-REVIEW
- A new cross-border data flow without an adequacy decision / SCCs.
- A new third-party processor receiving raw PII without a DPA.
- A new sensitive-data category (health, biometric, children's data) added to the platform.

None of those apply to the current snapshot.
