# Blue-Team Report — seige-range full audit

## Scope
- Project: `/data/projects/seige-range`
- Mode: AUDIT
- Log sources inventoried:
  - **Structured app log** (stdout from `seige-range-api-1`) via `structlog` — JSON-style key=value with `duration_ms`, `method`, `path`, `request_id`, `status`, `user_id`. Captured at `redteam/launch.log`.
  - **Uvicorn access log** — single-line `INFO: <ip>:<port> - "METHOD path" status` per request.
  - **`audit_ledger` table (Postgres)** — hash-chained append-only ledger with `event_type`, `actor_type`, `actor_id`, `resource_*`, `ip_address`, `request_id`, `payload (json)`, `created_at`. Schema confirmed via `\d audit_ledger`.
  - **Prometheus `/metrics`** — request count + latency histogram per `(method, route, status_code)` per `app/middleware/metrics.py`.
  - **CSP-report intake** at `POST /csp-report` (not reachable today because CSP itself is broken — see A1).
- Attack window analysed: 2026-05-23 01:01:52 → 01:03:46 UTC (red-team active interval).

## Detection coverage matrix

| RT  | Threat | RT result | Log evidence | Score | Recommended detection |
|-----|--------|-----------|--------------|-------|-----------------------|
| A1  | T11/T24 (CSP/HSTS broken) | EXPLOITED | None — the broken header never reaches the browser, so the CSP-report endpoint never receives input either. No app log on emission. | **SILENT** | Add a startup self-test that asserts canonical header names and logs an audit row + Prometheus gauge `siege_security_headers_ok{header="csp"}=0` on regression. |
| A2  | T1/T15 (no IP rate limit) | EXPLOITED | 30 `auth.login.failed` rows in 1.9 s window for distinct emails from `127.0.0.1`. 47 total in the analysed window. App log shows each as `status=401 user_id=None`. | **PARTIAL** | Add an alert: `count(event_type='auth.login.failed') GROUP BY ip_address HAVING count>10 OVER (1 min)`. The data is in the ledger; nothing acts on it. Recommend a Prometheus counter `siege_auth_failures_total{result,ip_class}` exposed via metrics middleware for direct alerting in Grafana/Alertmanager. |
| A3  | T1 (forgot-password bomb) | EXPLOITED | 20 `auth.password.reset.request` rows in 1.0 s — `payload.email` shows same victim, half `matched=False`, half `matched=True`. | **PARTIAL** | Alert: `count(event_type='auth.password.reset.request') GROUP BY payload->>'email' HAVING count>3 OVER (10 min)` AND/OR `… GROUP BY ip_address`. Counter `siege_password_reset_requests_total{matched}`. |
| A4  | T5/T25 (webhook SSRF) | INDETERMINATE | 401 on the 2 unauthenticated probes — surfaced in uvicorn access log only. No app-level "rejected, missing auth" structured record. | **PARTIAL** | When dispatch *does* happen (with admin token), add a Sigma-style detect: `webhook.outbound.target_url_private_ip` log line at ERROR + counter `siege_webhook_target_ip_classified_total{ip_class}` (loopback/private/link-local/public). |
| A5  | T2/T19 (MFA bypass via v0 login) | EXPLOITED | One `auth.login.success` row at 01:02:10 with `payload={"username":"rt_mfa"}` — **no `mfa_pending` field** despite the user being MFA-enabled. Strong distinguishing signal vs the v1 path's `{"mfa_pending": true}`. | **OBSERVABLE** (signal present, no alert configured) | Add audit-side alert: `event_type='auth.login.success' AND payload NOT? 'mfa_pending' AND actor.mfa_enabled=true`. Or, better, decommission v0. Counter `siege_auth_login_total{path_version, mfa_state}`. |
| A6  | T12 (`/docs` exposed) | EXPLOITED | Each `GET /docs`/`/redoc`/`/openapi.json` appears in the uvicorn access log at status 200. Not flagged as anomalous. | **PARTIAL** | Alert in prod: `path IN ('/docs','/redoc','/openapi.json') AND status=200` should be zero. |
| A7  | T2 (MFA pending-token brute-force) | EXPLOITED | 20 `auth.mfa.verify.failed` rows in 0.5 s window, all from the same IP, all `payload.reason='code did not match'`, all against the same user_id. Strong signal. | **OBSERVABLE** (signal present, no alert configured) | Alert: `count(event_type='auth.mfa.verify.failed') GROUP BY actor_id HAVING count>3 OVER (5 min)` → page on-call; auto-revoke pending tokens after 5 fails. |
| A8  | T1/T11 (login-timing enumeration) | EXPLOITED | 5 `auth.login.failed` rows with `reason=bad_password` for the real user, 5 with `reason=unknown_user` for the fake one — **the ledger DOES distinguish**. App log doesn't surface the existence-class but the ledger does. | **OBSERVABLE-VIA-LEDGER** | Same `unknown_user`/`bad_password` distinction in the ledger is itself an enumeration oracle if any /admin/audit endpoint exposes the raw `payload.reason` to non-staff. Recommend: collapse `unknown_user` and `bad_password` into a single `bad_credentials` reason in the ledger payload (defence-in-depth for AS-4 and a small DSAR hygiene win). For detection: alert on `count(reason='unknown_user') > 20 / min`. |
| A9  | T1 (case-bypass) | MITIGATED | Not exploitable; lockout state propagated across case variants. | OBSERVABLE | None additional. |
| A10 | T11 (cleartext attempted-email in ledger) | EXPLOITED | DB query shows `payload.email` is the literal user-typed string (`does-not-exist-rt@example.com`, etc.). | **OBSERVABLE-AS-PRIVACY-BREACH** | This is itself a *detection by overshoot* — the ledger captures too much. Fix per AS-4: store `sha256(email)` for unmatched users; drop `payload.email` when `actor_id` is set. |

