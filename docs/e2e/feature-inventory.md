# seige-range — feature inventory

> Compiled 2026-05-24 as the spec for the end-to-end test plan.
> Every entry cites `file_path:line_number`; corresponding deep-dives live in
> `/tmp/seige-feature-inventory-{backend,frontend}.md`.

This is the walked, ranked, deduplicated list of every user-visible feature,
every state-changing surface, every integration, every export, every role
permission, every lifecycle hook, and every existing test handle. It exists
so that the E2E plan can map 1:1 against features rather than against
files.

---

## A. Routes & pages

### A.1 Public (no auth)

| Route | Page | Backend surface |
|---|---|---|
| `/login` | `pages/Login.jsx:6` — email/password, pivots to TOTP/recovery on `mfa_required` | `POST /api/v1/auth/login`, `POST /api/v1/auth/mfa/verify` |
| `/register` | `pages/Register.jsx:6` — email + username + display_name + password + red/blue team | `POST /api/v1/auth/register` |
| `/forgot-password` | `pages/ForgotPassword.jsx:6` — request reset (always 202) | `POST /api/v1/auth/forgot-password` |
| `/reset-password?token=` | `pages/ResetPassword.jsx:6` — new password (≥8) + redirect to `/login` after 2s | `POST /api/v1/auth/reset-password` |
| `/verify-email?token=` | `pages/VerifyEmail.jsx:6` — auto-POSTs token on mount | `POST /api/v1/auth/verify-email` |

### A.2 Authenticated (operator)

| Route | Page | Notes |
|---|---|---|
| `/` | `pages/Dashboard.jsx:9` | stats cards, weekly activity chart, top-5 leaderboard, MITRE coverage; four parallel fetches on mount |
| `/challenges` | `pages/Challenges.jsx:12` | catalogue grid + filters + slide-in detail (`launch`, `submit`, `hints`) |
| `/challenges/:slug` | `pages/ChallengeDetail.jsx:12` | standalone detail page, same affordances |
| `/leaderboard` | `pages/Leaderboard.jsx:6` | all-time + per-team + weekly |
| `/profile/:username` | `pages/Profile.jsx:7` | stats, recharts skill radar, MITRE, solve history |
| `/settings` | `pages/Settings.jsx:15` | Email / Profile / Password / MFA / Danger-zone tabs |
| `/workstation` | `pages/Workstation.jsx:12` | launch / stop / SSH+web-shell strings / one-shot password |
| `/deploy` | `pages/Deploy.jsx:3` | static runbook docs |
| `*` | `pages/NotFound.jsx:3` | **declared outside `ProtectedRoute`** (`App.jsx:42`) |

### A.3 Admin

| Route | Page | Notes |
|---|---|---|
| `/admin` | `pages/Admin.jsx:21` | 6 tabs: Users / Challenges / Competitions / Webhooks / Audit / System. Self-redirects when `user.role !== 'admin'` (`Admin.jsx:26-28`) — client-side only; the backend re-enforces |

### A.4 Layout-mounted

Wrappers visible on every authed route (`components/Layout.jsx`):

- top nav (Overview, Challenges, Rankings, Workstation, Deploy)
- brand mark → `/`
- connection-state pill (LIVE/OFFLINE), driven by `useWebSocket().connectionState`
- `<NotificationDropdown />` (bell + unread badge)
- user-menu (Profile / Settings / **Admin (gated)** / Logout)
- `<CompetitionBanner />` sticky banner when a competition is active
- `<LiveFeed />` collapsible bottom-right flag-capture feed
- `<ToastViewport />` toast stack

---

## B. Forms (every write surface in the UI)

### B.1 Auth

| Form | File:line | Fields | Endpoint |
|---|---|---|---|
| Login (email/pw) | `Login.jsx:109-131` | email, password | `POST /api/v1/auth/login` |
| Login MFA step | `Login.jsx:72-106` | `mfaCode` 6-8 chars | `POST /api/v1/auth/mfa/verify` |
| Register | `Register.jsx:41-63` | email, username, display_name, password (≥8), confirm match, team (red/blue) | `POST /api/v1/auth/register` |
| Forgot password | `ForgotPassword.jsx:56-83` | email | `POST /api/v1/auth/forgot-password` |
| Reset password | `ResetPassword.jsx:76-115` | password (≥8), confirm match | `POST /api/v1/auth/reset-password` |
| Verify email (mount) | `VerifyEmail.jsx:13-27` | token (URL) | `POST /api/v1/auth/verify-email` |

### B.2 Settings

