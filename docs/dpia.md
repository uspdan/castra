# Data Protection Impact Assessment — seige-range

_Last updated: 2026-05-23 (covers code at commit ≥ `8527a98`)._

GDPR Art. 35 requires a DPIA where processing is "likely to result
in a high risk to the rights and freedoms of natural persons". The
seige-range platform's processing is **not** high-risk by the WP29
criteria (no automated decisions with legal effect, no large-scale
special-category processing, no public-space monitoring). The
remaining risks are routine identity + activity tracking; this
DPIA documents them so the operator has a written assessment to
hand to a DPA if asked.

---

## 1. Processing description

**Purpose:** run capture-the-flag training exercises against a
fleet of intentionally-vulnerable challenge containers, score the
results, and surface a leaderboard.

**Subjects:** end-users ("players") of the deployed platform.
Typical population: an organisation's internal security team or a
classroom cohort.

**Data categories:** see `docs/privacy.md` §1.

**Processing operations:**
1. Account create / login / MFA (active).
2. Challenge launch (orchestrated container per instance).
3. Flag submission + score award.
4. Audit-ledger append.
5. Optional outbound webhook dispatch.

**Storage:** Postgres for the relational state, Redis for sessions
and rate-limit counters, stdout for operational logs.

---

## 2. Necessity and proportionality

| Category | Necessary? | Notes |
|----------|------------|-------|
| Account identity | Yes | A scoreboard without identity is incoherent. |
| Credential material | Yes | The platform self-authenticates; SSO is optional. |
| Activity (solves, ledger) | Yes | Scoring + anti-cheat both depend on it. |
| IP for rate-limit + audit | Yes | Documented retention; bound to ledger row TTL. |
| Webhook receiver list | Yes if enabled | Admin-only, opt-in. |

Minimisation pass (R12): cleartext email is HMAC'd on
`auth.login.failed` and `auth.password.reset.request` rows when the
actor is anonymous (the bare actor_id is enough for known users —
no email field at all).

---

## 3. Risks identified

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Credential compromise via brute-force | Low | Medium | bcrypt; per-IP rate limit (R5); account lockout per email; MFA available |
| Credential compromise via leak in audit ledger | Very low | Medium | Ledger never carries cleartext passwords; failed-auth emails HMAC'd (R12) |
| Account takeover via stolen access token | Low | Medium | MFA enrol + confirm require current password (R10); refresh-token blacklist on logout |
| Account enumeration via timing | Low | Low | Constant-time bcrypt on unknown-email branch (R9) |
| Account enumeration via response shape | Low | Low | forgot-password always returns 202 |
| Data exposure via webhook misconfiguration | Medium | Medium | SSRF guard at create + dispatch (R4); HMAC-signed bodies; admin-only |
| Data exposure via OpenAPI / Swagger | Low | Low | Docs surface only mounted in development (R2) |
| Excessive retention | Low | Low | Ledger pruner at 365d (R16); deliveries pruner at 30d |
| Inability to honour Art. 17 erasure | Low | Medium | HMAC'd PII in ledger makes erasure-by-construction tractable (R17) |
| Unauthorised processor (webhook receiver) | Medium | Medium | Operator-as-Controller documented (R18); admin warn at subscribe time when subscribing to PII-bearing events |

---

## 4. Residual risks accepted by the operator

The following are documented but not mitigated in the platform code
— they're the operator's responsibility at deploy time:

* TLS certificate management (mTLS to the orchestrator is on the
  audit register, R26).
* Backup encryption of the Postgres volume.
* Physical security of the host.
* Log-collection-pipeline retention (the platform writes structured
  JSON to stdout; what happens after the container's stdout is
  outside this repo's control).
* DPA agreements with any operator-configured webhook receivers.

---

## 5. Review trigger

Re-do this DPIA when:

* A new event type starts carrying personal data (touches the
  `_PAYLOAD_VALIDATORS` map in `app/services/audit/events.py`).
* A new third-party processor is added (a new outbound dispatch
  surface, beyond webhooks).
* A new identity field is added to the `users` table.
* Retention defaults change.

Triggered manually for now — a future `/secure-audit` run can
flag DPIA drift automatically.
