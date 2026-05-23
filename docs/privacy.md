# Privacy Notice — seige-range

_Last updated: 2026-05-23 (covers code at commit ≥ `8527a98`)._

This document explains what personal data the seige-range platform
collects, why, how long it's kept, and how it's protected. It is
written for operators deploying the platform and for players whose
data is processed by it.

This is the **platform's** privacy posture — the intentionally-
vulnerable training challenges and example artefacts under
`challenges/` and `examples/` are out of scope; they are
synthetic training material and do not process real-user data
beyond the score / submission events they generate.

---

## 1. What we collect

| Category | Field | Where stored | Why |
|----------|-------|--------------|-----|
| Account identity | `email`, `username`, `display_name`, `team` | `users` table | Login, scoreboard attribution, leaderboard display |
| Credential material | bcrypt hash of password, optional TOTP secret, sha256 hashes of MFA recovery codes | `users.hashed_password`, `users.mfa_secret`, `mfa_recovery_codes` | Authentication |
| Session state | JWT refresh tokens (revocable; Redis blacklist) | Redis | Session continuity, logout invalidation |
| Activity | submission events (challenge slug, timestamp, correct/incorrect), solve records | `solves`, `solved_flags`, `audit_ledger` | Scoreboard, progress, anti-cheat |
| Audit | who/what/when/where for every state-changing action | `audit_ledger` (immutable, hash-chained) | Operational integrity, incident response, R12: cleartext emails on failed-auth rows are dropped or HMAC'd |
| Operational | request method, path, status code, duration, request id | stdout logs (no DB) | Operations |
| Webhook receivers (admin) | URL, signing secret, event subscription list | `webhook_subscriptions` | Operator-configured outbound integrations |

We do **not** collect: IP geolocation, browser fingerprint, third-
party identity-provider tokens, payment data, biometrics, health
data, or content of submitted writeups beyond what the player
chooses to put there.

---

## 2. Lawful basis (GDPR Art. 6)

For most fields the lawful basis is **performance of a contract**
(Art. 6(1)(b)) — you cannot run a CTF platform without the
account-and-submission core. The audit ledger, the security-event
emit, and the anti-cheat burst detector rest on **legitimate
interests** (Art. 6(1)(f)) — operating the platform safely. We do
not rely on consent for any of the above.

If your deployment ties accounts to an external identity provider
(SSO), the identity-provider's own lawful basis flows through.

---

## 3. Retention

| Data | Default retention | How to change |
|------|-------------------|---------------|
| Account row | Until the user requests deletion or the operator hard-deletes | Operator action |
| Solves / scoreboard | Indefinite (the platform's product is a leaderboard) | Operator action |
| Audit ledger | 365 days (default), rolling prune | `AUDIT_LEDGER_RETENTION_DAYS` config (R16 — pruner job) |
| Webhook deliveries history | 30 days | Existing `prune_old_deliveries` job |
| Refresh-token blacklist (Redis) | Until token's natural expiry | TTL keyed on the token's `exp` claim |
| Operational stdout logs | Per the operator's log-collection pipeline | Out of scope of this repo |

The audit ledger is immutable by construction (append-only, hash-
chained). To satisfy GDPR Art. 17 (right to erasure) without
breaking the chain, personal data fields in ledger rows are
written as one-way HMAC hashes at insert time (R17). Pseudonymous
correlation across rows is preserved; the cleartext value is not
recoverable from the ledger.

---

## 4. Sharing with third parties

The platform itself does not share data with third parties.

If the operator configures **outbound webhooks** (admin-only
feature), event payloads — which include personal data for `auth.*`
events — flow to whatever endpoint the operator subscribed.
Operators who enable webhook subscriptions are acting as a
Controller; the webhook receiver is a Processor that the operator
must DPA with directly (R18).

Webhook subscriptions that subscribe to the wildcard `*` or to any
`auth.*` event MUST be configured against a receiver covered by a
Data Processing Agreement (R18 — admin UI warns at create time).

---

## 5. Security controls (summary)

* TLS in transit (HSTS in production).
* bcrypt for passwords; TOTP for MFA second factor.
* JWT signing keys are configured per-deploy (`SECRET_KEY`); never
  defaulted.
* Audit ledger is immutable and hash-chained — tampering with a
  row breaks the chain at every subsequent row and is detectable
  by `audit_verify`.
* Cleartext PII (specifically: attempted email on failed-auth and
  password-reset events) is HMAC'd before being persisted to the
  ledger (R12).
* Webhook outbound dispatch refuses URLs resolving to private /
  loopback / link-local addresses (R4) to defeat SSRF pivots.

Full security posture: see `docs/runbooks/` and the corresponding
`/secure-audit` run under `.claude/runs/`.

---

## 6. Player rights

Under GDPR (where the operator is the Controller) players have
the right to:

* **Access** — `GET /api/v1/auth/data-export` returns the user's
  own data as a JSON bundle.
* **Rectification** — `PATCH /api/v1/auth/profile` for self-service
  edits.
* **Erasure** — `DELETE /api/v1/auth/account` (Sprint 7 Phase B —
  "Danger zone" in the Settings page). The audit ledger's
  HMAC'd PII columns become unresolvable once the salt material
  is rotated, satisfying erasure-by-construction (R17).
* **Portability** — the data-export above is JSON and machine-
  readable.
* **Restriction / objection** — direct request to the operator;
  the platform doesn't expose a self-service toggle.

---

## 7. Children

The platform has no age check. Operators offering it to a
population that may include minors are responsible for any
additional safeguards required by local law (COPPA, GDPR-K, etc.).

---

## 8. Contact

The Controller is the operator running the deployment. Contact
details for the operator should be added by the operator at
deployment time; this repo carries no default contact.

---

## 9. Changes

This notice is versioned in git alongside the code. Material
changes (new collection categories, new retention, new processor)
should be announced via the same release-notes pipeline the
platform uses for code changes.