| Form | File:line | Fields | Endpoint |
|---|---|---|---|
| Resend verification | `Settings.jsx:548-588` | — | `POST /api/v1/auth/resend-verification` |
| Profile | `Settings.jsx:41-104` | display_name, team | `PATCH /api/v1/auth/profile` |
| Change password | `Settings.jsx:109-185` | current, new (≥8), confirm | `POST /api/v1/auth/change-password` |
| MFA enrol — start | `Settings.jsx:378-403` | `enrollPw` | `POST /api/v1/auth/mfa/enroll` |
| MFA enrol — confirm | `Settings.jsx:292-333` | TOTP `code` | `POST /api/v1/auth/mfa/confirm` (returns recovery codes once) |
| MFA disable | `Settings.jsx:334-377` | password, code | `POST /api/v1/auth/mfa/disable` |
| Delete account | `Settings.jsx:482-504` | password (+ `window.confirm`) | `DELETE /api/v1/me` |
| Export my data | `Settings.jsx:471-479` | button | `GET /api/v1/me/data` → JSON blob download |

### B.3 Challenges

| Form | File:line | Fields | Endpoint |
|---|---|---|---|
| Flag submission | `components/FlagSubmission.jsx:36-81` | `flag` | `POST /api/v1/challenges/{slug}/submit` |
| Hint unlock | `Challenges.jsx:244-251` | button (no confirm) | `POST /api/v1/challenges/{slug}/hint` |

### B.4 Admin

| Form | File:line | Fields | Endpoint |
|---|---|---|---|
| Challenge create | `components/ChallengeEditor.jsx:113-194` (mode=create) | title, slug, description, category, team, difficulty 1-5, points 1-10000, flag `CTF{…}`, docker_image, docker_port, prerequisite_ids, docker_config JSON, hints JSON | `POST /api/v1/admin/challenges` |
| Challenge edit | same component (mode=edit) | same minus flag | `PUT /api/v1/admin/challenges/{slug}` |
| Audit filters | `Admin.jsx:679-695` | `action`, `user_id` | `GET /admin/audit` |
| Challenge filters | `Admin.jsx:270-319` | search, teamFilter, releaseFilter | client-side |
| Webhook create | `Admin.jsx:531-580` | name, target_url (HttpUrl), events (csv, closed allowlist + wildcard `*` rule + `dpa_acknowledged` for PII events) | `POST /api/v1/webhooks` |

> **Gaps acknowledged from the inventory**: no writeup create/rate/approve UI, no competition create UI, no per-user admin edit modal, no challenge release scheduling UI. Backend endpoints exist (`/writeups`, `/competitions`); frontend doesn't surface them.

---

## C. One-click mutation buttons (no form)

| Action | File:line | API |
|---|---|---|
| Instance LAUNCH (panel) | `Challenges.jsx:215-219` | `POST /instances/{slug}/launch` |
| Instance LAUNCH (detail) | `ChallengeDetail.jsx:80-84` | same |
| Instance STOP | `InstancePanel.jsx:126-138` | `DELETE /instances/{id}` |
| Instance RESET | `InstancePanel.jsx:139-151` | `POST /instances/{id}/reset` |
| Notification — mark read | `NotificationDropdown.jsx:48-50` | `PUT /notifications/{id}/read` |
| Notification — mark all | `NotificationDropdown.jsx:39-41` | `PUT /notifications/read-all` |
| Workstation launch | `Workstation.jsx:113-118` | `POST /api/v1/workstation/launch` |
| Workstation stop | `Workstation.jsx:195-198` | `POST /api/v1/workstation/stop` |
| Workstation copy SSH cmd | `Workstation.jsx:128-130` | clipboard |
| Workstation copy one-shot pw | `Workstation.jsx:148-150` | clipboard |
| Webhook delete | `Admin.jsx:510-513` | `DELETE /api/v1/webhooks/{id}` |
| Webhook delivery replay | `Admin.jsx:637-641` | `POST /api/v1/webhooks/{id}/deliveries/{deliveryId}/replay` |
| Admin user — toggle role | `Admin.jsx:136-141` | `PUT /api/v1/admin/users/{id}` |
| Admin user — toggle active | `Admin.jsx:146-149` | same |
| Challenge release (one) | `Admin.jsx:344-346` | `POST /api/v1/admin/challenges/{slug}/release` |
| Challenge bulk release | `Admin.jsx:306-312` | loop `POST /api/v1/admin/challenges/{slug}/release` |
| Challenge soft delete | `Admin.jsx:354-357` | `DELETE /api/v1/admin/challenges/{slug}` |
| Seed catalogue | `Admin.jsx:826-830` | `POST /api/v1/admin/seed` |
| Logout | `Layout.jsx:126-133` | `POST /api/v1/auth/logout` |