## Audit-ledger compliance (CLAUDE.md §4)

The ledger is **hash-chained** (`prev_hash` / `this_hash` columns, both 64-char check-constrained — verified). Append-only by schema (no `updated_at`; no UPDATE/DELETE invocations spotted in code review). Each row carries who (`actor_type`, `actor_id`), what (`event_type`), when (`created_at`), where (`ip_address`, `request_id`), which (`resource_type`, `resource_id`), and a structured `payload`. The six-question grid:

| State change | who | what | when | where | which | why | Verdict |
|--------------|-----|------|------|-------|-------|-----|---------|
| `auth.register` | ✅ user_id | ✅ | ✅ | ✅ ip | ✅ user | ❌ no reason field | INCOMPLETE — add `payload.reason` (always = "self-service") |
| `auth.login.success` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ no path-version field — v0 vs v1 indistinguishable except by absence of `mfa_pending` | INCOMPLETE — add `payload.path_version` ("v0"/"v1") |
| `auth.login.failed` | ✅ when matched / anonymous when unknown | ✅ | ✅ | ✅ | ✅ | ✅ `payload.reason` | COMPLETE — but stores raw email (privacy issue, AS-4) |
| `auth.password.reset.request` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ `payload.matched` | COMPLETE — but stores raw email |
| `auth.password.reset.redeem` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | COMPLETE |
| `auth.mfa.enroll/confirm/disable` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ `payload.success` | COMPLETE |
| `auth.mfa.verify.failed/success` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ `payload.reason` | COMPLETE |
| `challenge.flag.submit.pass/fail` | ✅ | ✅ | ✅ | ✅ | ✅ challenge.slug | ✅ payload with points/validator | COMPLETE |
| `instance.launch/stop/expired` | ❓ not exercised this run | — | — | — | — | — | NOT-VERIFIED |
| `admin.*` | ❓ admin endpoints not exercised this run | — | — | — | — | — | NOT-VERIFIED |

## Findings

### Critical (SILENT-COMPROMISE)

