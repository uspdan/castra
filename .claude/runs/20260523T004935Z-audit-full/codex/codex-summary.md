# Codex Pre-flight Summary — seige-range full audit (AUDIT mode)

## Iterations
- Pass 1: 17 findings reviewed (14 from the audit + 3 missed), verdict KICK-BACK, transcript: `codex-transcript-1.md`.
- Pass 2: not run — Codex's KICK-BACK identifies *additions*, not refutations. Per the audit-mode protocol, additions fold into the risk register; no re-loop required (no specialist to bounce to in a single-assessor audit).

## Final verdict
**APPROVED-WITH-ADDITIONS.** Every audit finding was CONFIRMED by Codex (with three severity DOWNGRADEs noted below). Three additional findings were identified and accepted into the risk register.

## Findings routing (Pass 1)

### Confirmed (no action — already in audit report)
| ID | Severity | File:line | Category | Note |
|----|----------|-----------|----------|------|
| F1  | CRITICAL  | `backend/app/middleware/security_headers.py:108` | security | header literals corrupted |
| F2  | HIGH      | `backend/app/main.py:154` | security | `/docs` exposed |
| F3  | CRITICAL  | `backend/app/routers/auth.py:106` | security | legacy login bypasses MFA |
| F4  | HIGH      | `backend/app/middleware/rate_limit.py:48` | security | auth limiter unused |
| F5  | HIGH      | `backend/app/middleware/rate_limit.py:43` | security | proxy-IP rate-limit key |
| F7  | HIGH      | `backend/app/routers/v1/auth.py:452` | security | forgot-password unlimited |
| F8  | HIGH      | `backend/app/services/mfa.py:176` | security | no MFA verify cap |
| F9  | HIGH      | `backend/app/routers/v1/auth.py:248` | security | login timing oracle |
| F12 | HIGH      | `frontend/package.json:15` | maintainability | floating deps |
| F13 | HIGH      | `.github/workflows/ci.yml:47` | test | CI bypasses coverage |
| F14 | HIGH      | `frontend/src/hooks/useWebSocket.js:17` | security | WS token in URL |

### Downgrades (Codex disputed severity; accepted)
| ID | Audit severity | Codex severity | File:line | Note |
|----|----------------|----------------|-----------|------|
| F6  | CRITICAL → HIGH | `backend/app/services/webhook_dispatch.py:228` | "admin-only create path mediates impact" |
| F10 | HIGH → MEDIUM   | `backend/app/routers/v1/auth.py:258` | "privacy issue, not a direct security vuln" |
| F11 | MEDIUM → LOW    | `backend/app/models.py:562` | "standards violation, not a security vuln" |

### Missed (added to risk register)
| ID  | Severity | File:line | Category | Finding |
|-----|----------|-----------|----------|---------|
| **C-M1** | HIGH | `backend/app/routers/v1/auth.py:687-722` (`mfa_enroll_v1` + `mfa_confirm_v1`) | security | MFA enrolment + confirm rotates a user's MFA with only an access token. A stolen access token (XSS, leaked log, etc.) lets the attacker register their own TOTP, with no prior-password or prior-MFA re-auth gate. The route docstring acknowledges "rotates the secret" but doesn't gate it. |
| **C-M2** | HIGH | `backend/app/routers/auth.py:106-186` | security | v0 login bypasses the `REQUIRE_EMAIL_VERIFIED` gate. v1 (`routers/v1/auth.py:283-301`) refuses login until verified; v0 doesn't check. Same root cause as F3 (v0 router is feature-stale). |
| **C-M3** | MEDIUM | `backend/app/services/auth.py:50-58` | security | JWT decode does not pass `audience=` or `issuer=` to `jose.jwt.decode` — only signature + exp + token-type are validated. The `algorithms=[ALGORITHM]` allowlist defends against alg-confusion, but issuer/audience confusion would let any HS256-signed token from another product using the same SECRET_KEY validate here. Minor in practice (SECRET_KEY is per-deploy) but the standard expects explicit aud/iss validation. |

## Accepted residual risks (this iteration)
- The three downgrades above are accepted: webhook SSRF is admin-mediated; ledger email leak is a privacy/storage-minimisation issue rather than a direct exploit primitive; file-size violations are engineering-standard debt rather than a security vulnerability. The risk register reflects the downgraded severities.
- No findings were dropped to FALSE-POSITIVE.

## Transcript paths
- `codex/codex-transcript-1.md` (one-shot pass, 264 KB — includes Codex's source-reading actions and per-finding verdicts).
- `codex/codex-canary-3.md` (sanity check confirming Codex was operational against the file system).