---

## D. Role & permission matrix

Roles in `UserRole` (`backend/app/models/_base.py:20`): `operator` (default), `admin`. Audit ledger actor types add `system` and `anonymous`.

| Capability | anon | operator | admin |
|---|:---:|:---:|:---:|
| Browse `/health`, `/readyz`, `/metrics`, `/csp-report` | ✅ | ✅ | ✅ |
| Register / login / refresh / forgot / reset / verify / MFA-verify | ✅ | — | — |
| Anything `Depends(get_current_user)` | ❌ | ✅ | ✅ |
| List & detail challenges (v1 + legacy) | ❌ | ✅ | ✅ |
| Submit flag, unlock hint, progress | ❌ | ✅ | ✅ |
| Launch own instance (cap 3 active, 1 per challenge) | ❌ | ✅ | ✅ |
| Stop / reset **own** instance | ❌ | ✅ | ✅ |
| Stop / reset other user's instance | ❌ | ❌ | ❌ *(self-only guard at `routers/instances.py:126`)* |
| Read own stats / notifications | ❌ | ✅ | ✅ |
| Read another user's stats | ❌ | ❌ | ✅ *(admin override at `stats.py:184`)* |
| Write writeup (post-solve), rate writeup | ❌ | ✅ | ✅ |
| Approve writeup | ❌ | ❌ | ✅ |
| Workstation launch / stop | ❌ | ✅ | ✅ |
| Account delete (`DELETE /api/v1/me`) | ❌ | ✅ | ✅ |
| GDPR data export (`GET /api/v1/me/data`) | ❌ | ✅ | ✅ |
| Admin CRUD challenges, flags, seed, audit, system | ❌ | ❌ | ✅ |
| Promote/demote user, toggle active | ❌ | ❌ | ✅ |
| Create / list / delete webhook, view + replay deliveries | ❌ | ❌ | ✅ |
| Create / activate competition | ❌ | ❌ | ✅ |
| Operator PDF report | ❌ | ❌ | ✅ |

Gates affecting login flow:
- account lockout 5/15min (`services/auth.py:140`)
- `REQUIRE_EMAIL_VERIFIED=true` returns 403 (`routers/v1/auth.py:329`)
- MFA second step: 5 attempts per pending-jti (`mfa.py:47`, `routers/v1/auth.py:1058`)
- per-email forgot-password 3/h throttle (`routers/v1/auth.py:553`)

Client-side gates in the UI:
- `isAdmin = user?.role === 'admin'` → user-menu "Admin" link only (`Layout.jsx:16`, `:116-125`)
- `/admin` self-redirect when not admin (`Admin.jsx:26-28`) — **flash visible before redirect**
- `useAuthStore.isAdmin` getter at `authStore.js:13-15` — declared, never read
- no team-based gate anywhere (red and blue users see identical UI)

---

## E. Integrations

### E.1 Outbound