**B1 (Critical) — A1 (CSP/HSTS broken) is fully silent.**
Browsers receive `content-redacted-policy` and ignore it. The app emits no log line on broken-header-name emission (and couldn't easily — the bug is in a header *value*). The `/csp-report` intake would have been the SOC's only signal that the policy was effective; today it's mute by construction.
- **Recommended detection:** add a startup self-check in `app/main.py` that hits its own root URL via `httpx` and asserts the response has `content-security-policy` and (if prod) `strict-transport-security`. Fail-fast on regression. Also add Prometheus gauge `siege_security_headers_ok{header="csp",header="hsts"}`.
- **Alert rule:** `siege_security_headers_ok < 1` → page immediately.

### High (DETECTION-GAPS)

**B2 (High) — A2 (no IP rate limit) is observable in the ledger but no alert exists.**
47 failed logins from 127.0.0.1 in the window — the data is there, nothing fires.
- **Add metric:** `siege_auth_login_failures_total{ip_class, reason}` in `app/middleware/metrics.py` or a new audit sink.
- **Alert:** `increase(siege_auth_login_failures_total[1m]) > 10` per IP, severity High.

**B3 (High) — A5 (MFA bypass) is observable only via the *absence* of a payload field.**
v0 and v1 login successes write different payload shapes but the same `event_type`. A SIEM rule keyed on `event_type` alone misses the bypass.
- **Add field:** `payload.path_version` ("v0"/"v1") on every `auth.login.success`/`failed` row (single-line change in each router).
- **Alert:** `event_type='auth.login.success' AND payload->>'path_version'='v0' AND actor.mfa_enabled=true` → page; lock the account; review.

**B4 (High) — A7 (MFA pending-token brute-force) is observable but no auto-revoke.**
20 `auth.mfa.verify.failed` rows per pending token: ledger captured every attempt; nothing else fires.
- **Implementation:** counter in Redis keyed on `mfa_pending:<hash(token)>:fails`; revoke pending token at 5.
- **Alert:** `count(event_type='auth.mfa.verify.failed') BY actor_id WHERE count > 5 IN 5 minutes`.

**B5 (High) — A3 (password-reset bomb) — same shape as B2.** 20 events in 1 s, all `payload.email` identical.
- **Alert:** `count(event_type='auth.password.reset.request') BY payload->>'email' HAVING count > 3 IN 10 min`.

### Medium (log-quality)

**B6 (Medium) — A6 (`/docs` reachable).** Uvicorn logs it, nothing flags it. Not silent — but no SOC rule would catch repeated production probes.
- **Alert:** `path IN ('/docs','/redoc','/openapi.json') AND env=production AND status=200 — count > 0`.

**B7 (Medium) — Webhook dispatch outcomes have rich structured log on internal-error (`webhook_dispatch.py:264`) but no metric.**
- **Add:** `siege_webhook_delivery_total{status_class}` counter; histogram `siege_webhook_delivery_duration_seconds`.

**B8 (Medium) — Audit ledger stores cleartext `payload.email` on `auth.login.failed` (matches AS-4 / A10).**
Privacy concern, but also a *detection over-emission*: an analyst with read access to the ledger gets the same enumeration oracle the attacker has. Mitigate at the source: store hashed email when `actor_id` is null.

### Low (nice-to-have)

**B9 (Low) — Uvicorn access log is plain text; the parallel structlog line is JSON-ish but unparsed by default by most ingesters.**
- Switch uvicorn to `--access-log-format` JSON or disable it (the structlog middleware already covers the same surface).

**B10 (Low) — No Prometheus alerting rules live in repo (`docs/alerts/` not present).**
- Add `docs/alerts/*.yml` with the rules above as starter content.

## Sensitive data in logs

- ✅ JWTs do not appear in structured app logs (`launch.log` doesn't carry `Authorization` values).
- ⚠️ JWTs **do** appear in uvicorn WS access logs: `WebSocket /ws?token=eyJ...` — the entire access token is logged in the query string. Two such entries observed in the attack window. **High severity** — anyone with read on the API container's stdout has live tokens.
  - **Fix:** the WebSocket auth path should accept `Authorization` header (HTTP upgrade carries headers) rather than a query-string token; or uvicorn's access-log format should redact query strings; or use a short-lived signed cookie.
  - Call out in the audit report as **B11 (High)** under sensitive-data-in-logs.
- ⚠️ Audit ledger stores cleartext attempted email on `auth.login.failed` (B8 / AS-4). High.
- ✅ Password reset tokens are never logged (`password_reset.py` returns cleartext only to the caller; service returns it once, never persists).
- ✅ MFA secrets and recovery codes are not in any observed log line.

## Recommended detections (consolidated)

| Gap | Log line / metric | Alert rule | Severity |
|-----|-------------------|------------|----------|
| B1 | startup self-check assertion + `siege_security_headers_ok` gauge | `siege_security_headers_ok < 1` | Critical, page |
| B2 | `siege_auth_login_failures_total{ip_class,reason}` | `increase(…[1m]) > 10` per IP | High |
| B3 | `payload.path_version` in `auth.login.*` | `event_type='auth.login.success' AND payload.path_version='v0' AND user.mfa_enabled` | High, page |
| B4 | `siege_mfa_verify_failures_total{actor_id}` | `… > 5` in 5 min per actor_id | High |
| B5 | `siege_password_reset_requests_total{matched}` | `count BY email > 3` in 10 min | High |
| B6 | `path` label on metrics | `siege_http_requests_total{path~"/docs|/redoc|/openapi.json",env="production"} > 0` | Medium |
| B7 | `siege_webhook_delivery_*` | `rate(error) > 0.1` | Medium |
| B8 | hash email at source | (no alert; sourcing fix) | High |
| B11 | strip token from WS access log | (no alert; sourcing fix) | High |

## Verdict
**SILENT-COMPROMISE.** A1 (CSP/HSTS broken) is a silent exploited finding — the attack succeeded and produced no log trace the platform itself emits (the broken header simply doesn't reach the would-be CSP-report endpoint). Combined with multiple High-severity detection gaps and a secondary `WebSocket /ws?token=...` token-in-log issue.