| Integration | Wiring | Trigger |
|---|---|---|
| SMTP | `services/email.py:63` | password reset, email verification; dev stderr fallback (`:84`); test buffer (`:56`) |
| Outbound webhooks (Slack/Teams/generic) | `services/webhook_dispatch/`; HMAC sign + SSRF guard (`services/webhook_ssrf.py:92`); retry, prune, replay | configured via `POST /api/v1/webhooks`; fan-out on `challenge.released`, etc. |
| OpenTelemetry | `observability/tracing.py:49` | opt-in via `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Docker (docker-socket-proxy) | `services/orchestration/docker_client.py:26` | every instance launch / stop |
| DinD orchestrator | same | port range `INSTANCE_PORT_MIN..MAX` |
| Egress proxy (tinyproxy) | `services/orchestration/networking.py:27`, `services/orchestration/egress.py` | allowlist re-rendered on each launch (`launcher.py:392`); SIGHUP |
| Per-instance egress sidecar | `services/orchestration/sidecar.py` | profile `egress-proxied-sidecar` |
| YARA / Sigma engines | subprocess sandbox (`services/validator_subprocess_runner.py`) | inside flag-dispatch when a challenge uses those validators |
| `pg_dump` | `services/backup.py:100` | nightly scheduler |
| Redis | `main.py:90` | ws pub/sub, rate limit, leaderboard cache, lockouts, MFA jti cap, instance locks |
| Postgres | `database.py` | every request |

> Not present despite being mentioned in the brief: **WireGuard** (deployment-layer only, surfaced via `/deploy` docs), **ClamAV**.

### E.2 Inbound

| Integration | Wiring |
|---|---|
| CORS | `main.py:209`, `settings.ALLOWED_ORIGINS`; fatal in prod when empty (`config.py:191`) |
| JWT | `iss=siege-range`, `aud=siege-range-api`, HS256 (`services/auth.py:24`) |
| WebSocket subprotocol token | `Sec-WebSocket-Protocol: siege-auth.<JWT>` (`routers/ws.py:26`); query-string auth removed in v2.5.1 |
| Proxy header trust | `settings.TRUST_PROXY_HEADERS` enables left-most XFF for rate-limit keys |
| CSP report | `POST /csp-report` (`routers/health.py:169`) |

---

## F. Exports / downloads

| Trigger | Format | File:line |
|---|---|---|
| `GET /admin/reports/operator/{user_id}` (admin only) | PDF (WeasyPrint, template `templates/reports/operator_report.html`) | `routers/admin.py:278` |
| `GET /api/v1/me/data` (any authed) | JSON (GDPR Art. 15: profile + solves + solved_flags + instances + writeups + hint_unlocks + audit) | `routers/v1/me.py:90` |
| Settings → Export my data | wraps the above into a synthetic `<a download>` → `siege-range-data-{ts}.json` | `Settings.jsx:417-439` |
| `GET /admin/audit` | JSON page of ledger rows | `routers/admin.py:108` |
| Scheduler nightly DB backup | `pg_dump | gzip` → `siege-<utc-iso>.sql.gz` under `BACKUP_DIR` | `services/backup.py:100`, `services/scheduler.py:359` |
| Scheduler egress allowlist render | tinyproxy filter file at `EGRESS_FILTER_PATH` | `services/orchestration/egress.py` |
| CLI tools | `app.tools.{audit_verify,render_egress_allowlist,load_challenges}` | `app/tools/` |

No CSV, no scoreboard download, no manifest export, no VPN-config download surfaced in the UI.

---

## G. Feature flags & config knobs (`backend/app/config.py`, `Settings` class)

| Field | Default | Gates |
|---|---|---|
| `APP_ENV` | `development` | docs surface, email mode, validator enforcement |
| `SECRET_KEY` | required (no default) | JWT HS256; placeholder-list rejected |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin@siege.local` / required | bootstrap admin on startup |
| `ALLOWED_ORIGINS` | "" | CORS allowlist; **required in prod** |
| `TRUST_PROXY_HEADERS` | `False` | XFF-based rate-limit keying |
| `AUDIT_LEDGER_RETENTION_DAYS` | `365` | ledger pruning |
| `AUDIT_PII_SALT` | "" → `SECRET_KEY` | HMAC of emails/IPs in ledger |
| `AUDIT_HASH_IPS` | `False` | hash `ip_address` in ledger |
| `RATE_LIMIT_AUTH_PER_MIN` | `5` | auth limiter budget; **capped at 20 outside dev/test** |
| `RATE_LIMIT_AUTH_BURST_PER_5MIN` | `5` | reset/MFA-verify budget; **capped at 20** |
| `RATE_LIMIT_FLAG_PER_MIN` | `10` | flag-submit budget; **capped at 60** |
| `RATE_LIMIT_GENERAL_PER_MIN` | `100` | general budget; **capped at 600** |
| `DOCKER_HOST` | `tcp://orchestrator:2376` | docker-socket-proxy |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `CONTAINER_TIMEOUT` | `7200` | instance TTL (capped per profile) |
| `REQUIRE_IMAGE_DIGEST` | `True` | refuses manifests without `container.digest` |
| `INSTANCE_PORT_MIN` / `MAX` | `10000` / `10049` | publish range |
| `EGRESS_FILTER_PATH` | `None` | tinyproxy allowlist path; SIGHUP step "harmlessly fails" until set |
| `SCORING_MODE` | `static` | `"dynamic"` enables decay |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | `30` / `7` | JWT TTLs |
| `SMTP_*` / `MAIL_FROM` / `FRONTEND_URL` | None | all **required in prod** |
| `PASSWORD_RESET_TTL_MINUTES` | `60` | reset token TTL |
| `REQUIRE_EMAIL_VERIFIED` | `False` | gates login |
| `BACKUP_DIR` | `/var/lib/siege-range/backups` | empty disables backup |
| `BACKUP_RETENTION_DAYS` | `30` | |

Production-fatal at boot (`_emit_fatal_and_exit`): `SECRET_KEY`, `ADMIN_PASSWORD`, `ALLOWED_ORIGINS`, `SMTP_HOST`, `MAIL_FROM`, `FRONTEND_URL`, plus any `RATE_LIMIT_*` budget above its ceiling (staging is capped too, not just production).

External env vars not in `Settings`: `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_TRACES_SAMPLER*`.

---

## H. Lifecycle hooks

### H.1 Backend — APScheduler (`services/scheduler.py:342`)

| Job | Trigger | What it does |
|---|---|---|
| `cleanup_expired` | every 5 min | stop/remove expired instances + orphan sweep; ledger `instance.expired` |
| `cache_leaderboard` | every 60 s | Redis `siege:leaderboard` (TTL 120 s) |
| `notification_cleanup` | cron 03:00 UTC | delete read notifs >30 d |
| `webhook_retry` | every 1 min | replay retriable deliveries |
| `webhook_prune` | cron 04:00 UTC | drop deliveries >30 d |
| `audit_verify` | every 1 h | re-walk hash chain; gauge + counter; global `audit_tamper` notification on finding |
| `db_backup` | cron 02:30 UTC | `pg_dump` + gzip + retention |
| `workstation_reap` | every 1 h | stop+remove workstations idle >8 h (preserve home vol) |
| `cheat_burst_detector` | every 5 min | admin notification when ≥8 passes in 15 min |
| `audit_ledger_prune` | cron 04:30 UTC | drop rows past `AUDIT_LEDGER_RETENTION_DAYS` |

### H.2 Backend — FastAPI lifespan (`main.py:79`)

Startup order: `init_db()` → bootstrap admin → connect Redis → warm docker client → sweep orphan instances → `setup_scheduler()` → start ws pubsub listener.

Shutdown: cancel pubsub → `scheduler.shutdown(wait=False)` → close docker → close Redis → close shared httpx client.

Pre-FastAPI (module-import): `_validate_seccomp_profiles_or_exit()` — malformed profile aborts boot.

### H.3 Frontend — useEffect / interval chains

| Behaviour | File:line |
|---|---|
| Auth-store rehydration on app boot | `authStore.js:5-7` (reads `access_token`/`refresh_token`/`user` from localStorage synchronously) |
| Axios 401-refresh interceptor (single retry) | `api/client.js:16-43` — **known `/api/api/v1/auth/refresh` double-prefix bug at `:26`** |
| Dashboard parallel fetch on mount | `Dashboard.jsx:16-34` |
| Challenges list re-fetch on filter change | `Challenges.jsx:23,29-30` (300 ms debounce on search) |
| Leaderboard re-fetch on `teamFilter` | `Leaderboard.jsx:11` |
| Notification badge bootstrap | `NotificationDropdown.jsx:9-12` |
| Instance countdown (1s interval) | `InstancePanel.jsx:40-43` (`EXPIRED` text at ≤0; **does not auto-stop**) |
| Competition countdown (1s interval) | `CompetitionBanner.jsx:17-29` |
| Verify-email auto-POST | `VerifyEmail.jsx:13-27` |
| MFA confirm/disable re-fetch me | `Settings.jsx:241,258` |
| WS reconnect with exponential backoff | `useWebSocket.js:48-54` |
| Admin client-side redirect | `Admin.jsx:26-28` |
| Reset-password 2 s redirect | `ResetPassword.jsx:40` |

### H.4 Domain state machines

- **Instance**: `pending → running → stopped | failed`, plus reconciliation row state `expired` (`services/orchestration/cleanup.py:102`). Cap 3 active per user, 1 per challenge, per-user/slug Redis lock.
- **Competition**: created → activated → `is_live = is_active AND starts_at ≤ now ≤ ends_at`. No explicit "closed" state.
- **Writeup**: created with `is_approved=False` → admin approves. No rejected state — admin just leaves unapproved.
- **Notification**: created (per-user or global) → `is_read=True`.
- **MFA**: not-enrolled → pending (`start_enrolment`) → enabled (`confirm_enrolment`, generates 10 hashed recovery codes) → not-enrolled (`disable_mfa`). Pending JWT TTL 90 s, 5 attempts per jti.
- **Email verification**: token issued at register/resend → `email_verified=True` on redeem. TTL 24 h.
- **Password reset**: sha256 token (`PasswordResetToken`), TTL `PASSWORD_RESET_TTL_MINUTES`, single-use (`used_at`). Per-email 3/h throttle.
- **Refresh token revocation**: logout writes `siege:blacklist:{token}` with TTL=`exp-now`; refresh handler rejects on hit.

---

## I. Audit / observability events

### I.1 Audit ledger event types (allowlisted, `services/audit/events.py:32`)

`auth.{register, login.success, login.failed, logout, refresh, password.reset.request, password.reset.redeem, password.change, profile.update, account.delete, data.export, mfa.enroll, mfa.confirm, mfa.disable, mfa.verify.success, mfa.verify.failed, email.verify.request, email.verify.redeem}`, `challenge.{flag.submit.pass, flag.submit.fail, released}`, `instance.{launch, stop, reset, expired}`, `workstation.{launch, stop, attached}`.

Append writer is single-writer via `pg_advisory_xact_lock` (`services/audit/ledger.py:127`).

### I.2 Prometheus metrics (`/metrics`)

- `http_requests_total{method,route,status}`
- `http_request_duration_seconds{method,route}`
- `http_requests_in_progress{method}`
- `siege_audit_last_verify_timestamp_seconds`
- `siege_audit_tamper_findings_total`

### I.3 structlog events

HTTP request log: `event="request"` with `{request_id, method, path, status, duration_ms, user_id}` (`middleware/logging_mw.py:33`). Boot/lifecycle, scheduler, workstation, validator-registry, webhook-dispatch events all listed in the backend inventory §8.

---

## J. Validators & plugins

### J.1 Flag validator entry points (`services/validator_registry.py:33`)

| Name | Class | Sandboxed? |
|---|---|---|
| `exact` | `validators/exact.py:34` | no |
| `regex` | `validators/regex.py:94` | no |
| `multi_part` | `validators/multi_part.py:32` | no |
| `sigma_rule` | `validators/sigma_rule.py:54` | yes |
| `yara_rule` | `validators/yara_rule.py:62` | yes |
| `chain_of_custody` | `validators/chain_of_custody.py:61` | yes |
| `attack_chain` | `validators/attack_chain.py:65` | no |
| `cloud_misconfig` | `validators/cloud_misconfig.py:63` | no |
| `llm_signal` | `validators/llm_signal.py:45` | no |

### J.2 Container profiles (`services/orchestration/profiles.py:219`)

`default-strict`, `malware-sandbox`, `egress-proxied`, `egress-proxied-sidecar`, `llm-sandbox`, `suid-allowed`. Profile-managed fields cannot be overridden by manifests (`launcher.py:71`).

### J.3 Seccomp profiles (`security/seccomp/`)

`default-strict.json`, `malware-sandbox.json`. SHA-256 captured into `ChallengeInstance.seccomp_profile_sha256` on launch.

---

## K. Existing E2E test-handle surface

`data-testid` attributes already in source (deduped, 59 handles total). The complete list lives in the frontend inventory §12; the **reachability gaps** to address with new test handles or in-spec workarounds:

- Top nav links (Overview / Challenges / Rankings / Workstation / Deploy)
- Connection-state pill, notification bell + badge + dropdown items + mark-all-read
- LiveFeed rows + collapse
- CompetitionBanner title + countdown
- ChallengeCard (the catalogue grid cell)
- Hint unlock button
- Workstation copy / SSH / web-shell rows
- **Register form (no `data-testid` on any field — biggest auth-flow gap)**
- All admin tables (user rows, role/active toggles, challenge release button, soft-delete, edit pencil)
- Webhook delete + delivery replay + secret-shown-once banner
- Audit table rows
- System tab readiness probes + Seed button
- Settings: Email card overall, MFA "I've saved them" confirmation
- Pagination prev/next on admin tables

---

## L. Known issues that the E2E plan should explicitly assert against

These are findings from the inventory pass — each is one spec away from being a fixed regression test.

1. **Double-`/api` bug** in axios refresh URL at `api/client.js:26` — interceptor refresh path is `/api/api/v1/auth/refresh`. Test by forcing a 401 in browser and asserting the original request replays.
2. **Two parallel WebSockets** — `Layout` and `LiveFeed` both call `useWebSocket()`. Hook isn't a singleton.
3. **`authStore.fetchMe` is dead code** — `user` snapshot can drift from server reality after role demotions, MFA changes from another session.
4. **Expired instances don't auto-stop** — countdown shows `EXPIRED` but the panel stays interactive; stop button may 404.
5. **`/admin` redirect is client-side only** — admin tab strip flashes before the `useEffect` redirects.
6. **Hint unlock has no confirm dialog** — single click charges 50% of points.
7. **Sensitive secrets in plain DOM**: workstation one-shot password (`Workstation.jsx:147`), MFA secret (`Settings.jsx:298`), webhook secret (`Admin.jsx:475`), MFA recovery codes (`Settings.jsx:277-283`).
8. **Version-string drift**: `/health` returns `"2.4.1"`, FastAPI title returns `"2.5.0"`, `/admin/system` returns `"2.4.1"`.
9. **Legacy vs v1 status-code drift**: e.g. already-solved is 400 in legacy (`routers/challenges/engagement.py:50`) vs 409 in v1 (`routers/v1/submit.py:72`).
10. **`v1/submit` permanently returns `validator: None`** in its response.
11. **`actor_id.isdigit()` filter in `routers/admin.py:161`** silently drops system-actor rows from the admin audit view.
12. **`EGRESS_FILTER_PATH` default-None** silently no-ops the SIGHUP step.
13. **NotFound outside `ProtectedRoute`** (`App.jsx:42`) — accessible without auth.

---

## M. E2E coverage plan (derived from sections A–K)

Specs are ordered by dependency: register → login → catalogue → submit → instance → admin → integrations. Specs marked **(have)** already exist in `frontend/tests/e2e/`; the rest are new.

### M.1 Auth & identity

- **(have)** login.spec.js — register → login → dashboard; wrong password; logout (the testid edit makes this stable).
- **NEW** register.spec.js — happy path; password mismatch; weak password; duplicate email; duplicate username; bad team value.
- **NEW** forgot-reset.spec.js — request reset → fetch token from dev SMTP buffer or audit ledger → reset → log in with new password.
- **NEW** verify-email.spec.js — register → token in dev SMTP → `/verify-email?token=` → flag flipped; expired/invalid token surface.
- **NEW** mfa.spec.js — enrol (capture secret), generate TOTP, confirm, see recovery codes once; login pivots to MFA step; verify code; disable MFA. Skip if `otplib` / `pyotp` unavailable in runner.
- **NEW** change-password.spec.js — happy path; wrong current; new ≠ confirm.
- **NEW** account-delete.spec.js — wrong password rejected; right password deletes, logs out, sets storage clean, GDPR row written.
- **NEW** rate-limit.spec.js — drop the bypass header, hammer login 6× from one IP, expect 429.

### M.2 Catalogue & challenge engagement

- **(have)** hint.spec.js — locked hint becomes visible after unlock (currently failing — needs UI refetch verification).
- **(have)** progress.spec.js — multi-flag chips; chip flips on success.
- **(have)** submit.spec.js — correct flag; wrong flag; already-solved → 409 (currently failing — flag-literal fix already applied to working tree).
- **NEW** challenge-filters.spec.js — search debounce; team filter; difficulty filter; clear-filters.
- **NEW** challenge-detail.spec.js — `/challenges/:slug` standalone page renders, has same affordances.
- **NEW** prereq.spec.js — submitting a flag for a challenge whose `prerequisite_ids` are unsolved returns 412 and the UI renders "Prerequisites not met — solve first: …".

### M.3 Instance lifecycle

- **(have)** instance-lifecycle.spec.js — launch → STOP → LAUNCH; launch → RESET; countdown chip. Currently failing — investigate orchestrator wiring; gate behind `E2E_SKIP_LIFECYCLE` only as last resort.
- **(have)** instance-panel.spec.js — LAUNCH button visible without instance; click reaches loading state.
- **NEW** instance-caps.spec.js — fourth concurrent launch refused (409); second launch of same slug refused.
- **NEW** instance-self-only.spec.js — user A cannot DELETE user B's instance (403 via direct API call from a second authed context).
- **NEW** instance-expired.spec.js — wait past TTL (or manually set in DB via admin path), assert countdown shows `EXPIRED` and stop action surfaces a clean error.

### M.4 Workstation

- **NEW** workstation.spec.js — launch → status returns SSH + web-shell URLs + one-shot password (shown once) → stop. Idempotent re-launch returns existing without exposing pw again.

### M.5 Leaderboard / dashboard / profile

- **(have)** leaderboard.spec.js — renders; viewer row distinguished. Second test currently fails — fix by seeding one solve before navigation.
- **NEW** dashboard.spec.js — four cards render; weekly chart paints; top-5 leaderboard shows.
- **NEW** profile.spec.js — `/profile/:username` for the viewer + for another seeded user.

### M.6 Settings

- **NEW** settings-profile.spec.js — display_name + team patch; UI reflects fresh `user`.
- **NEW** settings-export.spec.js — Export my data → JSON file downloaded, schema sanity-checked.
- **NEW** settings-mfa.spec.js — enrol + confirm + disable.
- **NEW** settings-password.spec.js — same as M.1 change-password (cross-link).
- **NEW** settings-resend-verification.spec.js — toast on success.

### M.7 Notifications & realtime

- **NEW** notifications-bell.spec.js — bell badge updates after a backend-emitted notification (use `services/notifications.create_notification` via admin seed path or webhook-triggered event); mark single / mark all both flip badge.
- **NEW** ws-livefeed.spec.js — another seeded user submits a correct flag (via API), the viewer's LiveFeed gains a row within X seconds.
- **NEW** ws-connection-pill.spec.js — pill is LIVE when ws is open; deliberately kill the ws (e.g. break network via Playwright `context.setOffline`), pill flips to OFFLINE.

### M.8 Admin (admin role required)

- **NEW** admin-users.spec.js — promote operator to admin, demote, toggle active. Audit rows written.
- **NEW** admin-challenge-create-edit.spec.js — create via editor (JSON config field, hints JSON, prereqs csv); release; soft-delete; bulk release of all drafts; seed.
- **NEW** admin-audit.spec.js — filter by action substring; filter by user_id; system-actor rows are missing today (asserts the `isdigit()` regression).
- **NEW** admin-webhooks.spec.js — create with closed-allowlist events; DPA acknowledgement required for PII events; secret shown once; delete; list deliveries; replay one; SSRF guard rejects `http://127.0.0.1`.
- **NEW** admin-system.spec.js — system tab renders readiness probes; seed button works.
- **NEW** admin-pdf-report.spec.js — `GET /admin/reports/operator/{id}` returns a PDF; content-type and size sanity.

### M.9 Integration surface (API only — no UI)

- **NEW** api-cors.spec.js — `OPTIONS /api/v1/auth/login` from disallowed origin denies; allowed origin succeeds.
- **NEW** api-csp-report.spec.js — `POST /csp-report` returns 204 and increments structlog counter.
- **NEW** api-metrics.spec.js — `GET /metrics` returns Prometheus exposition with the five expected metric names.
- **NEW** api-readyz.spec.js — `/readyz` returns 200 when DB+Redis healthy; flip to 503 by stopping Redis (skip if compose can't be touched mid-run).
- **NEW** api-jwt-iss-aud.spec.js — token signed with wrong `iss`/`aud` rejected at 401.

### M.10 Validator plugins (one spec per non-`exact` validator)

For each, seed a challenge wired to that validator, submit the matching artifact and a non-matching one.

- regex: seed `pattern: "^secret-\\d+$"`, submit `secret-42` → pass; `nope` → fail.
- multi_part: seed two-step composite, submit half → fail; submit both → pass.
- sigma_rule (sandboxed): minimal sigma rule + log line input; depend on subprocess sandbox in dev.
- yara_rule (sandboxed): minimal yara rule + byte artifact.
- chain_of_custody (sandboxed): manifest with the documented JSON shape.
- attack_chain: documented JSON ordered-events shape.
- cloud_misconfig: documented JSON ordered-events shape.
- llm_signal: documented JSON shape.

These belong in `backend/tests/integration/` rather than Playwright (they don't exercise UI) — keep them out of the browser layer.

### M.11 Per-challenge exercise validation

For each released challenge under `/data/projects/seige-range/challenges/<slug>/`:

1. Read `challenge.json` (or v2 manifest) for slug + flag(s) + image + port.
2. Via admin API: seed (if not already), release.
3. As operator: launch instance, assert running + countdown.
4. Submit the real flag(s); assert pass; assert audit row, leaderboard delta, solve count delta.
5. Stop instance.

This is one Playwright `test.describe.parallel` block driven by a `for (const challenge of …)` over the manifest list, with the docker dependency skipped cleanly when unavailable (mirror the pattern at `instance-lifecycle.spec.js:24-41`).

---

## N. Walking order to actually ship this

1. **Stabilise the existing 7 spec files** (currently 9/16 tests green) — the in-flight edits already on disk address `submit`, `login.logout`, and the rate-limit issue. Remaining: `hint`, `instance-lifecycle` (3), `leaderboard` (1).
2. **Add the M.1 + M.2 + M.3 specs** — they cover the highest-traffic surfaces and would have caught the redact-scrub regression that broke `submit.spec.js` in the first place.
3. **Add the M.4 + M.5 + M.6 specs** — operator-facing surface.
4. **Add the M.7 specs** — realtime / WS regression canaries.
5. **Add the M.8 specs** — admin surface; these double as audit-log canaries.
6. **Add the M.9 + M.10 specs** — API-only and validator coverage (lives in backend tests, not Playwright).
7. **Add M.11** — per-challenge exercise.
8. **Land the test-handle gaps from §K** at the same time as the specs that need them (the smallest viable diffs to source).
