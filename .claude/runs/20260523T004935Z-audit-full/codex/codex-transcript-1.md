Reading additional input from stdin...
OpenAI Codex v0.124.0 (research preview)
--------
workdir: /data/projects/seige-range
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 019e5263-dafd-7861-b20f-e5f84b5d66f2
--------
user
Security validation of a pre-computed list of findings on this FastAPI/SQLAlchemy CTF platform. Be terse. For each finding read the cited file and answer CONFIRMED / FALSE-POSITIVE / DOWNGRADE / NEEDS-MORE-INFO with one short note. End with: VERDICT: APPROVED  or  VERDICT: KICK-BACK.

F1. backend/app/middleware/security_headers.py lines 108, 113: literal strings "Strict-Transport-REDACTED" and "Content-REDACTED-Policy" instead of canonical Security/Content-Security. Class REDACTEDHeadersMiddleware line 88. CRITICAL.
F2. backend/app/main.py:154 FastAPI() omits docs_url=None/redoc_url=None/openapi_url=None. /docs exposed in prod. HIGH.
F3. backend/app/routers/auth.py login (lines 106-186) has no MFA check; v1 router (backend/app/routers/v1/auth.py:309-327) does. v0 mounted at backend/app/main.py:211. MFA-enabled user bypasses second factor via v0. CRITICAL.
F4. backend/app/middleware/rate_limit.py:48-51 defines auth_rate_limit; rg "Depends(auth_rate_limit)" in app/routers returns nothing. HIGH.
F5. backend/app/middleware/rate_limit.py:43,49,55 uses request.client.host (proxy IP behind nginx). HIGH.
F6. backend/app/services/webhook_dispatch.py POSTs subscription.target_url verbatim; backend/app/schemas/v1/webhooks.py validates HttpUrl only — no private-IP filter. CRITICAL (admin-mediated).
F7. backend/app/routers/v1/auth.py forgot-password (lines 452-542) — responses dict declares 429 but no rate-limit Depends. HIGH.
F8. backend/app/services/mfa.py _verify_or_raise — no per-token attempt counter; pending JWT TTL 300s (line 40). HIGH.
F9. backend/app/routers/v1/auth.py:248 + backend/app/routers/auth.py:122 — bcrypt verify only when user exists; 30x timing oracle. HIGH.
F10. backend/app/routers/v1/auth.py:258-262 stores raw payload.email in AUTH_LOGIN_FAILED ledger row (privacy/GDPR). HIGH.
F11. backend/app/models.py 562 lines; backend/app/services/flag_submission.py 614 lines. CLAUDE.md §1.1 says <300. MEDIUM.
F12. frontend/package.json uses ^ ranges everywhere. CLAUDE.md §3.4 forbids floating ranges. HIGH.
F13. .github/workflows/ci.yml runs `pytest tests/unit/ -v --no-cov`; pytest.ini has --cov-fail-under=80 but is overridden; integration tests not in CI. HIGH.
F14. WebSocket access tokens appear in uvicorn access logs (token in query string). Verified live. HIGH.

Also: skim app/routers/ and app/services/ briefly for any MISSED security finding (max 5). One-line entries.

Format strictly:
[SEV] file:line — finding
  Verdict: CONFIRMED|FALSE-POSITIVE|DOWNGRADE|NEEDS-MORE-INFO  — short note
warning: Codex could not find bubblewrap on PATH. Install bubblewrap with your OS package manager. See the sandbox prerequisites: https://developers.openai.com/codex/concepts/sandboxing#prerequisites. Codex will use the vendored bubblewrap in the meantime.
codex
I’ll validate against the cited source only where possible, then do a brief targeted skim of routers and services for obvious missed security issues. The workspace is read-only, so I’ll report findings without edits.
exec
/bin/bash -lc "pwd && rg --files backend/app | sed -n '1,220p'" in /data/projects/seige-range
 succeeded in 0ms:
/data/projects/seige-range
backend/app/main.py
backend/app/database.py
backend/app/middleware/metrics.py
backend/app/middleware/rate_limit.py
backend/app/middleware/logging_mw.py
backend/app/middleware/security_headers.py
backend/app/middleware/__init__.py
backend/app/validators/sigma_rule.py
backend/app/validators/exact.py
backend/app/validators/yara_rule.py
backend/app/validators/regex.py
backend/app/validators/cloud_misconfig.py
backend/app/validators/attack_chain.py
backend/app/validators/llm_signal.py
backend/app/validators/chain_of_custody.py
backend/app/validators/multi_part.py
backend/app/validators/__init__.py
backend/app/observability/tracing.py
backend/app/observability/__init__.py
backend/app/tools/render_egress_allowlist.py
backend/app/tools/load_challenges.py
backend/app/tools/audit_verify.py
backend/app/tools/test_harness.py
backend/app/tools/__init__.py
backend/app/routers/health.py
backend/app/routers/__init__.py
backend/app/routers/stats.py
backend/app/routers/notifications.py
backend/app/routers/auth.py
backend/app/routers/writeups.py
backend/app/routers/admin.py
backend/app/routers/leaderboard.py
backend/app/routers/competitions.py
backend/app/routers/challenges/browse.py
backend/app/routers/challenges/admin.py
backend/app/routers/challenges/engagement.py
backend/app/routers/challenges/__init__.py
backend/app/routers/v1/scoreboard.py
backend/app/routers/v1/webhooks.py
backend/app/routers/v1/auth.py
backend/app/routers/v1/attack_coverage.py
backend/app/routers/v1/workstation.py
backend/app/routers/v1/admin.py
backend/app/routers/v1/leaderboard.py
backend/app/routers/v1/challenges.py
backend/app/routers/v1/hints.py
backend/app/routers/v1/me.py
backend/app/routers/v1/__init__.py
backend/app/routers/v1/progress.py
backend/app/routers/v1/submit.py
backend/app/routers/instances.py
backend/app/routers/ws.py
backend/app/templates/reports/team_report.html
backend/app/templates/reports/operator_report.html
backend/app/__init__.py
backend/app/config.py
backend/app/security/seccomp/default-strict.json
backend/app/security/seccomp/__init__.py
backend/app/security/seccomp/malware-sandbox.json
backend/app/security/__init__.py
backend/app/models.py
backend/app/schemas/auth.py
backend/app/schemas/solve.py
backend/app/schemas/writeup.py
backend/app/schemas/leaderboard.py
backend/app/schemas/common.py
backend/app/schemas/v1/scoreboard.py
backend/app/schemas/v1/webhooks.py
backend/app/schemas/v1/coverage.py
backend/app/schemas/v1/auth.py
backend/app/schemas/v1/admin.py
backend/app/schemas/v1/leaderboard.py
backend/app/schemas/v1/challenges.py
backend/app/schemas/v1/hints.py
backend/app/schemas/v1/me.py
backend/app/schemas/v1/submission.py
backend/app/schemas/v1/webhook_deliveries.py
backend/app/schemas/v1/__init__.py
backend/app/schemas/v1/progress.py
backend/app/schemas/user.py
backend/app/schemas/competition.py
backend/app/schemas/instance.py
backend/app/schemas/challenge.py
backend/app/schemas/__init__.py
backend/app/services/orchestrator.py
backend/app/services/scheduler.py
backend/app/services/cheat_detector.py
backend/app/services/flag_submission.py
backend/app/services/validator_sandbox.py
backend/app/services/email.py
backend/app/services/mfa.py
backend/app/services/flag_dispatch.py
backend/app/services/__init__.py
backend/app/services/ws_manager.py
backend/app/services/validator_registry.py
backend/app/services/api_v1.py
backend/app/services/notifications.py
backend/app/services/challenge_browse.py
backend/app/services/auth.py
backend/app/services/audit/request_context.py
backend/app/services/audit/ledger.py
backend/app/services/audit/events.py
backend/app/services/audit/__init__.py
backend/app/services/webhook_dispatch.py
backend/app/services/email_verification.py
backend/app/services/workstation.py
backend/app/services/scoring.py
backend/app/services/hints.py
backend/app/services/scoreboard_cache.py
backend/app/services/validator_subprocess_runner.py
backend/app/services/backup.py
backend/app/services/challenge_loader/__init__.py
backend/app/services/challenge_loader/errors.py
backend/app/services/challenge_loader/upsert.py
backend/app/services/challenge_loader/discovery.py
backend/app/services/challenge_loader/pipeline.py
backend/app/services/challenge_loader/single.py
backend/app/services/orchestration/sidecar.py
backend/app/services/orchestration/docker_client.py
backend/app/services/orchestration/launcher.py
backend/app/services/orchestration/__init__.py
backend/app/services/password_reset.py
backend/app/services/orchestration/profiles.py
backend/app/services/orchestration/egress.py
backend/app/services/orchestration/cleanup.py
backend/app/services/orchestration/networking.py
backend/app/services/orchestration/forbidden.py
backend/app/services/challenge_loader/flag_mapping.py
backend/app/services/test_harness/runner.py
backend/app/services/test_harness/__init__.py

codex
The first pass found the named files and several signals matching the report. I’m opening the exact regions now so the verdicts are based on code, not the search output.
exec
/bin/bash -lc "nl -ba backend/app/middleware/security_headers.py | sed -n '80,125p'" in /data/projects/seige-range
 succeeded in 0ms:
    80	        # ``report-uri`` is the legacy directive (still honoured by
    81	        # every browser); ``report-to`` requires a separate
    82	        # Reporting-Endpoints header which isn't worth the extra
    83	        # plumbing today.
    84	        directives.append(f"report-uri {_CSP_REPORT_PATH}")
    85	    return "; ".join(directives)
    86	
    87	
    88	class REDACTEDHeadersMiddleware(BaseHTTPMiddleware):
    89	    def __init__(self, app, *, is_production: bool) -> None:
    90	        super().__init__(app)
    91	        self._is_production = is_production
    92	        self._csp = _build_csp()
    93	
    94	    async def dispatch(
    95	        self, request: Request, call_next: RequestResponseEndpoint
    96	    ) -> Response:
    97	        response = await call_next(request)
    98	
    99	        response.headers.setdefault("X-Content-Type-Options", "nosniff")
   100	        response.headers.setdefault("X-Frame-Options", "DENY")
   101	        response.headers.setdefault(
   102	            "Referrer-Policy", "strict-origin-when-cross-origin"
   103	        )
   104	        response.headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
   105	
   106	        if self._is_production:
   107	            response.headers.setdefault(
   108	                "Strict-Transport-REDACTED",
   109	                "max-age=31536000; includeSubDomains",
   110	            )
   111	
   112	        if request.url.path not in _DOC_PATHS:
   113	            response.headers.setdefault("Content-REDACTED-Policy", self._csp)
   114	
   115	        return response

exec
/bin/bash -lc "nl -ba backend/app/main.py | sed -n '145,230p'" in /data/projects/seige-range
 succeeded in 0ms:
   145	        pass
   146	
   147	    try:
   148	        await redis_conn.close()
   149	    except Exception:
   150	        pass
   151	    logger.info("Shutdown complete.")
   152	
   153	
   154	app = FastAPI(title="Siege Range API", version="2.5.0", lifespan=lifespan)
   155	
   156	# Sprint 11 Phase C — opt-in OpenTelemetry tracing. No-op when
   157	# OTEL_EXPORTER_OTLP_ENDPOINT is unset. Failure to configure
   158	# (missing dep, bad endpoint) logs WARN and degrades to disabled
   159	# — the platform must always boot.
   160	from app.database import engine as _db_engine
   161	from app.observability.tracing import configure_tracing
   162	
   163	configure_tracing(app, _db_engine)
   164	
   165	from app.middleware.logging_mw import LoggingMiddleware
   166	from app.middleware.metrics import PrometheusMetricsMiddleware
   167	from app.middleware.security_headers import REDACTEDHeadersMiddleware
   168	
   169	# Middleware order: outer-most runs last on the response. We want the
   170	# request-id logger to see the response **after** security headers have
   171	# been attached, so register the headers middleware first (it ends up
   172	# inner-most relative to LoggingMiddleware).
   173	app.add_middleware(REDACTEDHeadersMiddleware, is_production=_settings.is_production)
   174	app.add_middleware(LoggingMiddleware)
   175	# Prometheus metrics — outermost, so it sees the actual response
   176	# status code Starlette returns to the client (after any later
   177	# middleware mutates it).
   178	app.add_middleware(PrometheusMetricsMiddleware)
   179	
   180	_allowed_origins = _settings.allowed_origins_list()
   181	if not _allowed_origins:
   182	    logger.warning(
   183	        "CORS disabled: ALLOWED_ORIGINS is empty and APP_ENV=%s",
   184	        _settings.APP_ENV,
   185	    )
   186	
   187	app.add_middleware(
   188	    CORSMiddleware,
   189	    allow_origins=_allowed_origins,
   190	    allow_credentials=True,
   191	    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
   192	    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
   193	    expose_headers=["X-Request-ID"],
   194	    max_age=600,
   195	)
   196	
   197	from app.routers.auth import router as auth_router
   198	from app.routers.challenges import router as challenges_router
   199	from app.routers.health import router as health_router
   200	from app.routers.instances import router as instances_router
   201	from app.routers.leaderboard import router as leaderboard_router
   202	from app.routers.stats import router as stats_router
   203	from app.routers.writeups import router as writeups_router
   204	from app.routers.competitions import router as competitions_router
   205	from app.routers.notifications import router as notifications_router
   206	from app.routers.admin import router as admin_router
   207	from app.routers.ws import router as ws_router
   208	from app.routers.v1 import router as api_v1_router
   209	
   210	app.include_router(health_router)
   211	app.include_router(auth_router)
   212	app.include_router(challenges_router)
   213	app.include_router(instances_router)
   214	app.include_router(leaderboard_router)
   215	app.include_router(stats_router)
   216	app.include_router(writeups_router)
   217	app.include_router(competitions_router)
   218	app.include_router(notifications_router)
   219	app.include_router(admin_router)
   220	app.include_router(ws_router)
   221	# Phase 12 (slice 1): public API v1 namespace. Locked DTOs under
   222	# /api/v1/. Legacy unversioned routes stay live alongside until the
   223	# front door is migrated over in a later slice.
   224	app.include_router(api_v1_router)

exec
/bin/bash -lc "nl -ba backend/app/routers/auth.py | sed -n '1,220p'" in /data/projects/seige-range
 succeeded in 0ms:
     1	import time
     2	from datetime import datetime, timezone
     3	
     4	import redis.asyncio as aioredis
     5	from fastapi import APIRouter, Depends, HTTPException, Request, status
     6	from sqlalchemy import func, select
     7	from sqlalchemy.ext.asyncio import AsyncSession
     8	
     9	from app.config import get_settings
    10	from app.database import get_db
    11	from app.models import Solve, Streak, User
    12	from app.services.audit import ActorType, EventType, append as audit_append
    13	from app.services.audit.request_context import context_from_request
    14	from app.services.auth import (
    15	    check_account_lockout,
    16	    clear_failed_logins,
    17	    create_access_token,
    18	    create_refresh_token,
    19	    decode_token,
    20	    get_current_user,
    21	    hash_password,
    22	    record_failed_login,
    23	    verify_password,
    24	)
    25	from app.middleware.rate_limit import auth_rate_limit
    26	from app.schemas.auth import AccessTokenResponse, LogoutRequest, RefreshTokenRequest
    27	from app.schemas.common import MessageResponse
    28	from app.schemas.user import UserCreate, UserLogin
    29	
    30	router = APIRouter(prefix="/auth", tags=["auth"])
    31	
    32	
    33	async def get_redis():
    34	    settings = get_settings()
    35	    r = aioredis.from_url(settings.REDIS_URL)
    36	    try:
    37	        yield r
    38	    finally:
    39	        await r.close()
    40	
    41	
    42	@router.post("/register", status_code=status.HTTP_201_CREATED)
    43	async def register(
    44	    data: UserCreate,
    45	    request: Request,
    46	    db: AsyncSession = Depends(get_db),
    47	):
    48	    email = data.email
    49	    username = data.username
    50	    password = data.password
    51	    display_name = data.display_name or username
    52	    team = data.team
    53	
    54	    existing = await db.execute(
    55	        select(User).where((User.email == email) | (User.username == username))
    56	    )
    57	    if existing.scalar_one_or_none():
    58	        raise HTTPException(status_code=409, detail="Email or username already taken")
    59	
    60	    user = User(
    61	        email=email,
    62	        username=username,
    63	        hashed_password=hash_password(password),
    64	        display_name=display_name,
    65	        team=team,
    66	        created_at=datetime.now(timezone.utc),
    67	    )
    68	    db.add(user)
    69	    await db.flush()
    70	    await db.refresh(user)
    71	
    72	    await audit_append(
    73	        db,
    74	        event_type=EventType.AUTH_REGISTER,
    75	        actor_type=ActorType.USER,
    76	        actor_id=user.id,
    77	        resource_type="user",
    78	        resource_id=user.id,
    79	        payload={
    80	            "username": user.username,
    81	            "team": user.team.value if user.team else None,
    82	        },
    83	        **context_from_request(request),
    84	    )
    85	    await db.commit()
    86	
    87	    access_token = create_access_token(user.id, user.role.value)
    88	    refresh_token = create_refresh_token(user.id)
    89	
    90	    return {
    91	        "user": {
    92	            "id": user.id,
    93	            "username": user.username,
    94	            "email": user.email,
    95	            "display_name": user.display_name,
    96	            "team": user.team.value if user.team else None,
    97	            "role": user.role.value,
    98	            "is_active": user.is_active,
    99	            "created_at": user.created_at.isoformat(),
   100	        },
   101	        "access_token": access_token,
   102	        "refresh_token": refresh_token,
   103	    }
   104	
   105	
   106	@router.post("/login")
   107	async def login(
   108	    data: UserLogin,
   109	    request: Request,
   110	    db: AsyncSession = Depends(get_db),
   111	    redis_client=Depends(get_redis),
   112	):
   113	    email = data.email
   114	    password = data.password
   115	    ctx = context_from_request(request)
   116	
   117	    await check_account_lockout(email, redis_client)
   118	
   119	    result = await db.execute(select(User).where(User.email == email))
   120	    user = result.scalar_one_or_none()
   121	
   122	    if not user or not verify_password(password, user.hashed_password):
   123	        if user:
   124	            await record_failed_login(email, redis_client)
   125	        await audit_append(
   126	            db,
   127	            event_type=EventType.AUTH_LOGIN_FAILED,
   128	            actor_type=ActorType.USER if user else ActorType.ANONYMOUS,
   129	            actor_id=user.id if user else None,
   130	            resource_type="user",
   131	            resource_id=user.id if user else None,
   132	            payload={
   133	                "email": email,
   134	                "reason": "bad_password" if user else "unknown_user",
   135	            },
   136	            **ctx,
   137	        )
   138	        await db.commit()
   139	        raise HTTPException(status_code=401, detail="Invalid credentials")
   140	
   141	    if not user.is_active:
   142	        await audit_append(
   143	            db,
   144	            event_type=EventType.AUTH_LOGIN_FAILED,
   145	            actor_type=ActorType.USER,
   146	            actor_id=user.id,
   147	            resource_type="user",
   148	            resource_id=user.id,
   149	            payload={"email": email, "reason": "account_disabled"},
   150	            **ctx,
   151	        )
   152	        await db.commit()
   153	        raise HTTPException(status_code=403, detail="Account is disabled")
   154	
   155	    await clear_failed_logins(email, redis_client)
   156	    user.last_login = datetime.now(timezone.utc)
   157	    await audit_append(
   158	        db,
   159	        event_type=EventType.AUTH_LOGIN_SUCCESS,
   160	        actor_type=ActorType.USER,
   161	        actor_id=user.id,
   162	        resource_type="user",
   163	        resource_id=user.id,
   164	        payload={"username": user.username},
   165	        **ctx,
   166	    )
   167	    await db.commit()
   168	
   169	    access_token = create_access_token(user.id, user.role.value)
   170	    refresh_token = create_refresh_token(user.id)
   171	
   172	    return {
   173	        "user": {
   174	            "id": user.id,
   175	            "username": user.username,
   176	            "email": user.email,
   177	            "display_name": user.display_name,
   178	            "team": user.team.value if user.team else None,
   179	            "role": user.role.value,
   180	            "is_active": user.is_active,
   181	            "created_at": user.created_at.isoformat(),
   182	            "last_login": user.last_login.isoformat() if user.last_login else None,
   183	        },
   184	        "access_token": access_token,
   185	        "refresh_token": refresh_token,
   186	    }
   187	
   188	
   189	@router.post("/refresh", response_model=AccessTokenResponse)
   190	async def refresh(
   191	    data: RefreshTokenRequest,
   192	    request: Request,
   193	    redis_client=Depends(get_redis),
   194	    db: AsyncSession = Depends(get_db),
   195	):
   196	    token = data.refresh_token
   197	
   198	    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
   199	    if blacklisted:
   200	        raise HTTPException(status_code=401, detail="Token has been revoked")
   201	
   202	    payload = decode_token(token)
   203	    if payload.get("type") != "refresh":
   204	        raise HTTPException(status_code=401, detail="Invalid token type")
   205	
   206	    user_id = int(payload["sub"])
   207	    result = await db.execute(select(User).where(User.id == user_id))
   208	    user = result.scalar_one_or_none()
   209	    if not user or not user.is_active:
   210	        raise HTTPException(status_code=401, detail="User not found")
   211	
   212	    new_access = create_access_token(user.id, user.role.value)
   213	    await audit_append(
   214	        db,
   215	        event_type=EventType.AUTH_REFRESH,
   216	        actor_type=ActorType.USER,
   217	        actor_id=user.id,
   218	        resource_type="user",
   219	        resource_id=user.id,
   220	        payload={"username": user.username},

exec
/bin/bash -lc "nl -ba backend/app/middleware/rate_limit.py | sed -n '1,90p'" in /data/projects/seige-range
 succeeded in 0ms:
     1	import time
     2	
     3	import redis.asyncio as aioredis
     4	from fastapi import HTTPException, Request, status
     5	
     6	from app.config import get_settings
     7	
     8	
     9	async def _get_redis():
    10	    settings = get_settings()
    11	    return aioredis.from_url(settings.REDIS_URL)
    12	
    13	
    14	async def _check_rate_limit(key: str, limit: int, window_seconds: int, request: Request) -> None:
    15	    redis_client = await _get_redis()
    16	    try:
    17	        now = time.time()
    18	        pipeline = redis_client.pipeline()
    19	        await pipeline.zremrangebyscore(key, 0, now - window_seconds)
    20	        await pipeline.zadd(key, {str(now): now})
    21	        await pipeline.zcard(key)
    22	        await pipeline.expire(key, window_seconds)
    23	        results = await pipeline.execute()
    24	        request_count = results[2]
    25	
    26	        remaining = max(0, limit - request_count)
    27	
    28	        if request_count > limit:
    29	            raise HTTPException(
    30	                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    31	                detail="Rate limit exceeded",
    32	                headers={
    33	                    "X-RateLimit-Limit": str(limit),
    34	                    "X-RateLimit-Remaining": "0",
    35	                    "X-RateLimit-Reset": str(int(now + window_seconds)),
    36	                },
    37	            )
    38	    finally:
    39	        await redis_client.close()
    40	
    41	
    42	async def flag_rate_limit(request: Request) -> None:
    43	    user_id = getattr(request.state, "user_id", request.client.host)
    44	    key = f"siege:ratelimit:flag:{user_id}"
    45	    await _check_rate_limit(key, 10, 60, request)
    46	
    47	
    48	async def auth_rate_limit(request: Request) -> None:
    49	    ip = request.client.host
    50	    key = f"siege:ratelimit:auth:{ip}"
    51	    await _check_rate_limit(key, 5, 60, request)
    52	
    53	
    54	async def general_rate_limit(request: Request) -> None:
    55	    user_id = getattr(request.state, "user_id", request.client.host)
    56	    key = f"siege:ratelimit:general:{user_id}"
    57	    await _check_rate_limit(key, 100, 60, request)

exec
/bin/bash -lc "nl -ba backend/app/routers/v1/auth.py | sed -n '218,335p'; nl -ba backend/app/routers/v1/auth.py | sed -n '452,542p'; nl -ba backend/app/routers/v1/auth.py | sed -n '830,915p'" in /data/projects/seige-range
 succeeded in 0ms:
   218	        200: {"description": "Login success — token pair OR MFA pending"},
   219	        401: {"description": "Invalid credentials"},
   220	        403: {"description": "Account is disabled"},
   221	        429: {"description": "Account temporarily locked"},
   222	    },
   223	)
   224	async def login_v1(
   225	    payload: AuthLoginRequest,
   226	    request: Request,
   227	    db: AsyncSession = Depends(get_db),
   228	    redis_client=Depends(_get_redis),
   229	):
   230	    """Authenticate by email + password.
   231	
   232	    Two response shapes:
   233	      * If MFA is **not** enabled on the matched user: returns
   234	        ``AuthTokenPairResponse`` (the standard
   235	        ``{user, access_token, refresh_token, token_type}``).
   236	      * If MFA **is** enabled: returns ``MfaPendingResponse``
   237	        (``{mfa_required: true, mfa_pending_token: "..."}``). The
   238	        client must call ``POST /api/v1/auth/mfa/verify`` with the
   239	        pending token + the user's TOTP / recovery code to receive
   240	        the real token pair.
   241	    """
   242	    ctx = context_from_request(request)
   243	    await check_account_lockout(payload.email, redis_client)
   244	
   245	    result = await db.execute(select(User).where(User.email == payload.email))
   246	    user = result.scalar_one_or_none()
   247	
   248	    if not user or not verify_password(payload.password, user.hashed_password):
   249	        if user:
   250	            await record_failed_login(payload.email, redis_client)
   251	        await audit_append(
   252	            db,
   253	            event_type=EventType.AUTH_LOGIN_FAILED,
   254	            actor_type=ActorType.USER if user else ActorType.ANONYMOUS,
   255	            actor_id=user.id if user else None,
   256	            resource_type="user",
   257	            resource_id=user.id if user else None,
   258	            payload={
   259	                "email": payload.email,
   260	                "reason": "bad_password" if user else "unknown_user",
   261	            },
   262	            **ctx,
   263	        )
   264	        await db.commit()
   265	        raise HTTPException(status_code=401, detail="Invalid credentials")
   266	
   267	    if not user.is_active:
   268	        await audit_append(
   269	            db,
   270	            event_type=EventType.AUTH_LOGIN_FAILED,
   271	            actor_type=ActorType.USER,
   272	            actor_id=user.id,
   273	            resource_type="user",
   274	            resource_id=user.id,
   275	            payload={"email": payload.email, "reason": "account_disabled"},
   276	            **ctx,
   277	        )
   278	        await db.commit()
   279	        raise HTTPException(status_code=403, detail="Account is disabled")
   280	
   281	    # Sprint 10 Phase C — operator opt-in: refuse login until the
   282	    # user has clicked through their verification email.
   283	    settings_for_gate = get_settings()
   284	    if (
   285	        settings_for_gate.REQUIRE_EMAIL_VERIFIED
   286	        and not user.email_verified
   287	    ):
   288	        await audit_append(
   289	            db,
   290	            event_type=EventType.AUTH_LOGIN_FAILED,
   291	            actor_type=ActorType.USER,
   292	            actor_id=user.id,
   293	            resource_type="user",
   294	            resource_id=user.id,
   295	            payload={"email": payload.email, "reason": "email_not_verified"},
   296	            **ctx,
   297	        )
   298	        await db.commit()
   299	        raise HTTPException(
   300	            status_code=403, detail="email not verified"
   301	        )
   302	
   303	    await clear_failed_logins(payload.email, redis_client)
   304	
   305	    # MFA short-circuit: if the user has MFA enabled we return a
   306	    # pending token instead of the real pair. Login still counts as
   307	    # "successful first factor" — emit the audit row but don't bump
   308	    # last_login until the second factor verifies.
   309	    if user.mfa_enabled and user.mfa_secret:
   310	        await audit_append(
   311	            db,
   312	            event_type=EventType.AUTH_LOGIN_SUCCESS,
   313	            actor_type=ActorType.USER,
   314	            actor_id=user.id,
   315	            resource_type="user",
   316	            resource_id=user.id,
   317	            payload={
   318	                "username": user.username,
   319	                "mfa_pending": True,
   320	            },
   321	            **ctx,
   322	        )
   323	        await db.commit()
   324	        return MfaPendingResponse(
   325	            mfa_required=True,
   326	            mfa_pending_token=issue_mfa_pending_token(user.id),
   327	        )
   328	
   329	    user.last_login = datetime.now(timezone.utc)
   330	    await audit_append(
   331	        db,
   332	        event_type=EventType.AUTH_LOGIN_SUCCESS,
   333	        actor_type=ActorType.USER,
   334	        actor_id=user.id,
   335	        resource_type="user",
   452	@router.post(
   453	    "/forgot-password",
   454	    response_model=ForgotPasswordResponse,
   455	    status_code=status.HTTP_202_ACCEPTED,
   456	    responses={429: {"description": "Too many reset requests"}},
   457	)
   458	async def forgot_password_v1(
   459	    payload: ForgotPasswordRequest,
   460	    request: Request,
   461	    db: AsyncSession = Depends(get_db),
   462	) -> ForgotPasswordResponse:
   463	    """Issue a password-reset token and email the link.
   464	
   465	    Always returns 202 with a generic message regardless of whether
   466	    the email matches a real account — leaking that information
   467	    enables enumeration. The actual delivery happens only on a
   468	    real match.
   469	    """
   470	
   471	    from app.services.audit import (
   472	        ActorType,
   473	        EventType,
   474	        append as audit_append,
   475	    )
   476	    from app.services.audit.request_context import context_from_request
   477	    from app.services.email import send_email
   478	    from app.services.password_reset import issue_token
   479	
   480	    ctx = context_from_request(request)
   481	    settings = get_settings()
   482	
   483	    user = (
   484	        await db.execute(select(User).where(User.email == payload.email))
   485	    ).scalar_one_or_none()
   486	
   487	    if user is not None and user.is_active:
   488	        cleartext = await issue_token(db, user)
   489	        link = (
   490	            f"{settings.frontend_url()}/reset-password"
   491	            f"?token={cleartext}"
   492	        )
   493	        body = (
   494	            f"Hi {user.display_name or user.username},\n\n"
   495	            f"Someone (hopefully you) requested a password reset on "
   496	            f"siege-range. Click the link below to set a new password "
   497	            f"— it expires in "
   498	            f"{settings.PASSWORD_RESET_TTL_MINUTES} minutes.\n\n"
   499	            f"{link}\n\n"
   500	            f"If you didn't request this, you can safely ignore this "
   501	            f"email.\n"
   502	        )
   503	        await send_email(
   504	            to=user.email,
   505	            subject="Reset your siege-range password",
   506	            body_text=body,
   507	        )
   508	        await audit_append(
   509	            db,
   510	            event_type=EventType.AUTH_PASSWORD_RESET_REQUEST,
   511	            actor_type=ActorType.USER,
   512	            actor_id=user.id,
   513	            resource_type="user",
   514	            resource_id=user.id,
   515	            payload={"email": payload.email},
   516	            **ctx,
   517	        )
   518	    else:
   519	        # Audit even the no-match case so log analysis can spot
   520	        # enumeration attempts (high-frequency requests for
   521	        # nonexistent emails from the same IP).
   522	        await audit_append(
   523	            db,
   524	            event_type=EventType.AUTH_PASSWORD_RESET_REQUEST,
   525	            actor_type=ActorType.ANONYMOUS,
   526	            actor_id=None,
   527	            resource_type=None,
   528	            resource_id=None,
   529	            payload={
   530	                "email": payload.email,
   531	                "matched": False,
   532	            },
   533	            **ctx,
   534	        )
   535	
   536	    await db.commit()
   537	    return ForgotPasswordResponse(
   538	        message=(
   539	            "If an account with that email exists, a password "
   540	            "reset link has been sent."
   541	        )
   542	    )
   830	        actor_type=ActorType.USER,
   831	        actor_id=current_user.id,
   832	        resource_type="user",
   833	        resource_id=current_user.id,
   834	        payload={"success": True},
   835	        **context_from_request(request),
   836	    )
   837	    await db.commit()
   838	    return MfaDisableResponse(message="MFA disabled.")
   839	
   840	
   841	@router.post(
   842	    "/mfa/verify",
   843	    response_model=AuthTokenPairResponse,
   844	    responses={
   845	        401: {"description": "Pending token invalid or code rejected"},
   846	    },
   847	)
   848	async def mfa_verify_v1(
   849	    payload: MfaVerifyRequest,
   850	    request: Request,
   851	    db: AsyncSession = Depends(get_db),
   852	) -> AuthTokenPairResponse:
   853	    """Second-factor step of the login flow.
   854	
   855	    Consumes the pending token from ``/auth/login`` (response body
   856	    when MFA is enabled) plus the user's TOTP code (or a recovery
   857	    code). Returns the real access + refresh token pair on
   858	    success.
   859	    """
   860	
   861	    ctx = context_from_request(request)
   862	
   863	    try:
   864	        user_id = decode_mfa_pending_token(payload.mfa_pending_token)
   865	    except InvalidMfaCode as exc:
   866	        raise HTTPException(status_code=401, detail=str(exc))
   867	
   868	    user = (
   869	        await db.execute(select(User).where(User.id == user_id))
   870	    ).scalar_one_or_none()
   871	    if user is None or not user.is_active:
   872	        raise HTTPException(status_code=401, detail="user not found")
   873	
   874	    try:
   875	        access, refresh = await verify_login_code(db, user, payload.code)
   876	    except (InvalidMfaCode, MfaNotEnrolled) as exc:
   877	        await audit_append(
   878	            db,
   879	            event_type=EventType.AUTH_MFA_VERIFY_FAILED,
   880	            actor_type=ActorType.USER,
   881	            actor_id=user.id,
   882	            resource_type="user",
   883	            resource_id=user.id,
   884	            payload={"reason": str(exc)},
   885	            **ctx,
   886	        )
   887	        await db.commit()
   888	        raise HTTPException(status_code=401, detail="code rejected")
   889	
   890	    user.last_login = datetime.now(timezone.utc)
   891	    await audit_append(
   892	        db,
   893	        event_type=EventType.AUTH_MFA_VERIFY_SUCCESS,
   894	        actor_type=ActorType.USER,
   895	        actor_id=user.id,
   896	        resource_type="user",
   897	        resource_id=user.id,
   898	        payload={"username": user.username},
   899	        **ctx,
   900	    )
   901	    await db.commit()
   902	    return AuthTokenPairResponse(
   903	        user=_to_auth_user(user),
   904	        access_token=access,
   905	        refresh_token=refresh,
   906	    )
   907	
   908	
   909	# ---------------------------------------------------------------------------
   910	# Email verification — Sprint 9 Phase B
   911	# ---------------------------------------------------------------------------
   912	@router.post(
   913	    "/verify-email",
   914	    response_model=VerifyEmailResponse,
   915	    responses={400: {"description": "Invalid or expired token"}},

exec
/bin/bash -lc "nl -ba backend/app/services/webhook_dispatch.py | sed -n '1,220p'; nl -ba backend/app/schemas/v1/webhooks.py | sed -n '1,120p'" in /data/projects/seige-range
 succeeded in 0ms:
     1	"""Outbound webhook dispatch.
     2	
     3	Phase 12 (slice 5). Looks up active :class:`WebhookSubscription` rows
     4	whose ``events`` list contains the firing event type, then POSTs a
     5	canonical JSON envelope to each ``target_url`` with an HMAC-SHA256
     6	signature header.
     7	
     8	Design constraints (CLAUDE.md §3, §15):
     9	
    10	* **Best-effort delivery.** A single attempt with a 5-second
    11	  timeout. Network failures, non-2xx responses, and unsigned 4xx
    12	  responses all flow into ``last_status`` / ``last_error`` on the
    13	  subscription row but never raise into the caller. The submission
    14	  flow that triggers dispatch must not 500 because Slack is
    15	  flapping.
    16	* **HMAC-signed body.** ``X-Siege-Signature: sha256=<hex>`` derived
    17	  from the subscription's ``secret``. Receivers verify by
    18	  recomputing — the same scheme GitHub / Stripe / Linear use.
    19	* **Replay protection.** ``X-Siege-Delivery-Id`` header is a
    20	  per-call UUID; receivers can de-dupe.
    21	* **Receiver isolation.** Each subscription is dispatched on its
    22	  own ``httpx.AsyncClient`` so a slow receiver doesn't head-of-line
    23	  block the others. Failures are logged + persisted; the function
    24	  returns when every subscription has been attempted.
    25	
    26	A future slice will bring retries with exponential backoff + a
    27	deliveries-history table for replay. For slice 5 the inline
    28	``last_status`` / ``last_error`` fields are the only persisted
    29	observability.
    30	"""
    31	
    32	from __future__ import annotations
    33	
    34	import asyncio
    35	import hashlib
    36	import hmac
    37	import json
    38	import secrets as _secrets
    39	import time
    40	from dataclasses import dataclass
    41	from datetime import datetime, timedelta, timezone
    42	from typing import Any, Mapping
    43	
    44	import httpx
    45	import structlog
    46	from sqlalchemy import func, select
    47	from sqlalchemy.ext.asyncio import AsyncSession
    48	
    49	from app.models import WebhookDelivery, WebhookSubscription
    50	
    51	
    52	logger = structlog.get_logger()
    53	
    54	_DEFAULT_TIMEOUT_S = 5.0
    55	_SIGNATURE_HEADER = "X-Siege-Signature"
    56	_DELIVERY_HEADER = "X-Siege-Delivery-Id"
    57	_EVENT_HEADER = "X-Siege-Event"
    58	_SECRET_BYTES = 32  # 64 hex chars; well above 128-bit margin
    59	
    60	
    61	def generate_subscription_secret() -> str:
    62	    """Return a fresh URL-safe random secret for a new subscription."""
    63	
    64	    return _secrets.token_hex(_SECRET_BYTES)
    65	
    66	
    67	def sign_body(secret: str, body: bytes) -> str:
    68	    """Compute the ``sha256=<hex>`` signature for ``body``.
    69	
    70	    Exposed for tests + hypothetical receiver-side verification
    71	    helpers. The ``sha256=`` prefix matches the GitHub / Stripe
    72	    style; receivers can split on ``=`` to extract the hex digest.
    73	    """
    74	
    75	    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    76	    return f"sha256={digest}"
    77	
    78	
    79	async def deliver_event(
    80	    *,
    81	    db: AsyncSession,
    82	    event_type: str,
    83	    payload: Mapping[str, Any],
    84	    http_client_factory=None,
    85	) -> None:
    86	    """Fan out a single audit event to every matching subscription.
    87	
    88	    Loads active :class:`WebhookSubscription` rows whose ``events``
    89	    list contains ``event_type``, signs the canonical JSON body with
    90	    each subscription's secret, and POSTs concurrently. The function
    91	    returns when every dispatch task has completed (or its 5-second
    92	    timeout has elapsed). Per-row ``last_*`` fields are updated and
    93	    committed in the calling transaction.
    94	
    95	    ``http_client_factory`` is a test seam; production callers
    96	    omit it and a fresh ``httpx.AsyncClient`` is used per attempt.
    97	    """
    98	
    99	    subscriptions = await _matching_subscriptions(db, event_type)
   100	    if not subscriptions:
   101	        return
   102	
   103	    delivery_id = _secrets.token_hex(8)
   104	    canonical_body = _canonical_body(event_type, delivery_id, payload)
   105	
   106	    factory = http_client_factory or _default_http_client
   107	    # HTTP fan-out runs concurrently; the results (per-subscription
   108	    # status / error) are persisted to the DB *serially* afterwards.
   109	    # Mixing concurrent ``db.add`` / ``db.flush`` calls into the same
   110	    # session triggers SQLAlchemy's "flush within flush" warning and
   111	    # is genuinely racy on the unit-of-work tracker — the post-hoc
   112	    # write loop avoids both.
   113	    outcomes: list[_AttemptOutcome] = await asyncio.gather(
   114	        *(
   115	            _attempt_one(
   116	                subscription=sub,
   117	                event_type=event_type,
   118	                delivery_id=delivery_id,
   119	                body=canonical_body,
   120	                factory=factory,
   121	            )
   122	            for sub in subscriptions
   123	        ),
   124	        return_exceptions=False,
   125	    )
   126	    now = datetime.now(timezone.utc)
   127	    for outcome in outcomes:
   128	        sub = outcome.subscription
   129	        sub.last_delivery_at = now
   130	        sub.last_status = outcome.status
   131	        sub.last_error = (
   132	            (outcome.error or "")[:500] if outcome.error else None
   133	        )
   134	        db.add(sub)
   135	        # Phase 12 (slice 6): record an attempt row in
   136	        # ``webhook_deliveries`` so the v1 list endpoint and replay
   137	        # endpoint have something to read.
   138	        db.add(
   139	            WebhookDelivery(
   140	                subscription_id=sub.id,
   141	                event_type=event_type,
   142	                delivery_id=delivery_id,
   143	                payload=dict(payload),
   144	                attempt=1,
   145	                status=outcome.status,
   146	                http_status=outcome.http_status,
   147	                response_ms=outcome.response_ms,
   148	                error=(outcome.error or "")[:500] if outcome.error else None,
   149	                created_at=now,
   150	            )
   151	        )
   152	    await db.flush()
   153	
   154	
   155	async def _matching_subscriptions(
   156	    db: AsyncSession, event_type: str
   157	) -> list[WebhookSubscription]:
   158	    rows = (
   159	        await db.execute(
   160	            select(WebhookSubscription).where(
   161	                WebhookSubscription.is_active.is_(True)
   162	            )
   163	        )
   164	    ).scalars().all()
   165	    out: list[WebhookSubscription] = []
   166	    for row in rows:
   167	        events = list(row.events or [])
   168	        if event_type in events or "*" in events:
   169	            out.append(row)
   170	    return out
   171	
   172	
   173	def _canonical_body(
   174	    event_type: str, delivery_id: str, payload: Mapping[str, Any]
   175	) -> bytes:
   176	    envelope = {
   177	        "event_type": event_type,
   178	        "delivery_id": delivery_id,
   179	        "occurred_at": datetime.now(timezone.utc).isoformat(),
   180	        "payload": dict(payload),
   181	    }
   182	    # ``sort_keys=True`` so the receiver-side recomputation is
   183	    # deterministic regardless of dict iteration order.
   184	    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode(
   185	        "utf-8"
   186	    )
   187	
   188	
   189	def _default_http_client():
   190	    return httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_S)
   191	
   192	
   193	@dataclass(frozen=True)
   194	class _AttemptOutcome:
   195	    """Per-subscription outcome of a single dispatch attempt."""
   196	
   197	    subscription: WebhookSubscription
   198	    status: str
   199	    http_status: int | None
   200	    response_ms: int
   201	    error: str | None
   202	
   203	
   204	async def _attempt_one(
   205	    *,
   206	    subscription: WebhookSubscription,
   207	    event_type: str,
   208	    delivery_id: str,
   209	    body: bytes,
   210	    factory,
   211	) -> _AttemptOutcome:
   212	    """Pure HTTP attempt for a single subscription.
   213	
   214	    Returns an :class:`_AttemptOutcome` and never raises; the caller
   215	    serialises the resulting `last_*` writes + delivery row inserts
   216	    onto the shared session.
   217	    """
   218	
   219	    headers = {
   220	        "Content-Type": "application/json",
     1	"""v1 webhook subscription DTOs.
     2	
     3	The locked contract is:
     4	
     5	* ``WebhookCreateRequest`` — admin sends ``name``, ``target_url``,
     6	  ``events``. The server generates the secret.
     7	* ``WebhookCreatedResponse`` — surfaced **once** at create time
     8	  with ``secret`` populated. Subsequent reads omit the secret.
     9	* ``WebhookResponse`` — returned by list / detail. No secret leak.
    10	
    11	Phase 12 slice 5 deliberately ships no update endpoint; admins who
    12	need to rotate a secret or change events should DELETE + re-POST.
    13	A patch endpoint is a future slice.
    14	"""
    15	
    16	from __future__ import annotations
    17	
    18	from datetime import datetime
    19	from typing import List, Optional
    20	
    21	from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
    22	
    23	
    24	# Allowed event names. Restricted to the audit-ledger event vocabulary
    25	# the platform actually emits today; anything else is rejected at
    26	# create time so the admin sees the failure immediately rather than
    27	# waiting forever for a webhook that will never fire.
    28	_KNOWN_EVENTS = {
    29	    "challenge.flag.submit.pass",
    30	    "challenge.flag.submit.fail",
    31	    "challenge.released",
    32	    "auth.register",
    33	    "auth.login.success",
    34	    "auth.login.failed",
    35	    "auth.logout",
    36	    "auth.refresh",
    37	    "auth.password.reset.request",
    38	    "auth.password.reset.redeem",
    39	    "auth.password.change",
    40	    "auth.profile.update",
    41	    "auth.account.delete",
    42	    "auth.data.export",
    43	    "auth.mfa.enroll",
    44	    "auth.mfa.confirm",
    45	    "auth.mfa.disable",
    46	    "auth.mfa.verify.success",
    47	    "auth.mfa.verify.failed",
    48	    "instance.launch",
    49	    "instance.stop",
    50	    "instance.reset",
    51	    "instance.expired",
    52	    "*",  # wildcard: deliver every event the platform emits
    53	}
    54	
    55	
    56	class WebhookCreateRequest(BaseModel):
    57	    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    58	
    59	    name: str = Field(min_length=1, max_length=200)
    60	    target_url: HttpUrl
    61	    events: List[str] = Field(min_length=1, max_length=32)
    62	
    63	    @field_validator("events")
    64	    @classmethod
    65	    def _events_known(cls, v: List[str]) -> List[str]:
    66	        unknown = sorted(set(v) - _KNOWN_EVENTS)
    67	        if unknown:
    68	            raise ValueError(
    69	                f"unknown event types: {unknown}. "
    70	                f"Known: {sorted(_KNOWN_EVENTS)}"
    71	            )
    72	        if "*" in v and len(v) != 1:
    73	            raise ValueError(
    74	                "wildcard '*' must be the only entry when used"
    75	            )
    76	        # de-dupe while preserving order
    77	        seen: set[str] = set()
    78	        out: List[str] = []
    79	        for entry in v:
    80	            if entry not in seen:
    81	                seen.add(entry)
    82	                out.append(entry)
    83	        return out
    84	
    85	
    86	class WebhookResponse(BaseModel):
    87	    """Read-side view of a subscription (no secret)."""
    88	
    89	    model_config = ConfigDict(extra="forbid")
    90	
    91	    id: int
    92	    name: str
    93	    target_url: str
    94	    events: List[str]
    95	    is_active: bool
    96	    created_at: datetime
    97	    last_delivery_at: Optional[datetime] = None
    98	    last_status: Optional[str] = None
    99	    last_error: Optional[str] = None
   100	
   101	
   102	class WebhookCreatedResponse(WebhookResponse):
   103	    """One-time create response. Carries the secret exactly once."""
   104	
   105	    secret: str = Field(min_length=32)
   106	
   107	
   108	class WebhookListResponse(BaseModel):
   109	    model_config = ConfigDict(extra="forbid")
   110	
   111	    items: List[WebhookResponse]
   112	    total: int = Field(ge=0)

exec
/bin/bash -lc "nl -ba backend/app/services/mfa.py | sed -n '1,240p'" in /data/projects/seige-range
 succeeded in 0ms:
     1	"""TOTP-based MFA service.
     2	
     3	Sprint 7 Phase C. Wraps ``pyotp`` with the platform-specific bits:
     4	secret generation, recovery-code lifecycle, login-step pending-token
     5	issuance, code verification across both TOTP and recovery-code paths.
     6	
     7	Recovery codes are 10 single-use 8-character strings, shown to the
     8	user once at confirm time. Only sha256 hashes live in the
     9	``mfa_recovery_codes`` table.
    10	
    11	The MFA pending token is a short-lived JWT issued during the login
    12	flow when a user has MFA enabled. It carries
    13	``{"type": "mfa_pending", "sub": <user_id>}`` and TTLs in 5 minutes;
    14	the user exchanges it via ``POST /auth/mfa/verify`` for the real
    15	access + refresh tokens.
    16	"""
    17	
    18	from __future__ import annotations
    19	
    20	import hashlib
    21	import secrets
    22	import string
    23	from dataclasses import dataclass
    24	from datetime import datetime, timedelta, timezone
    25	from typing import List, Optional
    26	
    27	import pyotp
    28	from sqlalchemy import select
    29	from sqlalchemy.ext.asyncio import AsyncSession
    30	
    31	from app.config import get_settings
    32	from app.models import MfaRecoveryCode, User
    33	from app.services.auth import create_access_token, create_refresh_token
    34	
    35	
    36	_RECOVERY_CODE_COUNT = 10
    37	_RECOVERY_CODE_LENGTH = 8
    38	_RECOVERY_CODE_ALPHABET = string.ascii_uppercase + string.digits
    39	
    40	_MFA_PENDING_TTL_SECONDS = 5 * 60
    41	
    42	
    43	class InvalidMfaCode(ValueError):
    44	    """Raised when a TOTP code or recovery code fails validation."""
    45	
    46	
    47	class MfaNotEnrolled(ValueError):
    48	    """Raised when an MFA action is attempted but the user hasn't
    49	    finished enrolment (mfa_secret unset OR mfa_enabled=False)."""
    50	
    51	
    52	@dataclass(frozen=True)
    53	class EnrolStartResult:
    54	    secret: str
    55	    provisioning_uri: str
    56	
    57	
    58	@dataclass(frozen=True)
    59	class EnrolConfirmResult:
    60	    recovery_codes: List[str]
    61	
    62	
    63	def _hash_recovery_code(code: str) -> str:
    64	    return hashlib.sha256(code.upper().encode("utf-8")).hexdigest()
    65	
    66	
    67	def _generate_recovery_codes() -> List[str]:
    68	    return [
    69	        "".join(
    70	            secrets.choice(_RECOVERY_CODE_ALPHABET)
    71	            for _ in range(_RECOVERY_CODE_LENGTH)
    72	        )
    73	        for _ in range(_RECOVERY_CODE_COUNT)
    74	    ]
    75	
    76	
    77	def _issuer_name() -> str:
    78	    settings = get_settings()
    79	    return "siege-range" if settings.is_production else "siege-range (dev)"
    80	
    81	
    82	async def start_enrolment(db: AsyncSession, user: User) -> EnrolStartResult:
    83	    """Generate a fresh TOTP secret + provisioning URI for ``user``.
    84	
    85	    Stores the secret on the row but does NOT enable MFA yet —
    86	    enable happens in :func:`confirm_enrolment` after the user
    87	    submits a valid TOTP code from their authenticator. Calling
    88	    :func:`start_enrolment` again on a partially-enrolled user
    89	    rotates the secret (the previous one becomes garbage).
    90	    """
    91	
    92	    secret = pyotp.random_base32()
    93	    user.mfa_secret = secret
    94	    user.mfa_enabled = False
    95	    await db.flush()
    96	
    97	    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
    98	        name=user.email,
    99	        issuer_name=_issuer_name(),
   100	    )
   101	    return EnrolStartResult(
   102	        secret=secret, provisioning_uri=provisioning_uri
   103	    )
   104	
   105	
   106	async def confirm_enrolment(
   107	    db: AsyncSession, user: User, code: str
   108	) -> EnrolConfirmResult:
   109	    """Verify the TOTP ``code`` and finalise enrolment.
   110	
   111	    On success: sets ``mfa_enabled=True``, generates 10 recovery
   112	    codes, stores their hashes, returns the cleartext list once
   113	    (the caller surfaces them to the UI; they're never persisted).
   114	    """
   115	
   116	    if not user.mfa_secret:
   117	        raise MfaNotEnrolled("call /mfa/enroll first")
   118	
   119	    if not pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1):
   120	        raise InvalidMfaCode("code did not match")
   121	
   122	    user.mfa_enabled = True
   123	
   124	    cleartext_codes = _generate_recovery_codes()
   125	    for cc in cleartext_codes:
   126	        db.add(
   127	            MfaRecoveryCode(
   128	                user_id=user.id,
   129	                code_hash=_hash_recovery_code(cc),
   130	            )
   131	        )
   132	    await db.flush()
   133	    return EnrolConfirmResult(recovery_codes=cleartext_codes)
   134	
   135	
   136	async def disable_mfa(db: AsyncSession, user: User, code: str) -> None:
   137	    """Verify ``code`` (TOTP or recovery) and disable MFA + drop
   138	    all stored recovery codes."""
   139	
   140	    from sqlalchemy import delete
   141	
   142	    if not user.mfa_enabled or not user.mfa_secret:
   143	        raise MfaNotEnrolled("MFA is not enabled")
   144	
   145	    await _verify_or_raise(db, user, code)
   146	
   147	    user.mfa_enabled = False
   148	    user.mfa_secret = None
   149	    await db.execute(
   150	        delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
   151	    )
   152	    await db.flush()
   153	
   154	
   155	async def verify_login_code(
   156	    db: AsyncSession, user: User, code: str
   157	) -> tuple[str, str]:
   158	    """Verify ``code`` against TOTP first, then recovery codes.
   159	
   160	    On success: returns the (access_token, refresh_token) pair.
   161	    On failure: raises :class:`InvalidMfaCode`.
   162	    """
   163	
   164	    if not user.mfa_enabled or not user.mfa_secret:
   165	        raise MfaNotEnrolled("MFA is not enabled")
   166	
   167	    await _verify_or_raise(db, user, code)
   168	    await db.flush()
   169	
   170	    return (
   171	        create_access_token(user.id, user.role.value),
   172	        create_refresh_token(user.id),
   173	    )
   174	
   175	
   176	async def _verify_or_raise(
   177	    db: AsyncSession, user: User, code: str
   178	) -> None:
   179	    """TOTP first; falls back to recovery codes. Marks the matched
   180	    recovery code used. Raises :class:`InvalidMfaCode` on miss."""
   181	
   182	    code_str = (code or "").strip()
   183	    if not code_str:
   184	        raise InvalidMfaCode("code missing")
   185	
   186	    # TOTP path — 6 digits.
   187	    if code_str.isdigit() and len(code_str) == 6:
   188	        if pyotp.TOTP(user.mfa_secret).verify(code_str, valid_window=1):
   189	            return
   190	
   191	    # Recovery-code path — alphanumeric, length matches.
   192	    candidate = _hash_recovery_code(code_str)
   193	    row: Optional[MfaRecoveryCode] = (
   194	        await db.execute(
   195	            select(MfaRecoveryCode).where(
   196	                MfaRecoveryCode.user_id == user.id,
   197	                MfaRecoveryCode.code_hash == candidate,
   198	                MfaRecoveryCode.used_at.is_(None),
   199	            )
   200	        )
   201	    ).scalars().first()
   202	    if row is not None:
   203	        row.used_at = datetime.now(timezone.utc)
   204	        return
   205	
   206	    raise InvalidMfaCode("code did not match")
   207	
   208	
   209	# ---------------------------------------------------------------------------
   210	# Pending-token plumbing for the two-step login flow
   211	# ---------------------------------------------------------------------------
   212	def issue_mfa_pending_token(user_id: int) -> str:
   213	    """Short-lived JWT carrying ``{type:"mfa_pending"}`` + sub.
   214	
   215	    Uses the same ``python-jose`` library as the rest of the auth
   216	    stack so signature verification is uniform.
   217	    """
   218	
   219	    from jose import jwt as jose_jwt
   220	
   221	    settings = get_settings()
   222	    payload = {
   223	        "sub": str(user_id),
   224	        "type": "mfa_pending",
   225	        "exp": int(
   226	            (
   227	                datetime.now(timezone.utc)
   228	                + timedelta(seconds=_MFA_PENDING_TTL_SECONDS)
   229	            ).timestamp()
   230	        ),
   231	    }
   232	    return jose_jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
   233	
   234	
   235	def decode_mfa_pending_token(token: str) -> int:
   236	    """Validate the pending token and return the user_id."""
   237	
   238	    from jose import jwt as jose_jwt, JWTError
   239	
   240	    settings = get_settings()

exec
/bin/bash -lc "nl -ba backend/app/services/webhook_dispatch.py | sed -n '218,285p'" in /data/projects/seige-range
exec
/bin/bash -lc "nl -ba .github/workflows/ci.yml | sed -n '1,70p'; nl -ba backend/pytest.ini | sed -n '1,50p'" in /data/projects/seige-range
exec
/bin/bash -lc "nl -ba backend/app/routers/ws.py | sed -n '1,180p'; nl -ba frontend/src/hooks/useWebSocket.js | sed -n '1,60p'" in /data/projects/seige-range
exec
/bin/bash -lc "nl -ba frontend/package.json | sed -n '1,120p'; nl -ba CLAUDE.md | sed -n '112,122p'" in /data/projects/seige-range
 succeeded in 0ms:
   218	
   219	    headers = {
   220	        "Content-Type": "application/json",
   221	        _SIGNATURE_HEADER: sign_body(subscription.secret, body),
   222	        _DELIVERY_HEADER: delivery_id,
   223	        _EVENT_HEADER: event_type,
   224	    }
   225	    started = time.monotonic()
   226	    try:
   227	        async with factory() as client:
   228	            response = await client.post(
   229	                subscription.target_url, content=body, headers=headers
   230	            )
   231	        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
   232	        if 200 <= response.status_code < 300:
   233	            return _AttemptOutcome(
   234	                subscription=subscription,
   235	                status=f"ok_{response.status_code}",
   236	                http_status=response.status_code,
   237	                response_ms=elapsed_ms,
   238	                error=None,
   239	            )
   240	        return _AttemptOutcome(
   241	            subscription=subscription,
   242	            status=f"http_{response.status_code}",
   243	            http_status=response.status_code,
   244	            response_ms=elapsed_ms,
   245	            error=f"non-2xx response: {response.status_code}",
   246	        )
   247	    except httpx.TimeoutException:
   248	        return _AttemptOutcome(
   249	            subscription=subscription,
   250	            status="timeout",
   251	            http_status=None,
   252	            response_ms=int((time.monotonic() - started) * 1000),
   253	            error="request timed out",
   254	        )
   255	    except httpx.HTTPError as exc:
   256	        return _AttemptOutcome(
   257	            subscription=subscription,
   258	            status="network_error",
   259	            http_status=None,
   260	            response_ms=int((time.monotonic() - started) * 1000),
   261	            error=f"{type(exc).__name__}: {exc}",
   262	        )
   263	    except Exception as exc:  # noqa: BLE001 — never propagate to caller
   264	        logger.error(
   265	            "webhook dispatch internal error",
   266	            subscription_id=subscription.id,
   267	            event_type=event_type,
   268	            error=f"{type(exc).__name__}: {exc}",
   269	        )
   270	        return _AttemptOutcome(
   271	            subscription=subscription,
   272	            status="internal_error",
   273	            http_status=None,
   274	            response_ms=int((time.monotonic() - started) * 1000),
   275	            error=f"{type(exc).__name__}: {exc}",
   276	        )
   277	
   278	
   279	# ---------------------------------------------------------------------------
   280	# Replay (slice 6)
   281	# ---------------------------------------------------------------------------
   282	async def replay_delivery(
   283	    *,
   284	    db: AsyncSession,
   285	    delivery: WebhookDelivery,

exec
/bin/bash -lc "wc -l backend/app/models.py backend/app/services/flag_submission.py; nl -ba CLAUDE.md | sed -n '1,125p'" in /data/projects/seige-range
 succeeded in 0ms:
     1	name: ci
     2	
     3	on:
     4	  push:
     5	    branches: [main]
     6	  pull_request:
     7	    branches: [main]
     8	
     9	# Cancel in-flight runs when a branch is pushed twice in quick
    10	# succession — the older run's signal is no longer load-bearing.
    11	concurrency:
    12	  group: ci-${{ github.ref }}
    13	  cancel-in-progress: true
    14	
    15	jobs:
    16	  backend-tests:
    17	    name: backend — pytest + coverage gate
    18	    runs-on: ubuntu-22.04
    19	    timeout-minutes: 20
    20	
    21	    steps:
    22	      - name: checkout
    23	        uses: actions/checkout@v4
    24	
    25	      - name: set up python 3.11
    26	        uses: actions/setup-python@v5
    27	        with:
    28	          python-version: '3.11'
    29	          cache: 'pip'
    30	          cache-dependency-path: backend/requirements*.txt
    31	
    32	      - name: install backend deps
    33	        working-directory: backend
    34	        run: |
    35	          python -m pip install --upgrade pip
    36	          pip install -r requirements.txt -r requirements-test.txt
    37	
    38	      - name: run pytest — unit tests only (integration suite needs
    39	          testcontainers config that isn't wired into CI yet)
    40	        working-directory: backend
    41	        env:
    42	          APP_ENV: test
    43	          SECRET_KEY: ci-test-secret-do-not-use-in-prod-0123456789abcdef0123456789abcdef
    44	          ADMIN_PASSWORD: CIAdminPasswordA1!
    45	          ALLOWED_ORIGINS: http://localhost:3000
    46	        run: |
    47	          python -m pytest tests/unit/ -v --no-cov
    48	
    49	  frontend-build:
    50	    name: frontend — vite build + lint
    51	    runs-on: ubuntu-22.04
    52	    timeout-minutes: 10
    53	
    54	    steps:
    55	      - name: checkout
    56	        uses: actions/checkout@v4
    57	
    58	      - name: set up node 20
    59	        uses: actions/setup-node@v4
    60	        with:
    61	          node-version: '20'
    62	          cache: 'npm'
    63	          cache-dependency-path: frontend/package-lock.json
    64	
    65	      - name: install
    66	        working-directory: frontend
    67	        run: npm ci
    68	
    69	      - name: lint
    70	        working-directory: frontend
     1	[pytest]
     2	testpaths = tests
     3	asyncio_mode = auto
     4	filterwarnings =
     5	    ignore::DeprecationWarning:passlib.*
     6	    ignore::DeprecationWarning:jose.*
     7	addopts =
     8	    -ra
     9	    --strict-markers
    10	    --strict-config
    11	    --cov=app.services.auth
    12	    --cov=app.services.scoring
    13	    --cov=app.services.audit
    14	    --cov=app.services.hints
    15	    --cov=app.services.flag_submission
    16	    --cov=app.services.challenge_browse
    17	    --cov=app.services.challenge_loader
    18	    --cov=app.services.flag_dispatch
    19	    --cov=app.services.validator_registry
    20	    --cov=app.services.validator_sandbox
    21	    --cov=app.services.validator_subprocess_runner
    22	    --cov=app.services.test_harness
    23	    --cov=app.services.api_v1
    24	    --cov=app.services.webhook_dispatch
    25	    --cov=app.routers.v1
    26	    --cov=app.validators
    27	    --cov=app.routers.auth
    28	    --cov=app.routers.challenges
    29	    --cov=app.routers.admin
    30	    --cov=app.routers.competitions
    31	    --cov=app.routers.health
    32	    --cov=app.routers.instances
    33	    --cov=app.routers.leaderboard
    34	    --cov=app.routers.notifications
    35	    --cov=app.routers.stats
    36	    --cov=app.routers.writeups
    37	    --cov=app.security.seccomp
    38	    --cov=app.services.orchestration
    39	    --cov=app.services.scheduler
    40	    --cov=app.services.ws_manager
    41	    --cov-report=term-missing
    42	    # Phase 12 (slice 12): project-wide gate bumped from the Phase 5
    43	    # 60% floor to 80% per the Phase 0 commitment. Slices 1–11 left
    44	    # the project at ~86%; the new gate locks in the margin.
    45	    --cov-fail-under=80
    46	markers =
    47	    integration: tests that hit the testcontainer Postgres/Redis
    48	    unit: in-process unit tests with no external deps (mocked docker, no DB)

 succeeded in 0ms:
     1	import asyncio
     2	import json
     3	
     4	from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
     5	
     6	from app.services.auth import decode_token
     7	from app.services.ws_manager import ws_manager
     8	
     9	router = APIRouter(tags=["websocket"])
    10	
    11	
    12	@router.websocket("/ws")
    13	async def websocket_endpoint(
    14	    websocket: WebSocket,
    15	    token: str = Query(None),
    16	):
    17	    if not token:
    18	        await websocket.close(code=4001, reason="Missing authentication token")
    19	        return
    20	
    21	    try:
    22	        payload = decode_token(token)
    23	        user_id = int(payload.get("sub", 0))
    24	        if not user_id:
    25	            await websocket.close(code=4001, reason="Invalid token")
    26	            return
    27	    except Exception:
    28	        await websocket.close(code=4001, reason="Invalid or expired token")
    29	        return
    30	
    31	    await ws_manager.connect(websocket, user_id)
    32	
    33	    heartbeat_task = asyncio.create_task(_heartbeat(websocket))
    34	
    35	    try:
    36	        while True:
    37	            data = await websocket.receive_text()
    38	            try:
    39	                message = json.loads(data)
    40	            except json.JSONDecodeError:
    41	                continue
    42	            if message.get("type") == "ping":
    43	                await websocket.send_json({"type": "pong"})
    44	    except WebSocketDisconnect:
    45	        pass
    46	    except Exception:
    47	        pass
    48	    finally:
    49	        heartbeat_task.cancel()
    50	        await ws_manager.disconnect(websocket, user_id)
    51	
    52	
    53	async def _heartbeat(websocket: WebSocket):
    54	    try:
    55	        while True:
    56	            await asyncio.sleep(30)
    57	            try:
    58	                await websocket.send_json({"type": "ping"})
    59	            except Exception:
    60	                break
    61	    except asyncio.CancelledError:
    62	        pass
     1	import { useEffect, useRef, useState, useCallback } from 'react'
     2	import useAuthStore from '../stores/authStore'
     3	import useLeaderboardStore from '../stores/leaderboardStore'
     4	import useChallengeStore from '../stores/challengeStore'
     5	import useNotificationStore from '../stores/notificationStore'
     6	
     7	export default function useWebSocket() {
     8	  const [connectionState, setConnectionState] = useState('disconnected')
     9	  const [lastMessage, setLastMessage] = useState(null)
    10	  const wsRef = useRef(null)
    11	  const reconnectDelay = useRef(1000)
    12	  const accessToken = useAuthStore((s) => s.accessToken)
    13	
    14	  const connect = useCallback(() => {
    15	    if (!accessToken) return
    16	    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    17	    const url = `${protocol}//${window.location.host}/api/ws?token=${accessToken}`
    18	
    19	    setConnectionState('connecting')
    20	    const ws = new WebSocket(url)
    21	    wsRef.current = ws
    22	
    23	    ws.onopen = () => {
    24	      setConnectionState('connected')
    25	      reconnectDelay.current = 1000
    26	    }
    27	
    28	    ws.onmessage = (event) => {
    29	      try {
    30	        const data = JSON.parse(event.data)
    31	        setLastMessage(data)
    32	
    33	        if (data.type === 'flag_captured') {
    34	          useLeaderboardStore.getState().fetchLeaderboard()
    35	        } else if (data.type === 'challenge_released') {
    36	          useChallengeStore.getState().fetchChallenges()
    37	        } else if (data.type === 'notification') {
    38	          useNotificationStore.getState().addNotification(data)
    39	          useNotificationStore.getState().fetchUnreadCount()
    40	        }
    41	      } catch {}
    42	    }
    43	
    44	    ws.onclose = () => {
    45	      setConnectionState('disconnected')
    46	      wsRef.current = null
    47	      const delay = Math.min(reconnectDelay.current, 30000)
    48	      reconnectDelay.current *= 2
    49	      setTimeout(connect, delay)
    50	    }
    51	
    52	    ws.onerror = () => {
    53	      ws.close()
    54	    }
    55	  }, [accessToken])
    56	
    57	  useEffect(() => {
    58	    connect()
    59	    return () => {
    60	      if (wsRef.current) {

 succeeded in 0ms:
     1	{
     2	  "name": "siege-range-dashboard",
     3	  "private": true,
     4	  "version": "2.4.1",
     5	  "type": "module",
     6	  "scripts": {
     7	    "dev": "vite --host 0.0.0.0",
     8	    "build": "vite build",
     9	    "preview": "vite preview",
    10	    "e2e": "playwright test",
    11	    "e2e:list": "playwright test --list",
    12	    "e2e:ui": "playwright test --ui"
    13	  },
    14	  "dependencies": {
    15	    "axios": "^1.6.7",
    16	    "clsx": "^2.1.0",
    17	    "lucide-react": "^0.344.0",
    18	    "react": "^18.2.0",
    19	    "react-dom": "^18.2.0",
    20	    "react-router-dom": "^6.22.1",
    21	    "recharts": "^2.12.2",
    22	    "zustand": "^4.5.1"
    23	  },
    24	  "devDependencies": {
    25	    "@playwright/test": "^1.59.1",
    26	    "@tailwindcss/vite": "^4.0.0",
    27	    "@vitejs/plugin-react": "^4.2.1",
    28	    "autoprefixer": "^10.4.17",
    29	    "tailwindcss": "^4.0.0",
    30	    "vite": "^5.1.4"
    31	  }
    32	}
   112	- PII and sensitive fields are encrypted at rest and masked in logs. Implement a `SensitiveString` wrapper type that redacts on serialisation/logging.
   113	- No secrets in URLs or query parameters. Ever.
   114	- Database queries use parameterised queries or ORM methods. Raw string interpolation into SQL is forbidden.
   115	- All HTTP responses include security headers: `Content-REDACTED-Policy`, `X-Content-Type-Options`, `Strict-Transport-REDACTED`, `X-Frame-Options`.
   116	
   117	### 3.4 Dependency REDACTED
   118	
   119	- Pin all dependency versions exactly. No floating ranges (`^`, `~`, `*`).
   120	- Run `npm audit` / `pip audit` / `cargo audit` (as appropriate) before every commit. Fail the build on HIGH or CRITICAL findings.
   121	- No dependencies with known CVEs in CISA KEV or with EPSS > 0.7.
   122	- Review new dependencies before adding: check maintainer count, last publish date, download count, licence compatibility.

 succeeded in 0ms:
  562 backend/app/models.py
  614 backend/app/services/flag_submission.py
 1176 total
     1	# CLAUDE.md — Project Engineering Standards
     2	
     3	> This file governs how Claude Code builds, modifies, and reviews code in this project.
     4	> All directives are mandatory. Violations must be flagged, not silently ignored.
     5	>
     6	> **Canonical source:** `standards` repo. Do not edit per-project copies directly.
     7	> Pull updates via `./scripts/sync-standards.sh` or CI bootstrap.
     8	
     9	---
    10	
    11	## 1. ARCHITECTURE PRINCIPLES
    12	
    13	### 1.1 Modularity
    14	
    15	- **Single Responsibility**: Every module, class, and function does exactly one thing. If you need the word "and" to describe what it does, split it.
    16	- **Explicit Boundaries**: Each module exposes a public API via an `index.ts` (or `__init__.py`, `mod.rs`, etc.). Internal implementation files are never imported directly by other modules.
    17	- **Dependency Direction**: Dependencies flow inward. Core/domain logic has zero dependencies on infrastructure, frameworks, or I/O. Use dependency injection or ports-and-adapters to invert where needed.
    18	- **No God Files**: No single file exceeds 300 lines. No single function exceeds 50 lines. If a module needs more, decompose it.
    19	- **Feature Isolation**: New features are added as new modules, not by extending existing ones. Existing modules are only modified to expose new extension points.
    20	
    21	### 1.2 Project Structure
    22	
    23	Every project must follow a consistent layout. Adapt naming to the language ecosystem but preserve the separation:
    24	
    25	```
    26	src/
    27	├── core/              # Domain logic, pure functions, business rules — zero I/O
    28	├── services/          # Orchestration layer — coordinates core logic with infra
    29	├── infra/             # External integrations: DB, HTTP, queues, file I/O
    30	│   ├── db/
    31	│   ├── http/
    32	│   └── queue/
    33	├── api/               # Entrypoints: REST routes, CLI handlers, event consumers
    34	├── shared/            # Cross-cutting: types, constants, errors, result types
    35	│   ├── types/
    36	│   ├── errors/
    37	│   └── constants/
    38	├── config/            # Configuration loading, validation, env parsing
    39	└── utils/             # Pure utility functions only — no business logic
    40	tests/
    41	├── unit/              # Mirror src/ structure, one test file per module
    42	├── integration/       # Tests requiring real infra (DB, network)
    43	└── fixtures/          # Shared test data, factories, builders
    44	scripts/               # Build, deploy, migration, seed scripts
    45	docs/                  # Architecture decision records, runbooks, API docs
    46	docker/                # Dockerfiles, compose files, container configs
    47	```
    48	
    49	### 1.3 Naming & Conventions
    50	
    51	- Files: `kebab-case` (TS/JS), `snake_case` (Python/Rust).
    52	- Exported types/classes: `PascalCase`. Functions/variables: `camelCase` (TS/JS) or `snake_case` (Python/Rust).
    53	- Boolean variables/functions: prefix with `is`, `has`, `should`, `can`.
    54	- Constants: `UPPER_SNAKE_CASE`, defined in `shared/constants/`.
    55	- No abbreviations in public APIs. `getUserAuthentication()` not `getUsrAuth()`.
    56	
    57	### 1.4 Dependency Injection & Wiring
    58	
    59	- **Constructor injection** is the default pattern. All dependencies are passed explicitly — no service locators, no ambient singletons, no module-level mutable state.
    60	- **Composition root**: A single wiring entrypoint (`src/composition-root.ts`, `src/container.py`, etc.) assembles the dependency graph. No other file instantiates infrastructure or service-layer objects.
    61	- **Interfaces over implementations**: Core and service layers depend on interfaces/protocols/traits. Concrete implementations live in `infra/` and are wired at the composition root.
    62	- **Test seams**: Every external dependency is injectable, making it replaceable in tests without mocks of internals. Fake implementations live in `tests/fixtures/fakes/`.
    63	
    64	---
    65	
    66	## 2. ERROR HANDLING & RESULT TYPES
    67	
    68	### 2.1 Fail-Fast, Fail-Loud
    69	
    70	- **No silent swallowing.** Every `catch` block must either re-throw, return a typed error, or log at `ERROR` level with full context. Empty catch blocks are forbidden.
    71	- **Use Result types** over thrown exceptions for expected failure paths. `Result<T, E>` (Rust), `Either` pattern (TS), or equivalent. Exceptions are for truly exceptional/unrecoverable situations.
    72	- **Validate at the boundary.** All external input (HTTP, CLI, env vars, file reads, queue messages) is validated and parsed into typed domain objects at the point of entry. Nothing unvalidated reaches core logic.
    73	
    74	### 2.2 Error Classification
    75	
    76	Define and use a typed error hierarchy:
    77	
    78	```
    79	AppError
    80	├── ValidationError      # Bad input — 400-class
    81	├── AuthenticationError  # Identity unknown — 401
    82	├── AuthorisationError   # Identity known, access denied — 403
    83	├── NotFoundError        # Resource does not exist — 404
    84	├── ConflictError        # State conflict — 409
    85	├── RateLimitError       # Throttled — 429
    86	├── DependencyError      # Upstream/infra failure — 502/503
    87	└── InternalError        # Unexpected bug — 500
    88	```
    89	
    90	Every error must carry: `code` (machine-readable), `message` (human-readable), `context` (structured metadata), `timestamp`, `requestId` (if in a request context).
    91	
    92	---
    93	
    94	## 3. SECURITY CONTROLS
    95	
    96	### 3.1 Input Validation
    97	
    98	- Validate **all** external input with a schema validation library (Zod, Pydantic, JSON Schema, etc.). No hand-rolled regex-only validation.
    99	- Apply allowlists, not denylists. Define what is permitted, reject everything else.
   100	- Enforce length limits, type constraints, and format constraints on every field.
   101	- Sanitise all string inputs before use in HTML, SQL, shell commands, or log output.
   102	
   103	### 3.2 Authentication & Authorisation
   104	
   105	- Never store secrets, API keys, tokens, or passwords in source code, config files, or environment variable defaults. Use a secrets manager or `.env` files excluded via `.gitignore`.
   106	- Always check authorisation at the service layer, not only at the API/route layer. Defence in depth.
   107	- Implement principle of least privilege: every component, user, and service account gets the minimum permissions required.
   108	- Session tokens / JWTs: validate expiry, issuer, audience, and signature on every request. No "trust the client" patterns.
   109	
   110	### 3.3 Data Protection
   111	
   112	- PII and sensitive fields are encrypted at rest and masked in logs. Implement a `SensitiveString` wrapper type that redacts on serialisation/logging.
   113	- No secrets in URLs or query parameters. Ever.
   114	- Database queries use parameterised queries or ORM methods. Raw string interpolation into SQL is forbidden.
   115	- All HTTP responses include security headers: `Content-REDACTED-Policy`, `X-Content-Type-Options`, `Strict-Transport-REDACTED`, `X-Frame-Options`.
   116	
   117	### 3.4 Dependency REDACTED
   118	
   119	- Pin all dependency versions exactly. No floating ranges (`^`, `~`, `*`).
   120	- Run `npm audit` / `pip audit` / `cargo audit` (as appropriate) before every commit. Fail the build on HIGH or CRITICAL findings.
   121	- No dependencies with known CVEs in CISA KEV or with EPSS > 0.7.
   122	- Review new dependencies before adding: check maintainer count, last publish date, download count, licence compatibility.
   123	
   124	---
   125	

codex
Most listed findings are now directly confirmed or bounded. I’m doing a quick router/service skim for high-signal missed issues, focusing on authz gaps, secret handling, shell/process execution, and unsafe outbound/network behavior.
exec
/bin/bash -lc 'rg -n "def require_admin|async def require_admin|get_current_user|UserRole|role|is_admin|current_user" backend/app' in /data/projects/seige-range
exec
/bin/bash -lc "rg -n \"flag|value|secret|password|token|email|payload=|logger\\.|print\\(\" backend/app/routers backend/app/services | sed -n '1,260p'" in /data/projects/seige-range
 succeeded in 0ms:
backend/app/services/validator_registry.py:118:                f"entry point {ep.name!r} from {ep.value!r} resolved to "
backend/app/services/validator_registry.py:121:        registry.register(instance, source=ep.value)
backend/app/services/validator_registry.py:122:        _logger.info(
backend/app/services/validator_registry.py:124:            extra={"name": ep.name, "target": ep.value},
backend/app/services/validator_registry.py:144:    services (``audit.append``, ``flag_dispatch.dispatch_submission``).
backend/app/services/api_v1.py:55:        # callers' validation matches the model's accepted values.
backend/app/services/api_v1.py:82:                "team": user.team.value if user.team else None,
backend/app/services/notifications.py:86:        logger.warning(
backend/app/services/scoring.py:66:async def calculate_flag_points(
backend/app/services/scoring.py:68:    flag: ChallengeFlag,
backend/app/services/scoring.py:73:    """Score a single per-flag capture for a multi-flag v1 challenge.
backend/app/services/scoring.py:75:    Mirrors :func:`calculate_points` but operates on the per-flag
backend/app/services/scoring.py:76:    base value declared in the manifest. The "first blood" bonus
backend/app/services/scoring.py:77:    fires when no other user has yet captured *this specific flag*
backend/app/services/scoring.py:78:    (read from ``solved_flags``), not when no one has fully solved
backend/app/services/scoring.py:79:    the challenge — multi-flag scoring rewards the racer who got
backend/app/services/scoring.py:80:    each flag first, which is what blue-team co-op challenges
backend/app/services/scoring.py:84:    identically to :func:`calculate_points` so a per-flag capture
backend/app/services/scoring.py:89:    base = float(flag.points)
backend/app/services/scoring.py:93:        # this same flag, decay base by 5% per prior capture, floor
backend/app/services/scoring.py:99:                    SolvedFlag.flag_id == flag.flag_id,
backend/app/services/scoring.py:103:        base = max(flag.points * 0.2, flag.points * (0.95 ** capture_count))
backend/app/services/scoring.py:107:    # First-blood-flag bonus +25%: nobody else has captured this
backend/app/services/scoring.py:108:    # specific (challenge, flag) pair yet.
backend/app/services/scoring.py:113:                SolvedFlag.flag_id == flag.flag_id,
backend/app/routers/notifications.py:90:        .values(is_read=True)
backend/app/services/auth.py:21:def hash_password(password: str) -> str:
backend/app/services/auth.py:22:    return pwd_context.hash(password)
backend/app/services/auth.py:25:def verify_password(plain_password: str, hashed_password: str) -> bool:
backend/app/services/auth.py:26:    return pwd_context.verify(plain_password, hashed_password)
backend/app/services/auth.py:29:def create_access_token(user_id: int, role: str) -> str:
backend/app/services/auth.py:40:def create_refresh_token(user_id: int) -> str:
backend/app/services/auth.py:50:def decode_token(token: str) -> dict:
backend/app/services/auth.py:52:        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
backend/app/services/auth.py:57:            detail="Invalid or expired token",
backend/app/services/auth.py:70:    payload = decode_token(credentials.credentials)
backend/app/services/auth.py:74:            detail="Invalid token type",
backend/app/services/auth.py:88:    if current_user.role.value != "admin":
backend/app/services/auth.py:96:async def check_account_lockout(email: str, redis_client) -> None:
backend/app/services/auth.py:97:    key = f"login_failures:{email}"
backend/app/services/auth.py:106:async def record_failed_login(email: str, redis_client) -> None:
backend/app/services/auth.py:107:    key = f"login_failures:{email}"
backend/app/services/auth.py:112:async def clear_failed_logins(email: str, redis_client) -> None:
backend/app/services/auth.py:113:    key = f"login_failures:{email}"
backend/app/services/hints.py:41:    Returns ``(index, hint_value)``. ``hint_value`` is whatever's stored
backend/app/services/email.py:1:"""Outbound email sender.
backend/app/services/email.py:3:Sprint 6. Used by the password-reset flow today; will host
backend/app/services/email.py:4:verification + future transactional emails. Three modes:
backend/app/services/email.py:19:  :func:`reset_captured_emails` between cases.
backend/app/services/email.py:23:back to the client (the password-reset endpoint maps
backend/app/services/email.py:54:# ``reset_captured_emails`` from test setup; not cleared between
backend/app/services/email.py:59:def reset_captured_emails() -> None:
backend/app/services/email.py:63:async def send_email(
backend/app/services/email.py:69:    """Dispatch a single plaintext email.
backend/app/services/email.py:89:                    "event": "email.dev_fallback",
backend/app/services/email.py:126:            password=settings.SMTP_PASSWORD,
backend/app/services/email.py:130:        logger.error(
backend/app/services/email.py:131:            "email.delivery_failed",
backend/app/services/email.py:143:    "reset_captured_emails",
backend/app/services/email.py:144:    "send_email",
backend/app/routers/auth.py:17:    create_access_token,
backend/app/routers/auth.py:18:    create_refresh_token,
backend/app/routers/auth.py:19:    decode_token,
backend/app/routers/auth.py:21:    hash_password,
backend/app/routers/auth.py:23:    verify_password,
backend/app/routers/auth.py:48:    email = data.email
backend/app/routers/auth.py:50:    password = data.password
backend/app/routers/auth.py:55:        select(User).where((User.email == email) | (User.username == username))
backend/app/routers/auth.py:61:        email=email,
backend/app/routers/auth.py:63:        hashed_password=hash_password(password),
backend/app/routers/auth.py:79:        payload={
backend/app/routers/auth.py:81:            "team": user.team.value if user.team else None,
backend/app/routers/auth.py:87:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:88:    refresh_token = create_refresh_token(user.id)
backend/app/routers/auth.py:94:            "email": user.email,
backend/app/routers/auth.py:96:            "team": user.team.value if user.team else None,
backend/app/routers/auth.py:97:            "role": user.role.value,
backend/app/routers/auth.py:101:        "access_token": access_token,
backend/app/routers/auth.py:102:        "refresh_token": refresh_token,
backend/app/routers/auth.py:113:    email = data.email
backend/app/routers/auth.py:114:    password = data.password
backend/app/routers/auth.py:117:    await check_account_lockout(email, redis_client)
backend/app/routers/auth.py:119:    result = await db.execute(select(User).where(User.email == email))
backend/app/routers/auth.py:122:    if not user or not verify_password(password, user.hashed_password):
backend/app/routers/auth.py:124:            await record_failed_login(email, redis_client)
backend/app/routers/auth.py:132:            payload={
backend/app/routers/auth.py:133:                "email": email,
backend/app/routers/auth.py:134:                "reason": "bad_password" if user else "unknown_user",
backend/app/routers/auth.py:149:            payload={"email": email, "reason": "account_disabled"},
backend/app/routers/auth.py:155:    await clear_failed_logins(email, redis_client)
backend/app/routers/auth.py:164:        payload={"username": user.username},
backend/app/routers/auth.py:169:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:170:    refresh_token = create_refresh_token(user.id)
backend/app/routers/auth.py:176:            "email": user.email,
backend/app/routers/auth.py:178:            "team": user.team.value if user.team else None,
backend/app/routers/auth.py:179:            "role": user.role.value,
backend/app/routers/auth.py:184:        "access_token": access_token,
backend/app/routers/auth.py:185:        "refresh_token": refresh_token,
backend/app/routers/auth.py:196:    token = data.refresh_token
backend/app/routers/auth.py:198:    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
backend/app/routers/auth.py:202:    payload = decode_token(token)
backend/app/routers/auth.py:204:        raise HTTPException(status_code=401, detail="Invalid token type")
backend/app/routers/auth.py:212:    new_access = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:220:        payload={"username": user.username},
backend/app/routers/auth.py:224:    return {"access_token": new_access, "token_type": "bearer"}
backend/app/routers/auth.py:234:    token = data.refresh_token
backend/app/routers/auth.py:236:    if token:
backend/app/routers/auth.py:238:            payload = decode_token(token)
backend/app/routers/auth.py:242:                await redis_client.set(f"siege:blacklist:{token}", "1", ex=ttl)
backend/app/routers/auth.py:258:        payload={"token_revoked": bool(token)},
backend/app/routers/auth.py:296:        "email": current_user.email,
backend/app/routers/auth.py:298:        "team": current_user.team.value if current_user.team else None,
backend/app/routers/auth.py:299:        "role": current_user.role.value,
backend/app/services/scheduler.py:42:                logger.info("Cleaned up expired instances", count=count)
backend/app/services/scheduler.py:47:                logger.info("Swept orphan instances", count=orphaned)
backend/app/services/scheduler.py:61:            logger.info("Reaped idle workstations", user_ids=reaped)
backend/app/services/scheduler.py:63:        logger.warning("workstation.reap.job_failed", error=str(exc))
backend/app/services/scheduler.py:68:    actor crosses the burst threshold of correct flag submissions
backend/app/services/scheduler.py:77:                logger.info("Submission-burst alerts raised", count=raised)
backend/app/services/scheduler.py:79:        logger.warning("cheat_detector.job_failed", error=str(exc))
backend/app/services/scheduler.py:117:                    "team": row.team.value if row.team else None,
backend/app/services/scheduler.py:125:        logger.error("Failed to cache leaderboard", error=str(e))
backend/app/services/scheduler.py:141:            logger.info("Cleaned up old notifications")
backend/app/services/scheduler.py:143:        logger.error("Notification cleanup failed", error=str(e))
backend/app/services/scheduler.py:155:                logger.info(
backend/app/services/scheduler.py:159:        logger.error("Webhook retry failed", error=str(e))
backend/app/services/scheduler.py:185:        logger.error("Audit verify scheduler crashed", error=str(exc))
backend/app/services/scheduler.py:198:        logger.info(
backend/app/services/scheduler.py:205:    logger.error(
backend/app/services/scheduler.py:227:        logger.error("audit_ledger.notify_failed", error=str(exc))
backend/app/services/scheduler.py:246:        logger.info("backup.skipped", reason="BACKUP_DIR empty")
backend/app/services/scheduler.py:258:    logger.error(
backend/app/services/scheduler.py:279:        logger.error("backup.notify_failed", error=str(exc))
backend/app/services/scheduler.py:292:                logger.info(
backend/app/services/scheduler.py:296:        logger.error("Webhook prune failed", error=str(e))
backend/app/services/scheduler.py:325:    # for actors crossing the burst threshold of correct flag
backend/app/services/scheduler.py:331:    logger.info("Scheduler started")
backend/app/routers/admin.py:17:from app.validators.exact import hash_exact_value
backend/app/routers/admin.py:64:                "email": user.email,
backend/app/routers/admin.py:93:    for field, value in updates.items():
backend/app/routers/admin.py:94:        setattr(user, field, value)
backend/app/routers/admin.py:208:        flag = data.get("flag", "")
backend/app/routers/admin.py:209:        flag_hashed = hash_exact_value(flag) if flag else ""
backend/app/routers/admin.py:219:            flag_hash=flag_hashed,
backend/app/services/mfa.py:4:secret generation, recovery-code lifecycle, login-step pending-token
backend/app/services/mfa.py:11:The MFA pending token is a short-lived JWT issued during the login
backend/app/services/mfa.py:15:access + refresh tokens.
backend/app/services/mfa.py:21:import secrets
backend/app/services/mfa.py:33:from app.services.auth import create_access_token, create_refresh_token
backend/app/services/mfa.py:49:    finished enrolment (mfa_secret unset OR mfa_enabled=False)."""
backend/app/services/mfa.py:54:    secret: str
backend/app/services/mfa.py:70:            secrets.choice(_RECOVERY_CODE_ALPHABET)
backend/app/services/mfa.py:83:    """Generate a fresh TOTP secret + provisioning URI for ``user``.
backend/app/services/mfa.py:85:    Stores the secret on the row but does NOT enable MFA yet —
backend/app/services/mfa.py:89:    rotates the secret (the previous one becomes garbage).
backend/app/services/mfa.py:92:    secret = pyotp.random_base32()
backend/app/services/mfa.py:93:    user.mfa_secret = secret
backend/app/services/mfa.py:97:    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
backend/app/services/mfa.py:98:        name=user.email,
backend/app/services/mfa.py:102:        secret=secret, provisioning_uri=provisioning_uri
backend/app/services/mfa.py:116:    if not user.mfa_secret:
backend/app/services/mfa.py:119:    if not pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1):
backend/app/services/mfa.py:142:    if not user.mfa_enabled or not user.mfa_secret:
backend/app/services/mfa.py:148:    user.mfa_secret = None
backend/app/services/mfa.py:160:    On success: returns the (access_token, refresh_token) pair.
backend/app/services/mfa.py:164:    if not user.mfa_enabled or not user.mfa_secret:
backend/app/services/mfa.py:171:        create_access_token(user.id, user.role.value),
backend/app/services/mfa.py:172:        create_refresh_token(user.id),
backend/app/services/mfa.py:188:        if pyotp.TOTP(user.mfa_secret).verify(code_str, valid_window=1):
backend/app/services/mfa.py:210:# Pending-token plumbing for the two-step login flow
backend/app/services/mfa.py:212:def issue_mfa_pending_token(user_id: int) -> str:
backend/app/services/mfa.py:235:def decode_mfa_pending_token(token: str) -> int:
backend/app/services/mfa.py:236:    """Validate the pending token and return the user_id."""
backend/app/services/mfa.py:243:            token, settings.SECRET_KEY, algorithms=["HS256"]
backend/app/services/mfa.py:246:        raise InvalidMfaCode("invalid pending token") from exc
backend/app/services/mfa.py:248:        raise InvalidMfaCode("wrong token type")
backend/app/services/mfa.py:253:        raise InvalidMfaCode("malformed pending token") from exc
backend/app/services/mfa.py:262:    "decode_mfa_pending_token",
backend/app/services/mfa.py:264:    "issue_mfa_pending_token",
backend/app/services/orchestration/profiles.py:33:    kwargs purely from these values. Manifests cannot override any
backend/app/services/cheat_detector.py:4:``challenge.flag.submit.pass`` events in a rolling window, groups by
backend/app/services/cheat_detector.py:24:* ``BURST_THRESHOLD = 8`` correct flags in that window
backend/app/services/cheat_detector.py:48:_EVENT = "challenge.flag.submit.pass"
backend/app/services/cheat_detector.py:74:        logger.warning(
backend/app/services/cheat_detector.py:110:                f"flag submissions in the {BURST_WINDOW_MINUTES} minute "
backend/app/services/cheat_detector.py:119:        logger.info(
backend/app/services/orchestration/egress.py:214:    flapping egress proxy must not 500 a flag submission or block an
backend/app/services/orchestration/egress.py:226:        logger.info(
backend/app/services/orchestration/egress.py:233:        logger.warning(
backend/app/services/orchestration/egress.py:276:        logger.warning(
backend/app/services/orchestration/cleanup.py:79:        logger.warning("container.stop_failed", id=container_id, error=str(exc))
backend/app/services/orchestration/cleanup.py:83:        logger.warning("container.remove_failed", id=container_id, error=str(exc))
backend/app/services/orchestration/cleanup.py:107:                payload={
backend/app/services/orchestration/cleanup.py:121:            logger.info("instance.cleanup", instance_id=instance.id)
backend/app/services/orchestration/cleanup.py:124:            logger.error(
backend/app/services/orchestration/cleanup.py:157:        logger.warning("orphan_sweep.docker_list_failed", error=str(exc))
backend/app/services/orchestration/cleanup.py:175:                payload={
backend/app/services/orchestration/cleanup.py:185:            logger.info("instance.orphan_swept", instance_id=inst.id)
backend/app/services/orchestration/cleanup.py:188:            logger.warning(
backend/app/services/orchestration/cleanup.py:205:        "status": instance.status.value,
backend/app/services/flag_submission.py:32:from app.services.flag_dispatch import dispatch_submission
backend/app/services/flag_submission.py:33:from app.services.scoring import calculate_flag_points, calculate_points, update_streak
backend/app/services/flag_submission.py:68:    flag_id: str | None = None
backend/app/services/flag_submission.py:138:    submitted_flag: str,
backend/app/services/flag_submission.py:142:    """Run the full flag-submission flow.
backend/app/services/flag_submission.py:150:    * **Single-flag / legacy**: the historical one-shot path — first
backend/app/services/flag_submission.py:154:    * **Multi-flag v1** (``len(challenge.flag_definitions) >= 2``):
backend/app/services/flag_submission.py:155:      per-flag captures award per-flag points; the ``Solve`` row is
backend/app/services/flag_submission.py:156:      created only when *every* declared flag has been captured by
backend/app/services/flag_submission.py:157:      this user. Re-submitting a flag the user already captured
backend/app/services/flag_submission.py:166:    flag_defs = list(challenge.flag_definitions or [])
backend/app/services/flag_submission.py:167:    if len(flag_defs) >= 2:
backend/app/services/flag_submission.py:168:        return await _process_multi_flag_submission(
backend/app/services/flag_submission.py:171:            flag_defs=flag_defs,
backend/app/services/flag_submission.py:172:            submitted_flag=submitted_flag,
backend/app/services/flag_submission.py:180:    dispatch = await dispatch_submission(submitted_flag, challenge)
backend/app/services/flag_submission.py:187:            matched_flag_id=dispatch.flag_id,
backend/app/services/flag_submission.py:195:async def _process_multi_flag_submission(
backend/app/services/flag_submission.py:199:    flag_defs: list,
backend/app/services/flag_submission.py:200:    submitted_flag: str,
backend/app/services/flag_submission.py:205:    # a no-op (409). Same semantics as the single-flag branch.
backend/app/services/flag_submission.py:218:    dispatch = await dispatch_submission(submitted_flag, challenge)
backend/app/services/flag_submission.py:228:        (f for f in flag_defs if f.flag_id == dispatch.flag_id), None
backend/app/services/flag_submission.py:231:        # Dispatcher reported a flag_id that isn't in the challenge's
backend/app/services/flag_submission.py:233:        # iterates the same rows we have in flag_defs — but treat as
backend/app/services/flag_submission.py:248:                SolvedFlag.flag_id == matched.flag_id,
backend/app/services/flag_submission.py:253:        # User has already captured this specific flag; the rest of
backend/app/services/flag_submission.py:254:        # the challenge may still be open. 409 keeps the single-flag
backend/app/services/flag_submission.py:258:    return await _record_multi_flag_pass(
backend/app/services/flag_submission.py:261:        flag_defs=flag_defs,
backend/app/services/flag_submission.py:262:        matched_flag=matched,
backend/app/services/flag_submission.py:269:async def _record_multi_flag_pass(
backend/app/services/flag_submission.py:273:    flag_defs: list,
backend/app/services/flag_submission.py:274:    matched_flag,
backend/app/services/flag_submission.py:280:    points = await calculate_flag_points(
backend/app/services/flag_submission.py:281:        challenge, matched_flag, user.id, hint_used, db
backend/app/services/flag_submission.py:283:    is_first_blood_flag = await _is_first_blood_flag(
backend/app/services/flag_submission.py:284:        challenge.id, matched_flag.flag_id, db
backend/app/services/flag_submission.py:292:            flag_id=matched_flag.flag_id,
backend/app/services/flag_submission.py:294:            is_first_blood_flag=is_first_blood_flag,
backend/app/services/flag_submission.py:300:    # all-flags-captured query below.
backend/app/services/flag_submission.py:306:                select(SolvedFlag.flag_id).where(
backend/app/services/flag_submission.py:313:    declared_ids = {f.flag_id for f in flag_defs}
backend/app/services/flag_submission.py:350:                f"You captured every flag in '{challenge.title}' "
backend/app/services/flag_submission.py:360:        "is_first_blood": is_first_blood_flag,
backend/app/services/flag_submission.py:361:        "flag_id": matched_flag.flag_id,
backend/app/services/flag_submission.py:374:        # challenge total. ``is_first_blood`` is the per-flag value
backend/app/services/flag_submission.py:377:        payload=payload,
backend/app/services/flag_submission.py:389:        payload=payload,
backend/app/services/flag_submission.py:399:        is_first_blood=is_first_blood_flag,
backend/app/services/flag_submission.py:400:        flag_id=matched_flag.flag_id,
backend/app/services/flag_submission.py:456:    matched_flag_id: str | None = None,
backend/app/services/flag_submission.py:469:    # Phase 12 (slice 3): record per-flag attribution. Legacy
backend/app/services/flag_submission.py:473:    # ``flag_id`` column is constrained UNIQUE (user_id, challenge_id,
backend/app/services/flag_submission.py:474:    # flag_id) so the duplicate-submission path is handled by the
backend/app/services/flag_submission.py:476:    flag_id_value = matched_flag_id or "legacy"
backend/app/services/flag_submission.py:477:    is_first_blood_flag = await _is_first_blood_flag(
backend/app/services/flag_submission.py:478:        challenge.id, flag_id_value, db
backend/app/services/flag_submission.py:484:            flag_id=flag_id_value,
backend/app/services/flag_submission.py:486:            is_first_blood_flag=is_first_blood_flag,

 succeeded in 0ms:
backend/app/main.py:68:                role="admin",
backend/app/templates/reports/operator_report.html:38:            <span>Role: {{ user.role }}</span>
backend/app/models.py:26:class UserRole(str, enum.Enum):
backend/app/models.py:55:    role = Column(Enum(UserRole), default=UserRole.operator, nullable=False)
backend/app/services/auth.py:29:def create_access_token(user_id: int, role: str) -> str:
backend/app/services/auth.py:33:        "role": role,
backend/app/services/auth.py:61:async def get_current_user(
backend/app/services/auth.py:87:async def require_admin(current_user: User = Depends(get_current_user)) -> User:
backend/app/services/auth.py:88:    if current_user.role.value != "admin":
backend/app/services/auth.py:93:    return current_user
backend/app/services/mfa.py:171:        create_access_token(user.id, user.role.value),
backend/app/services/orchestration/sidecar.py:44:_SIDECAR_LABEL_KEY = "siege.role"
backend/app/schemas/user.py:50:    role: str
backend/app/schemas/user.py:66:    role: Optional[str] = None
backend/app/schemas/user.py:69:    @field_validator("role")
backend/app/schemas/user.py:71:    def _role(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/user.py:73:            raise ValueError("role must be 'operator' or 'admin'")
backend/app/schemas/v1/me.py:31:    role: str
backend/app/schemas/v1/auth.py:34:    role: str
backend/app/schemas/v1/auth.py:198:    (changing them is a separate flow with reverification). ``role``
backend/app/schemas/v1/admin.py:3:Wraps challenge CRUD, release, user role updates, and the seed
backend/app/schemas/v1/admin.py:149:# User role / status updates
backend/app/schemas/v1/admin.py:154:    role: Optional[str] = None
backend/app/schemas/v1/admin.py:159:    @field_validator("role")
backend/app/schemas/v1/admin.py:161:    def _role(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/v1/admin.py:163:            raise ValueError("role must be 'operator' or 'admin'")
backend/app/schemas/v1/admin.py:183:    role: str
backend/app/routers/notifications.py:7:from app.services.auth import get_current_user
backend/app/routers/notifications.py:16:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:21:        Notification.target_user_id == current_user.id,
backend/app/routers/notifications.py:57:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:67:    if not notification.is_global and notification.target_user_id != current_user.id:
backend/app/routers/notifications.py:78:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:86:                Notification.target_user_id == current_user.id,
backend/app/routers/notifications.py:100:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:107:                Notification.target_user_id == current_user.id,
backend/app/routers/auth.py:20:    get_current_user,
backend/app/routers/auth.py:87:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:97:            "role": user.role.value,
backend/app/routers/auth.py:169:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:179:            "role": user.role.value,
backend/app/routers/auth.py:212:    new_access = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:267:    current_user: User = Depends(get_current_user),
backend/app/routers/auth.py:271:        select(func.coalesce(func.sum(Solve.points_awarded), 0)).where(Solve.user_id == current_user.id)
backend/app/routers/auth.py:276:        select(func.count(Solve.id)).where(Solve.user_id == current_user.id)
backend/app/routers/auth.py:280:    streak_result = await db.execute(select(Streak).where(Streak.user_id == current_user.id))
backend/app/routers/auth.py:294:        "id": current_user.id,
backend/app/routers/auth.py:295:        "username": current_user.username,
backend/app/routers/auth.py:296:        "email": current_user.email,
backend/app/routers/auth.py:297:        "display_name": current_user.display_name,
backend/app/routers/auth.py:298:        "team": current_user.team.value if current_user.team else None,
backend/app/routers/auth.py:299:        "role": current_user.role.value,
backend/app/routers/auth.py:300:        "is_active": current_user.is_active,
backend/app/routers/auth.py:301:        "created_at": current_user.created_at.isoformat(),
backend/app/routers/auth.py:302:        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
backend/app/routers/writeups.py:11:from app.services.auth import get_current_user, require_admin
backend/app/routers/writeups.py:31:    current_user: User = Depends(get_current_user),
backend/app/routers/writeups.py:45:                Solve.user_id == current_user.id,
backend/app/routers/writeups.py:63:        user_id=current_user.id,
backend/app/routers/writeups.py:88:    current_user: User = Depends(get_current_user),
backend/app/routers/writeups.py:102:                Solve.user_id == current_user.id,
backend/app/routers/writeups.py:153:    current_user: User = Depends(get_current_user),
backend/app/routers/admin.py:67:                "role": user.role,
backend/app/routers/admin.py:102:        "role": user.role,
backend/app/routers/leaderboard.py:12:from app.services.auth import get_current_user
backend/app/routers/leaderboard.py:22:    current_user: User = Depends(get_current_user),
backend/app/routers/leaderboard.py:91:    current_user: User = Depends(get_current_user),
backend/app/routers/leaderboard.py:135:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/scoreboard.py:14:from app.services.auth import get_current_user
backend/app/routers/v1/scoreboard.py:24:    _viewer: User = Depends(get_current_user),
backend/app/routers/competitions.py:10:from app.services.auth import get_current_user, require_admin
backend/app/routers/competitions.py:47:    current_user: User = Depends(get_current_user),
backend/app/routers/competitions.py:93:    current_user: User = Depends(get_current_user),
backend/app/routers/competitions.py:133:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/webhooks.py:3:Phase 12 (slice 5). All endpoints require admin role via
backend/app/routers/v1/webhooks.py:42:    responses={403: {"description": "Admin role required"}},
backend/app/routers/v1/webhooks.py:67:    responses={403: {"description": "Admin role required"}},
backend/app/routers/v1/webhooks.py:90:        403: {"description": "Admin role required"},
backend/app/routers/v1/webhooks.py:108:        403: {"description": "Admin role required"},
backend/app/routers/v1/webhooks.py:165:        403: {"description": "Admin role required"},
backend/app/routers/v1/webhooks.py:209:        403: {"description": "Admin role required"},
backend/app/routers/v1/progress.py:25:from app.services.auth import get_current_user
backend/app/routers/v1/progress.py:37:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/progress.py:63:                    SolvedFlag.user_id == current_user.id,
backend/app/routers/v1/progress.py:73:        entries, totals = await _legacy_entries(challenge, current_user, db)
backend/app/routers/v1/submit.py:27:from app.services.auth import get_current_user
backend/app/routers/v1/submit.py:53:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/submit.py:59:            user=current_user,
backend/app/routers/challenges/browse.py:12:from app.services.auth import get_current_user
backend/app/routers/challenges/browse.py:35:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/browse.py:39:        viewer=current_user,
backend/app/routers/challenges/browse.py:57:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/browse.py:60:    detail = await _service_get_detail(slug=slug, viewer=current_user, db=db)
backend/app/routers/v1/auth.py:78:    get_current_user,
backend/app/routers/v1/auth.py:103:        role=user.role.value,
backend/app/routers/v1/auth.py:209:        access_token=create_access_token(user.id, user.role.value),
backend/app/routers/v1/auth.py:344:        access_token=create_access_token(user.id, user.role.value),
backend/app/routers/v1/auth.py:386:    new_access = create_access_token(user.id, user.role.value)
backend/app/routers/v1/auth.py:444:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:446:    return _to_auth_user(current_user)
backend/app/routers/v1/auth.py:613:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:618:    if not verify_password(payload.current_password, current_user.hashed_password):
backend/app/routers/v1/auth.py:623:            actor_id=current_user.id,
backend/app/routers/v1/auth.py:625:            resource_id=current_user.id,
backend/app/routers/v1/auth.py:632:    current_user.hashed_password = hash_password(payload.new_password)
backend/app/routers/v1/auth.py:637:        actor_id=current_user.id,
backend/app/routers/v1/auth.py:639:        resource_id=current_user.id,
backend/app/routers/v1/auth.py:651:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:659:        return _to_auth_user(current_user)
backend/app/routers/v1/auth.py:665:        setattr(current_user, field, value)
backend/app/routers/v1/auth.py:671:        actor_id=current_user.id,
backend/app/routers/v1/auth.py:673:        resource_id=current_user.id,
backend/app/routers/v1/auth.py:680:    await db.refresh(current_user)
backend/app/routers/v1/auth.py:681:    return _to_auth_user(current_user)
backend/app/routers/v1/auth.py:696:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:707:    result = await start_enrolment(db, current_user)
backend/app/routers/v1/auth.py:712:        actor_id=current_user.id,
backend/app/routers/v1/auth.py:714:        resource_id=current_user.id,
backend/app/routers/v1/auth.py:736:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:748:        result = await confirm_enrolment(db, current_user, payload.code)
backend/app/routers/v1/auth.py:754:            actor_id=current_user.id,
backend/app/routers/v1/auth.py:756:            resource_id=current_user.id,
backend/app/routers/v1/auth.py:767:        actor_id=current_user.id,
backend/app/routers/v1/auth.py:769:        resource_id=current_user.id,
backend/app/routers/v1/auth.py:792:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:797:    if not verify_password(payload.password, current_user.hashed_password):
backend/app/routers/v1/auth.py:802:            actor_id=current_user.id,
backend/app/routers/v1/auth.py:804:            resource_id=current_user.id,
backend/app/routers/v1/auth.py:812:        await disable_mfa(db, current_user, payload.code)
backend/app/routers/v1/auth.py:818:            actor_id=current_user.id,
backend/app/routers/v1/auth.py:820:            resource_id=current_user.id,
backend/app/routers/v1/auth.py:831:        actor_id=current_user.id,
backend/app/routers/v1/auth.py:833:        resource_id=current_user.id,
backend/app/routers/v1/auth.py:969:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:984:    if not current_user.email_verified:
backend/app/routers/v1/auth.py:985:        cleartext = await issue_verify_token(db, current_user)
backend/app/routers/v1/auth.py:991:            to=current_user.email,
backend/app/routers/v1/auth.py:994:                f"Hi {current_user.display_name or current_user.username},\n\n"
backend/app/routers/v1/auth.py:1003:            actor_id=current_user.id,
backend/app/routers/v1/auth.py:1005:            resource_id=current_user.id,
backend/app/routers/instances.py:13:from app.services.auth import get_current_user
backend/app/routers/instances.py:54:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:71:            current_user.id, challenge, db, redis_client
backend/app/routers/instances.py:85:        actor_id=current_user.id,
backend/app/routers/instances.py:115:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:126:    if instance.user_id != current_user.id:
backend/app/routers/instances.py:138:        actor_id=current_user.id,
backend/app/routers/instances.py:151:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:157:            ChallengeInstance.user_id == current_user.id,
backend/app/routers/instances.py:200:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:211:    if instance.user_id != current_user.id:
backend/app/routers/instances.py:224:            current_user.id, challenge, db, redis_client
backend/app/routers/instances.py:238:        actor_id=current_user.id,
backend/app/routers/v1/attack_coverage.py:12:from app.services.auth import get_current_user
backend/app/routers/v1/attack_coverage.py:19:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/attack_coverage.py:23:        db, viewer_id=current_user.id
backend/app/routers/challenges/engagement.py:14:from app.services.auth import get_current_user
backend/app/routers/challenges/engagement.py:35:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/engagement.py:41:            user=current_user,
backend/app/routers/challenges/engagement.py:66:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/engagement.py:81:            user=current_user, challenge=challenge, db=db
backend/app/routers/challenges/engagement.py:124:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/engagement.py:127:    challenge = await _require_solved_challenge(slug, current_user.id, db)
backend/app/routers/challenges/engagement.py:130:            user_id=current_user.id,
backend/app/routers/stats.py:9:from app.services.auth import get_current_user, require_admin
backend/app/routers/stats.py:16:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:92:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:142:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:181:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:184:    if current_user.id != user_id and current_user.role != "admin":
backend/app/routers/v1/challenges.py:28:from app.services.auth import get_current_user
backend/app/routers/v1/challenges.py:49:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/challenges.py:62:    raw = await list_challenges(viewer=current_user, filters=filters, db=db)
backend/app/routers/v1/challenges.py:74:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/challenges.py:77:    raw = await get_challenge_detail(slug=slug, viewer=current_user, db=db)
backend/app/routers/v1/workstation.py:25:from app.services.auth import get_current_user
backend/app/routers/v1/workstation.py:111:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/workstation.py:113:    d = ws.get_status(user_id=current_user.id)
backend/app/routers/v1/workstation.py:115:        **_to_status(d, _public_host(request), _public_scheme(request), proxied=_is_proxied(request), user_id=current_user.id)
backend/app/routers/v1/workstation.py:122:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/workstation.py:126:        d = ws.launch(user_id=current_user.id)
backend/app/routers/v1/workstation.py:140:                actor_id=current_user.id,
backend/app/routers/v1/workstation.py:164:            user_id=current_user.id,
backend/app/routers/v1/workstation.py:173:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/workstation.py:176:    stopped = ws.stop(user_id=current_user.id)
backend/app/routers/v1/workstation.py:177:    d = ws.get_status(user_id=current_user.id)
backend/app/routers/v1/workstation.py:185:                actor_id=current_user.id,
backend/app/routers/v1/workstation.py:196:        **_to_status(d, _public_host(request), _public_scheme(request), proxied=_is_proxied(request), user_id=current_user.id)
backend/app/routers/v1/hints.py:17:from app.services.auth import get_current_user
backend/app/routers/v1/hints.py:38:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/hints.py:53:            user=current_user, challenge=challenge, db=db
backend/app/routers/v1/me.py:34:    get_current_user,
backend/app/routers/v1/me.py:48:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/me.py:52:        db, viewer_id=current_user.id
backend/app/routers/v1/me.py:56:        id=current_user.id,
backend/app/routers/v1/me.py:57:        username=current_user.username,
backend/app/routers/v1/me.py:58:        display_name=current_user.display_name or current_user.username,
backend/app/routers/v1/me.py:59:        email=current_user.email,
backend/app/routers/v1/me.py:60:        role=current_user.role.value,
backend/app/routers/v1/me.py:61:        team=current_user.team.value if current_user.team else None,
backend/app/routers/v1/me.py:62:        is_active=current_user.is_active,
backend/app/routers/v1/me.py:63:        created_at=current_user.created_at,
backend/app/routers/v1/me.py:93:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/me.py:111:    profile = _row_dict(current_user, exclude=("hashed_password",))
backend/app/routers/v1/me.py:114:        await db.execute(select(Solve).where(Solve.user_id == current_user.id))
backend/app/routers/v1/me.py:118:            select(SolvedFlag).where(SolvedFlag.user_id == current_user.id)
backend/app/routers/v1/me.py:124:                ChallengeInstance.user_id == current_user.id
backend/app/routers/v1/me.py:130:            select(Writeup).where(Writeup.user_id == current_user.id)
backend/app/routers/v1/me.py:135:            select(HintUnlock).where(HintUnlock.user_id == current_user.id)
backend/app/routers/v1/me.py:142:                AuditLedger.actor_id == str(current_user.id),
backend/app/routers/v1/me.py:151:        actor_id=current_user.id,
backend/app/routers/v1/me.py:153:        resource_id=current_user.id,
backend/app/routers/v1/me.py:186:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/me.py:211:    if not verify_password(payload.password, current_user.hashed_password):
backend/app/routers/v1/me.py:214:    user_id = current_user.id
backend/app/routers/v1/me.py:215:    current_user.email = f"deleted-{user_id}@deleted.local"
backend/app/routers/v1/me.py:216:    current_user.username = f"deleted_{user_id}"
backend/app/routers/v1/me.py:217:    current_user.display_name = "deleted user"
backend/app/routers/v1/me.py:218:    current_user.hashed_password = hash_password(secrets.token_hex(32))
backend/app/routers/v1/me.py:219:    current_user.is_active = False
backend/app/routers/v1/me.py:220:    current_user.team = None
backend/app/routers/v1/me.py:221:    current_user.last_login = None
backend/app/routers/v1/leaderboard.py:33:from app.services.auth import get_current_user
backend/app/routers/v1/leaderboard.py:41:    _viewer: User = Depends(get_current_user),
backend/app/routers/v1/leaderboard.py:89:    _viewer: User = Depends(get_current_user),
backend/app/routers/v1/admin.py:10:- ``PUT    /api/v1/admin/users/{user_id}``      — role/team/active
backend/app/routers/v1/admin.py:36:    UserRole,
backend/app/routers/v1/admin.py:82:        role=u.role.value,
backend/app/routers/v1/admin.py:97:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:146:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:209:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:285:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:313:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:373:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:447:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:464:    if "role" in updates and updates["role"] is not None:
backend/app/routers/v1/admin.py:465:        updates["role"] = UserRole(updates["role"])
backend/app/routers/v1/admin.py:484:        403: {"description": "Admin role required"},

exec
/bin/bash -lc "rg -n \"@router\\.(get|post|put|patch|delete)|Depends\\(get_current_user|require_admin|admin|HTTPException|subprocess|shell=True|os\\.system|eval\\(|exec\\(|docker|requests\\.|httpx\\.|secret|password|token|Authorization|Depends\\(\" backend/app/routers backend/app/services" in /data/projects/seige-range
 succeeded in 0ms:
backend/app/services/validator_registry.py:17:Sandboxing — ``asyncio.timeout`` enforcement, subprocess pool — lives
backend/app/services/orchestrator.py:6:removal in Phase 12 alongside the rest of the legacy admin surface.
backend/app/services/orchestrator.py:11:    get_docker_client,
backend/app/services/orchestrator.py:19:    "get_docker_client",
backend/app/services/auth.py:3:from fastapi import Depends, HTTPException, Request, status
backend/app/services/auth.py:4:from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
backend/app/services/auth.py:21:def hash_password(password: str) -> str:
backend/app/services/auth.py:22:    return pwd_context.hash(password)
backend/app/services/auth.py:25:def verify_password(plain_password: str, hashed_password: str) -> bool:
backend/app/services/auth.py:26:    return pwd_context.verify(plain_password, hashed_password)
backend/app/services/auth.py:29:def create_access_token(user_id: int, role: str) -> str:
backend/app/services/auth.py:40:def create_refresh_token(user_id: int) -> str:
backend/app/services/auth.py:50:def decode_token(token: str) -> dict:
backend/app/services/auth.py:52:        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
backend/app/services/auth.py:55:        raise HTTPException(
backend/app/services/auth.py:57:            detail="Invalid or expired token",
backend/app/services/auth.py:62:    credentials: HTTPAuthorizationCredentials = Depends(security),
backend/app/services/auth.py:63:    db: AsyncSession = Depends(get_db),
backend/app/services/auth.py:66:        raise HTTPException(
backend/app/services/auth.py:70:    payload = decode_token(credentials.credentials)
backend/app/services/auth.py:72:        raise HTTPException(
backend/app/services/auth.py:74:            detail="Invalid token type",
backend/app/services/auth.py:80:        raise HTTPException(
backend/app/services/auth.py:87:async def require_admin(current_user: User = Depends(get_current_user)) -> User:
backend/app/services/auth.py:88:    if current_user.role.value != "admin":
backend/app/services/auth.py:89:        raise HTTPException(
backend/app/services/auth.py:100:        raise HTTPException(
backend/app/routers/notifications.py:1:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/notifications.py:12:@router.get("/")
backend/app/routers/notifications.py:16:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:17:    db: AsyncSession = Depends(get_db),
backend/app/routers/notifications.py:54:@router.put("/{notification_id}/read")
backend/app/routers/notifications.py:57:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:58:    db: AsyncSession = Depends(get_db),
backend/app/routers/notifications.py:65:        raise HTTPException(status_code=404, detail="Notification not found.")
backend/app/routers/notifications.py:68:        raise HTTPException(status_code=403, detail="Access denied.")
backend/app/routers/notifications.py:76:@router.put("/read-all")
backend/app/routers/notifications.py:78:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:79:    db: AsyncSession = Depends(get_db),
backend/app/routers/notifications.py:98:@router.get("/unread-count")
backend/app/routers/notifications.py:100:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:101:    db: AsyncSession = Depends(get_db),
backend/app/services/validator_subprocess_runner.py:1:"""Child-process entrypoint for ``requires_subprocess=True`` validators.
backend/app/services/validator_subprocess_runner.py:3:Run as ``python -m app.services.validator_subprocess_runner``. The
backend/app/services/validator_subprocess_runner.py:4:parent (``run_validator_subprocess`` in :mod:`validator_sandbox`) writes
backend/app/services/validator_subprocess_runner.py:172:if __name__ == "__main__":  # pragma: no cover — exercised via subprocess
backend/app/services/scheduler.py:43:            # Reconcile orphans whose docker container vanished
backend/app/services/scheduler.py:67:    """Tier-4 cheat-resistance: raise admin notifications when an
backend/app/services/scheduler.py:167:    broadcast tagged ``audit_tamper`` so admins see it on the
backend/app/services/scheduler.py:236:    so admins see it in the NotificationDropdown.
backend/app/services/scheduler.py:326:    # submissions and surface admin notifications.
backend/app/services/backup.py:9:2. Builds a ``pg_dump`` subprocess against
backend/app/services/backup.py:19:on the admin drawer.
backend/app/services/backup.py:21:Tests stub the subprocess so we never spawn a real ``pg_dump``;
backend/app/services/backup.py:74:    if p.password:
backend/app/services/backup.py:75:        out["PGPASSWORD"] = p.password
backend/app/services/backup.py:147:        proc = await asyncio.create_subprocess_shell(
backend/app/services/backup.py:150:            stdout=asyncio.subprocess.DEVNULL,
backend/app/services/backup.py:151:            stderr=asyncio.subprocess.PIPE,
backend/app/services/backup.py:156:            ok=False, error=f"subprocess error: {type(exc).__name__}: {exc}"
backend/app/services/cheat_detector.py:5:actor, and raises an admin notification when a single actor crosses
backend/app/services/cheat_detector.py:113:                f"/admin → Audit log → filter by actor_id={actor_id}."
backend/app/services/cheat_detector.py:116:            is_global=False,  # admin-only — surfaced via /admin
backend/app/routers/auth.py:5:from fastapi import APIRouter, Depends, HTTPException, Request, status
backend/app/routers/auth.py:17:    create_access_token,
backend/app/routers/auth.py:18:    create_refresh_token,
backend/app/routers/auth.py:19:    decode_token,
backend/app/routers/auth.py:21:    hash_password,
backend/app/routers/auth.py:23:    verify_password,
backend/app/routers/auth.py:42:@router.post("/register", status_code=status.HTTP_201_CREATED)
backend/app/routers/auth.py:46:    db: AsyncSession = Depends(get_db),
backend/app/routers/auth.py:50:    password = data.password
backend/app/routers/auth.py:58:        raise HTTPException(status_code=409, detail="Email or username already taken")
backend/app/routers/auth.py:63:        hashed_password=hash_password(password),
backend/app/routers/auth.py:87:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:88:    refresh_token = create_refresh_token(user.id)
backend/app/routers/auth.py:101:        "access_token": access_token,
backend/app/routers/auth.py:102:        "refresh_token": refresh_token,
backend/app/routers/auth.py:106:@router.post("/login")
backend/app/routers/auth.py:110:    db: AsyncSession = Depends(get_db),
backend/app/routers/auth.py:111:    redis_client=Depends(get_redis),
backend/app/routers/auth.py:114:    password = data.password
backend/app/routers/auth.py:122:    if not user or not verify_password(password, user.hashed_password):
backend/app/routers/auth.py:134:                "reason": "bad_password" if user else "unknown_user",
backend/app/routers/auth.py:139:        raise HTTPException(status_code=401, detail="Invalid credentials")
backend/app/routers/auth.py:153:        raise HTTPException(status_code=403, detail="Account is disabled")
backend/app/routers/auth.py:169:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:170:    refresh_token = create_refresh_token(user.id)
backend/app/routers/auth.py:184:        "access_token": access_token,
backend/app/routers/auth.py:185:        "refresh_token": refresh_token,
backend/app/routers/auth.py:189:@router.post("/refresh", response_model=AccessTokenResponse)
backend/app/routers/auth.py:193:    redis_client=Depends(get_redis),
backend/app/routers/auth.py:194:    db: AsyncSession = Depends(get_db),
backend/app/routers/auth.py:196:    token = data.refresh_token
backend/app/routers/auth.py:198:    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
backend/app/routers/auth.py:200:        raise HTTPException(status_code=401, detail="Token has been revoked")
backend/app/routers/auth.py:202:    payload = decode_token(token)
backend/app/routers/auth.py:204:        raise HTTPException(status_code=401, detail="Invalid token type")
backend/app/routers/auth.py:210:        raise HTTPException(status_code=401, detail="User not found")
backend/app/routers/auth.py:212:    new_access = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:224:    return {"access_token": new_access, "token_type": "bearer"}
backend/app/routers/auth.py:227:@router.post("/logout", response_model=MessageResponse)
backend/app/routers/auth.py:231:    redis_client=Depends(get_redis),
backend/app/routers/auth.py:232:    db: AsyncSession = Depends(get_db),
backend/app/routers/auth.py:234:    token = data.refresh_token
backend/app/routers/auth.py:236:    if token:
backend/app/routers/auth.py:238:            payload = decode_token(token)
backend/app/routers/auth.py:242:                await redis_client.set(f"siege:blacklist:{token}", "1", ex=ttl)
backend/app/routers/auth.py:258:        payload={"token_revoked": bool(token)},
backend/app/routers/auth.py:265:@router.get("/me")
backend/app/routers/auth.py:267:    current_user: User = Depends(get_current_user),
backend/app/routers/auth.py:268:    db: AsyncSession = Depends(get_db),
backend/app/services/webhook_dispatch.py:17:  from the subscription's ``secret``. Receivers verify by
backend/app/services/webhook_dispatch.py:22:  own ``httpx.AsyncClient`` so a slow receiver doesn't head-of-line
backend/app/services/webhook_dispatch.py:38:import secrets as _secrets
backend/app/services/webhook_dispatch.py:61:def generate_subscription_secret() -> str:
backend/app/services/webhook_dispatch.py:62:    """Return a fresh URL-safe random secret for a new subscription."""
backend/app/services/webhook_dispatch.py:64:    return _secrets.token_hex(_SECRET_BYTES)
backend/app/services/webhook_dispatch.py:67:def sign_body(secret: str, body: bytes) -> str:
backend/app/services/webhook_dispatch.py:75:    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
backend/app/services/webhook_dispatch.py:90:    each subscription's secret, and POSTs concurrently. The function
backend/app/services/webhook_dispatch.py:96:    omit it and a fresh ``httpx.AsyncClient`` is used per attempt.
backend/app/services/webhook_dispatch.py:103:    delivery_id = _secrets.token_hex(8)
backend/app/services/webhook_dispatch.py:190:    return httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_S)
backend/app/services/webhook_dispatch.py:221:        _SIGNATURE_HEADER: sign_body(subscription.secret, body),
backend/app/services/webhook_dispatch.py:247:    except httpx.TimeoutException:
backend/app/services/webhook_dispatch.py:255:    except httpx.HTTPError as exc:
backend/app/services/webhook_dispatch.py:294:    subscription's *current* secret — rotating the secret therefore
backend/app/routers/writeups.py:4:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/writeups.py:11:from app.services.auth import get_current_user, require_admin
backend/app/routers/writeups.py:27:@router.post("/{slug}")
backend/app/routers/writeups.py:31:    current_user: User = Depends(get_current_user),
backend/app/routers/writeups.py:32:    db: AsyncSession = Depends(get_db),
backend/app/routers/writeups.py:39:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/routers/writeups.py:50:        raise HTTPException(
backend/app/routers/writeups.py:83:@router.get("/{slug}")
backend/app/routers/writeups.py:88:    current_user: User = Depends(get_current_user),
backend/app/routers/writeups.py:89:    db: AsyncSession = Depends(get_db),
backend/app/routers/writeups.py:96:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/routers/writeups.py:107:        raise HTTPException(
backend/app/routers/writeups.py:149:@router.post("/{writeup_id}/rate", response_model=WriteupRatingResponse)
backend/app/routers/writeups.py:153:    current_user: User = Depends(get_current_user),
backend/app/routers/writeups.py:154:    db: AsyncSession = Depends(get_db),
backend/app/routers/writeups.py:159:        raise HTTPException(status_code=404, detail="Writeup not found.")
backend/app/routers/writeups.py:176:@router.put("/{writeup_id}/approve")
backend/app/routers/writeups.py:179:    admin: User = Depends(require_admin),
backend/app/routers/writeups.py:180:    db: AsyncSession = Depends(get_db),
backend/app/routers/writeups.py:185:        raise HTTPException(status_code=404, detail="Writeup not found.")
backend/app/services/orchestration/profiles.py:32:    All fields are intentionally final; the launcher composes docker-py
backend/app/services/orchestration/profiles.py:39:    mem_limit: str  # docker-py format, e.g. "512m"
backend/app/services/email_verification.py:1:"""Email-verification token issue + redeem.
backend/app/services/email_verification.py:3:Sprint 9 Phase B. Mirrors the password-reset flow shape: a 32-byte
backend/app/services/email_verification.py:4:URL-safe secret is generated at register time, sha256-hashed at
backend/app/services/email_verification.py:8:TTL is longer than password-reset (24 hours) — users may not check
backend/app/services/email_verification.py:15:import secrets
backend/app/services/email_verification.py:32:def _hash_cleartext(token: str) -> str:
backend/app/services/email_verification.py:33:    return hashlib.sha256(token.encode("utf-8")).hexdigest()
backend/app/services/email_verification.py:36:async def issue_token(db: AsyncSession, user: User) -> str:
backend/app/services/email_verification.py:37:    """Generate a fresh single-use verification token.
backend/app/services/email_verification.py:44:    cleartext = secrets.token_urlsafe(32)
backend/app/services/email_verification.py:48:            token_hash=_hash_cleartext(cleartext),
backend/app/services/email_verification.py:59:async def redeem_token(db: AsyncSession, cleartext: str) -> User:
backend/app/services/email_verification.py:67:        raise InvalidVerificationToken("token missing")
backend/app/services/email_verification.py:69:    token_hash = _hash_cleartext(cleartext)
backend/app/services/email_verification.py:73:                EmailVerificationToken.token_hash == token_hash
backend/app/services/email_verification.py:78:        raise InvalidVerificationToken("token not found")
backend/app/services/email_verification.py:80:        raise InvalidVerificationToken("token already used")
backend/app/services/email_verification.py:82:        raise InvalidVerificationToken("token expired")
backend/app/services/email_verification.py:98:    "issue_token",
backend/app/services/email_verification.py:99:    "redeem_token",
backend/app/routers/admin.py:7:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/admin.py:16:from app.services.auth import require_admin
backend/app/routers/admin.py:19:router = APIRouter(prefix="/admin", tags=["admin"])
backend/app/routers/admin.py:22:@router.get("/users")
backend/app/routers/admin.py:26:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:27:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:80:@router.put("/users/{user_id}")
backend/app/routers/admin.py:84:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:85:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:90:        raise HTTPException(status_code=404, detail="User not found.")
backend/app/routers/admin.py:108:@router.get("/audit")
backend/app/routers/admin.py:116:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:117:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:174:@router.post("/seed")
backend/app/routers/admin.py:176:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:177:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:184:        raise HTTPException(
backend/app/routers/admin.py:237:@router.get("/system")
backend/app/routers/admin.py:239:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:240:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:256:        import docker
backend/app/routers/admin.py:258:        client = docker.from_env()
backend/app/routers/admin.py:278:@router.get("/reports/operator/{user_id}")
backend/app/routers/admin.py:281:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:282:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:287:        raise HTTPException(status_code=404, detail="User not found.")
backend/app/routers/admin.py:326:        raise HTTPException(
backend/app/services/orchestration/egress.py:4:deployment-wide allowlist at ``docker/egress-proxy/egress-allowlist.conf``
backend/app/services/orchestration/egress.py:7:into ``Challenge.docker_config["egress_allowlist"]`` and persisted on
backend/app/services/orchestration/egress.py:141:    challenge ``docker_config["egress_allowlist"]`` ride along.
backend/app/services/orchestration/egress.py:163:            (challenge.docker_config or {}).get("egress_allowlist") or []
backend/app/services/orchestration/egress.py:204:    docker_client_obj,
backend/app/services/orchestration/egress.py:212:    on any failure (container missing, signal rejected, docker socket
backend/app/services/orchestration/egress.py:218:    The docker-socket-proxy ACL needs ``CONTAINERS=1`` + ``POST=1``
backend/app/services/orchestration/egress.py:224:        container = docker_client_obj.containers.get(proxy_container_name)
backend/app/services/orchestration/egress.py:243:    docker_client_obj=None,
backend/app/services/orchestration/egress.py:283:    # Only signal if we got a real docker client. Tests pass a stub;
backend/app/services/orchestration/egress.py:285:    if docker_client_obj is not None:
backend/app/services/orchestration/egress.py:287:            docker_client_obj, proxy_container_name=proxy_container_name
backend/app/services/workstation.py:18:**one-shot password** that the player must capture; if they lose
backend/app/services/workstation.py:24:import secrets
backend/app/services/workstation.py:31:from app.services.orchestration import docker_client
backend/app/services/workstation.py:36:# workstation surface is opt-in — admins who deploy it can patch
backend/app/services/workstation.py:39:# Network the workstation joins. ``None`` ⇒ docker's default
backend/app/services/workstation.py:62:def _new_password() -> str:
backend/app/services/workstation.py:64:    return "".join(secrets.choice(alphabet) for _ in range(PASSWORD_LEN))
backend/app/services/workstation.py:77:    one_shot_password: Optional[str] = None
backend/app/services/workstation.py:93:    client = docker_client.get()
backend/app/services/workstation.py:116:    password (the caller already has it from the original launch).
backend/app/services/workstation.py:123:    client = docker_client.get()
backend/app/services/workstation.py:137:    password = _new_password()
backend/app/services/workstation.py:150:            "SIEGE_WORKSTATION_PASSWORD": password,
backend/app/services/workstation.py:188:        one_shot_password=password,
backend/app/services/workstation.py:197:    and swallows any docker-side failure — workstation attachment
backend/app/services/workstation.py:201:    client = docker_client.get()
backend/app/services/workstation.py:235:    client = docker_client.get()
backend/app/services/workstation.py:274:    client = docker_client.get()
backend/app/services/validator_sandbox.py:17:   ``requires_subprocess=True`` (Phase 10's yara/sigma) run inside a
backend/app/services/validator_sandbox.py:46:# Per-call resource ceilings for the subprocess sandbox. CPU is the
backend/app/services/validator_sandbox.py:84:    if validator.requires_subprocess:
backend/app/services/validator_sandbox.py:85:        return await run_validator_subprocess(
backend/app/services/validator_sandbox.py:103:async def run_validator_subprocess(
backend/app/services/validator_sandbox.py:111:    """Run a ``requires_subprocess=True`` validator under rlimits.
backend/app/services/validator_sandbox.py:113:    Spawns ``python -m app.services.validator_subprocess_runner`` with
backend/app/services/validator_sandbox.py:129:            "subprocess sandbox requires a POSIX host (resource.setrlimit "
backend/app/services/validator_sandbox.py:147:    # We pass an explicit, minimal env (see ``_subprocess_env``) so
backend/app/services/validator_sandbox.py:153:    proc = await asyncio.create_subprocess_exec(
backend/app/services/validator_sandbox.py:157:        "app.services.validator_subprocess_runner",
backend/app/services/validator_sandbox.py:158:        stdin=asyncio.subprocess.PIPE,
backend/app/services/validator_sandbox.py:159:        stdout=asyncio.subprocess.PIPE,
backend/app/services/validator_sandbox.py:160:        stderr=asyncio.subprocess.PIPE,
backend/app/services/validator_sandbox.py:161:        env=_subprocess_env(),
backend/app/services/validator_sandbox.py:175:            f"validator {validator.name!r} subprocess exceeded "
backend/app/services/validator_sandbox.py:184:            f"validator {validator.name!r} subprocess killed by signal "
backend/app/services/validator_sandbox.py:190:            f"validator {validator.name!r} subprocess produced no output "
backend/app/services/validator_sandbox.py:198:            f"validator {validator.name!r} subprocess returned malformed "
backend/app/services/validator_sandbox.py:211:    message = str(response.get("message", "unknown subprocess error"))
backend/app/services/validator_sandbox.py:243:def _subprocess_env() -> dict[str, str]:
backend/app/services/validator_sandbox.py:246:    Drops every secret / connection-string we know about; preserves
backend/app/services/validator_sandbox.py:329:    "run_validator_subprocess",
backend/app/routers/leaderboard.py:19:@router.get("/")
backend/app/routers/leaderboard.py:22:    current_user: User = Depends(get_current_user),
backend/app/routers/leaderboard.py:23:    db: AsyncSession = Depends(get_db),
backend/app/routers/leaderboard.py:89:@router.get("/teams")
backend/app/routers/leaderboard.py:91:    current_user: User = Depends(get_current_user),
backend/app/routers/leaderboard.py:92:    db: AsyncSession = Depends(get_db),
backend/app/routers/leaderboard.py:132:@router.get("/weekly")
backend/app/routers/leaderboard.py:135:    current_user: User = Depends(get_current_user),
backend/app/routers/leaderboard.py:136:    db: AsyncSession = Depends(get_db),
backend/app/services/orchestration/launcher.py:9:    * Profile lookup: ``challenge.docker_config["profile"]`` keyed
backend/app/services/orchestration/launcher.py:12:    * Digest enforcement: ``challenge.docker_config["digest"]`` must
backend/app/services/orchestration/launcher.py:16:      on a profile-managed field. The launcher composes its docker-py
backend/app/services/orchestration/launcher.py:27:import secrets
backend/app/services/orchestration/launcher.py:31:import docker
backend/app/services/orchestration/launcher.py:39:from app.services.orchestration import docker_client, networking, profiles
backend/app/services/orchestration/launcher.py:62:    ``docker-py`` resolving an ``image@digest`` reference and the
backend/app/services/orchestration/launcher.py:72:    name = (challenge.docker_config or {}).get("profile", "default-strict")
backend/app/services/orchestration/launcher.py:77:    digest = (challenge.docker_config or {}).get("digest")
backend/app/services/orchestration/launcher.py:122:    base = challenge.docker_image
backend/app/services/orchestration/launcher.py:198:        "ports": {f"{challenge.docker_port}/tcp": host_port},
backend/app/services/orchestration/launcher.py:228:        container_name = f"siege-{user_id}-{challenge.slug}-{secrets.token_hex(3)}"
backend/app/services/orchestration/launcher.py:229:        client = docker_client.get()
backend/app/services/orchestration/launcher.py:250:                (challenge.docker_config or {}).get("egress_allowlist") or []
backend/app/services/orchestration/launcher.py:264:        image_ref = _image_ref(challenge, digest) if digest else challenge.docker_image
backend/app/services/orchestration/cleanup.py:12:import docker
backend/app/services/orchestration/cleanup.py:19:from app.services.orchestration import docker_client, networking
backend/app/services/orchestration/cleanup.py:38:    client = docker_client.get()
backend/app/services/orchestration/cleanup.py:69:def _stop_container(client: docker.DockerClient, container_id: str | None) -> None:
backend/app/services/orchestration/cleanup.py:74:    except docker.errors.NotFound:
backend/app/services/orchestration/cleanup.py:78:    except docker.errors.APIError as exc:
backend/app/services/orchestration/cleanup.py:82:    except docker.errors.APIError as exc:
backend/app/services/orchestration/cleanup.py:139:    ``docker.containers.list()`` plus one SELECT.
backend/app/services/orchestration/cleanup.py:141:    from app.services.orchestration import docker_client
backend/app/services/orchestration/cleanup.py:153:        client = docker_client.get()
backend/app/services/orchestration/cleanup.py:157:        logger.warning("orphan_sweep.docker_list_failed", error=str(exc))
backend/app/services/orchestration/cleanup.py:219:        client = docker_client.get()
backend/app/services/orchestration/cleanup.py:223:            "docker_status": container.status,
backend/app/services/orchestration/cleanup.py:227:        return {"docker_status": "unknown"}
backend/app/services/email.py:3:Sprint 6. Used by the password-reset flow today; will host
backend/app/services/email.py:23:back to the client (the password-reset endpoint maps
backend/app/services/email.py:126:            password=settings.SMTP_PASSWORD,
backend/app/services/orchestration/__init__.py:8:from app.services.orchestration import docker_client, networking, profiles
backend/app/services/orchestration/__init__.py:30:def get_docker_client():
backend/app/services/orchestration/__init__.py:32:    return docker_client.get()
backend/app/services/orchestration/__init__.py:43:    "docker_client",
backend/app/services/orchestration/__init__.py:45:    "get_docker_client",
backend/app/routers/competitions.py:3:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/competitions.py:10:from app.services.auth import get_current_user, require_admin
backend/app/routers/competitions.py:15:@router.post("/")
backend/app/routers/competitions.py:18:    admin: User = Depends(require_admin),
backend/app/routers/competitions.py:19:    db: AsyncSession = Depends(get_db),
backend/app/routers/competitions.py:30:        created_by=admin.id,
backend/app/routers/competitions.py:44:@router.get("/")
backend/app/routers/competitions.py:47:    current_user: User = Depends(get_current_user),
backend/app/routers/competitions.py:48:    db: AsyncSession = Depends(get_db),
backend/app/routers/competitions.py:90:@router.get("/{competition_id}")
backend/app/routers/competitions.py:93:    current_user: User = Depends(get_current_user),
backend/app/routers/competitions.py:94:    db: AsyncSession = Depends(get_db),
backend/app/routers/competitions.py:101:        raise HTTPException(status_code=404, detail="Competition not found.")
backend/app/routers/competitions.py:130:@router.get("/{competition_id}/scoreboard")
backend/app/routers/competitions.py:133:    current_user: User = Depends(get_current_user),
backend/app/routers/competitions.py:134:    db: AsyncSession = Depends(get_db),
backend/app/routers/competitions.py:141:        raise HTTPException(status_code=404, detail="Competition not found.")
backend/app/routers/competitions.py:147:@router.post("/{competition_id}/activate")
backend/app/routers/competitions.py:150:    admin: User = Depends(require_admin),
backend/app/routers/competitions.py:151:    db: AsyncSession = Depends(get_db),
backend/app/routers/competitions.py:158:        raise HTTPException(status_code=404, detail="Competition not found.")
backend/app/services/orchestration/networking.py:4:docker bridge per instance and attaches only the challenge container.
backend/app/services/orchestration/networking.py:9:The egress-proxy container is created out-of-band by docker-compose
backend/app/services/orchestration/networking.py:18:import secrets
backend/app/services/orchestration/networking.py:21:import docker
backend/app/services/orchestration/networking.py:31:    return f"siege-ch-{user_id}-{slug}-{secrets.token_hex(4)}"
backend/app/services/orchestration/networking.py:35:    client: docker.DockerClient,
backend/app/services/orchestration/networking.py:54:    Returns the docker-py ``Network`` object. Caller is responsible for
backend/app/services/orchestration/networking.py:88:def _attach_egress_proxy(client: docker.DockerClient, network) -> None:
backend/app/services/orchestration/networking.py:95:    except docker.errors.NotFound as exc:
backend/app/services/orchestration/networking.py:107:def remove_network(client: docker.DockerClient, network_name: str) -> None:
backend/app/services/orchestration/networking.py:111:    except docker.errors.NotFound:
backend/app/services/orchestration/networking.py:115:    except docker.errors.APIError as exc:
backend/app/services/mfa.py:4:secret generation, recovery-code lifecycle, login-step pending-token
backend/app/services/mfa.py:11:The MFA pending token is a short-lived JWT issued during the login
backend/app/services/mfa.py:15:access + refresh tokens.
backend/app/services/mfa.py:21:import secrets
backend/app/services/mfa.py:33:from app.services.auth import create_access_token, create_refresh_token
backend/app/services/mfa.py:49:    finished enrolment (mfa_secret unset OR mfa_enabled=False)."""
backend/app/services/mfa.py:54:    secret: str
backend/app/services/mfa.py:70:            secrets.choice(_RECOVERY_CODE_ALPHABET)
backend/app/services/mfa.py:83:    """Generate a fresh TOTP secret + provisioning URI for ``user``.
backend/app/services/mfa.py:85:    Stores the secret on the row but does NOT enable MFA yet —
backend/app/services/mfa.py:89:    rotates the secret (the previous one becomes garbage).
backend/app/services/mfa.py:92:    secret = pyotp.random_base32()
backend/app/services/mfa.py:93:    user.mfa_secret = secret
backend/app/services/mfa.py:97:    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
backend/app/services/mfa.py:102:        secret=secret, provisioning_uri=provisioning_uri
backend/app/services/mfa.py:116:    if not user.mfa_secret:
backend/app/services/mfa.py:119:    if not pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1):
backend/app/services/mfa.py:142:    if not user.mfa_enabled or not user.mfa_secret:
backend/app/services/mfa.py:148:    user.mfa_secret = None
backend/app/services/mfa.py:160:    On success: returns the (access_token, refresh_token) pair.
backend/app/services/mfa.py:164:    if not user.mfa_enabled or not user.mfa_secret:
backend/app/services/mfa.py:171:        create_access_token(user.id, user.role.value),
backend/app/services/mfa.py:172:        create_refresh_token(user.id),
backend/app/services/mfa.py:188:        if pyotp.TOTP(user.mfa_secret).verify(code_str, valid_window=1):
backend/app/services/mfa.py:210:# Pending-token plumbing for the two-step login flow
backend/app/services/mfa.py:212:def issue_mfa_pending_token(user_id: int) -> str:
backend/app/services/mfa.py:235:def decode_mfa_pending_token(token: str) -> int:
backend/app/services/mfa.py:236:    """Validate the pending token and return the user_id."""
backend/app/services/mfa.py:243:            token, settings.SECRET_KEY, algorithms=["HS256"]
backend/app/services/mfa.py:246:        raise InvalidMfaCode("invalid pending token") from exc
backend/app/services/mfa.py:248:        raise InvalidMfaCode("wrong token type")
backend/app/services/mfa.py:253:        raise InvalidMfaCode("malformed pending token") from exc
backend/app/services/mfa.py:262:    "decode_mfa_pending_token",
backend/app/services/mfa.py:264:    "issue_mfa_pending_token",
backend/app/services/password_reset.py:1:"""Password-reset token issue + redeem.
backend/app/services/password_reset.py:3:Sprint 6. Tokens are 32-byte cryptographically random secrets,
backend/app/services/password_reset.py:5:The cleartext is returned by :func:`issue_token` once and never
backend/app/services/password_reset.py:7:``password_reset_tokens.token_hash``.
backend/app/services/password_reset.py:10:later attempt with the same token fails validation.
backend/app/services/password_reset.py:16:import secrets
backend/app/services/password_reset.py:25:from app.services.auth import hash_password
backend/app/services/password_reset.py:36:def _hash_cleartext(token: str) -> str:
backend/app/services/password_reset.py:37:    return hashlib.sha256(token.encode("utf-8")).hexdigest()
backend/app/services/password_reset.py:40:async def issue_token(db: AsyncSession, user: User) -> str:
backend/app/services/password_reset.py:41:    """Generate a fresh single-use token for ``user``.
backend/app/services/password_reset.py:43:    Returns the cleartext token (URL-safe base64) for embedding in
backend/app/services/password_reset.py:45:    ``token_hash`` and TTL controlled by
backend/app/services/password_reset.py:51:    cleartext = secrets.token_urlsafe(32)
backend/app/services/password_reset.py:54:        token_hash=_hash_cleartext(cleartext),
backend/app/services/password_reset.py:65:async def redeem_token(
backend/app/services/password_reset.py:68:    new_password: str,
backend/app/services/password_reset.py:70:    """Validate ``cleartext`` and set ``new_password`` on the owner.
backend/app/services/password_reset.py:73:    expired, already-used). On success: marks token used, sets
backend/app/services/password_reset.py:74:    new password (hashed), flushes. Caller commits.
backend/app/services/password_reset.py:78:        raise InvalidResetToken("token missing")
backend/app/services/password_reset.py:79:    if len(new_password) < 8:
backend/app/services/password_reset.py:80:        raise InvalidResetToken("password too short")
backend/app/services/password_reset.py:82:    token_hash = _hash_cleartext(cleartext)
backend/app/services/password_reset.py:86:                PasswordResetToken.token_hash == token_hash
backend/app/services/password_reset.py:91:        raise InvalidResetToken("token not found")
backend/app/services/password_reset.py:93:        raise InvalidResetToken("token already used")
backend/app/services/password_reset.py:95:        raise InvalidResetToken("token expired")
backend/app/services/password_reset.py:103:    user.hashed_password = hash_password(new_password)
backend/app/services/password_reset.py:109:__all__ = ["InvalidResetToken", "issue_token", "redeem_token"]
backend/app/services/orchestration/forbidden.py:1:"""Refusal layer: reject docker-py kwargs that would break the sandbox.
backend/app/services/orchestration/forbidden.py:16:    """A docker-py kwarg violates the sandbox boundary."""
backend/app/services/orchestration/forbidden.py:48:    "/var/run/docker.sock",
backend/app/services/orchestration/forbidden.py:91:        # docker-py accepts list form for read-only binds; refuse the legacy
backend/app/services/orchestration/forbidden.py:108:    The launcher calls this after composing the final docker-py kwargs
backend/app/services/orchestration/sidecar.py:28:import secrets
backend/app/services/orchestration/sidecar.py:90:    return f"{_SIDECAR_NAME_PREFIX}-{safe[:48]}-{secrets.token_hex(3)}"
backend/app/services/orchestration/sidecar.py:94:    docker_client_obj,
backend/app/services/orchestration/sidecar.py:109:    challenge-container errors). On a docker-py error here, the
backend/app/services/orchestration/sidecar.py:124:    container = docker_client_obj.containers.run(
backend/app/services/orchestration/sidecar.py:151:    docker_client_obj,
backend/app/services/orchestration/sidecar.py:157:    any failure (container already gone, docker socket flapping). The
backend/app/services/orchestration/sidecar.py:165:        container = docker_client_obj.containers.get(container_id)
backend/app/routers/challenges/browse.py:7:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/challenges/browse.py:25:@router.get("/")
backend/app/routers/challenges/browse.py:35:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/browse.py:36:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/browse.py:54:@router.get("/{slug}")
backend/app/routers/challenges/browse.py:57:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/browse.py:58:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/browse.py:62:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/services/orchestration/docker_client.py:1:"""Long-lived Docker client wired through the docker-socket-proxy.
backend/app/services/orchestration/docker_client.py:14:import docker
backend/app/services/orchestration/docker_client.py:22:_client: Optional[docker.DockerClient] = None
backend/app/services/orchestration/docker_client.py:26:def get() -> docker.DockerClient:
backend/app/services/orchestration/docker_client.py:34:            _client = docker.DockerClient(
backend/app/services/orchestration/docker_client.py:39:                "docker.client.connected",
backend/app/services/orchestration/docker_client.py:58:                logger.warning("docker.client.close_failed", error=str(exc))
backend/app/services/orchestration/docker_client.py:62:def set_for_test(client: Optional[docker.DockerClient]) -> None:
backend/app/routers/challenges/admin.py:5:from fastapi import APIRouter, Depends, HTTPException, Request
backend/app/routers/challenges/admin.py:14:from app.services.auth import require_admin
backend/app/routers/challenges/admin.py:22:@router.post("/")
backend/app/routers/challenges/admin.py:25:    admin: User = Depends(require_admin),
backend/app/routers/challenges/admin.py:26:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/admin.py:32:        raise HTTPException(status_code=409, detail="Challenge slug already exists.")
backend/app/routers/challenges/admin.py:46:        docker_image=data.docker_image,
backend/app/routers/challenges/admin.py:47:        docker_port=data.docker_port,
backend/app/routers/challenges/admin.py:48:        docker_config=data.docker_config,
backend/app/routers/challenges/admin.py:66:@router.put("/{slug}")
backend/app/routers/challenges/admin.py:70:    admin: User = Depends(require_admin),
backend/app/routers/challenges/admin.py:71:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/admin.py:77:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/routers/challenges/admin.py:90:            raise HTTPException(
backend/app/routers/challenges/admin.py:102:            raise HTTPException(status_code=409, detail="Slug already exists.")
backend/app/routers/challenges/admin.py:114:@router.post("/{slug}/release")
backend/app/routers/challenges/admin.py:118:    admin: User = Depends(require_admin),
backend/app/routers/challenges/admin.py:119:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/admin.py:125:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/routers/challenges/admin.py:157:        actor_id=admin.id,
backend/app/routers/challenges/admin.py:184:@router.delete("/{slug}")
backend/app/routers/challenges/admin.py:187:    admin: User = Depends(require_admin),
backend/app/routers/challenges/admin.py:188:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/admin.py:194:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/routers/ws.py:6:from app.services.auth import decode_token
backend/app/routers/ws.py:15:    token: str = Query(None),
backend/app/routers/ws.py:17:    if not token:
backend/app/routers/ws.py:18:        await websocket.close(code=4001, reason="Missing authentication token")
backend/app/routers/ws.py:22:        payload = decode_token(token)
backend/app/routers/ws.py:25:            await websocket.close(code=4001, reason="Invalid token")
backend/app/routers/ws.py:28:        await websocket.close(code=4001, reason="Invalid or expired token")
backend/app/routers/challenges/engagement.py:5:from fastapi import APIRouter, Depends, HTTPException, Request
backend/app/routers/challenges/engagement.py:30:@router.post("/{slug}/submit", response_model=FlagResult)
backend/app/routers/challenges/engagement.py:35:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/engagement.py:36:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/engagement.py:37:    _rl=Depends(flag_rate_limit),
backend/app/routers/challenges/engagement.py:48:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/routers/challenges/engagement.py:50:        raise HTTPException(status_code=400, detail="Challenge already solved.")
backend/app/routers/challenges/engagement.py:52:        raise HTTPException(status_code=400, detail="Prerequisites not met.")
backend/app/routers/challenges/engagement.py:63:@router.post("/{slug}/hint")
backend/app/routers/challenges/engagement.py:66:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/engagement.py:67:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/engagement.py:77:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/routers/challenges/engagement.py:84:        raise HTTPException(status_code=400, detail="No hints available.")
backend/app/routers/challenges/engagement.py:86:        raise HTTPException(status_code=400, detail="All hints already unlocked.")
backend/app/routers/challenges/engagement.py:102:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/routers/challenges/engagement.py:113:        raise HTTPException(
backend/app/routers/challenges/engagement.py:120:@router.post("/{slug}/feedback")
backend/app/routers/challenges/engagement.py:124:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/engagement.py:125:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/engagement.py:142:        raise HTTPException(
backend/app/routers/health.py:43:@router.get("/health")
backend/app/routers/health.py:64:async def _probe_docker() -> None:
backend/app/routers/health.py:65:    # docker-py is sync; run in a thread so it doesn't block the loop
backend/app/routers/health.py:67:    # this through the long-lived client wired to the docker-socket-proxy
backend/app/routers/health.py:69:    from app.services.orchestration import docker_client
backend/app/routers/health.py:72:        client = docker_client.get()
backend/app/routers/health.py:81:    "docker": _probe_docker,
backend/app/routers/health.py:133:@router.get("/readyz")
backend/app/routers/health.py:145:@router.get("/metrics", include_in_schema=False)
backend/app/routers/health.py:169:@router.post("/csp-report", include_in_schema=False)
backend/app/services/audit/events.py:38:    AUTH_PASSWORD_RESET_REQUEST: Final = "auth.password.reset.request"
backend/app/services/audit/events.py:39:    AUTH_PASSWORD_RESET_REDEEM: Final = "auth.password.reset.redeem"
backend/app/services/audit/events.py:40:    AUTH_PASSWORD_CHANGE: Final = "auth.password.change"
backend/app/routers/stats.py:3:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/stats.py:9:from app.services.auth import get_current_user, require_admin
backend/app/routers/stats.py:14:@router.get("/overview")
backend/app/routers/stats.py:16:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:17:    db: AsyncSession = Depends(get_db),
backend/app/routers/stats.py:90:@router.get("/mitre")
backend/app/routers/stats.py:92:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:93:    db: AsyncSession = Depends(get_db),
backend/app/routers/stats.py:140:@router.get("/activity")
backend/app/routers/stats.py:142:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:143:    db: AsyncSession = Depends(get_db),
backend/app/routers/stats.py:178:@router.get("/user/{user_id}")
backend/app/routers/stats.py:181:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:182:    db: AsyncSession = Depends(get_db),
backend/app/routers/stats.py:184:    if current_user.id != user_id and current_user.role != "admin":
backend/app/routers/stats.py:185:        raise HTTPException(status_code=403, detail="Access denied.")
backend/app/routers/stats.py:190:        raise HTTPException(status_code=404, detail="User not found.")
backend/app/routers/challenges/__init__.py:5:actions: submit / hint / feedback), and ``admin`` (CRUD) — wired here
backend/app/routers/challenges/__init__.py:16:from app.routers.challenges import admin, browse, engagement
backend/app/routers/challenges/__init__.py:21:router.include_router(admin.router)
backend/app/routers/instances.py:4:from fastapi import APIRouter, Depends, HTTPException, Request
backend/app/routers/instances.py:35:def _launch_to_http(exc: Exception) -> HTTPException:
backend/app/routers/instances.py:38:        return HTTPException(status_code=409, detail=str(exc))
backend/app/routers/instances.py:40:        return HTTPException(status_code=409, detail=str(exc))
backend/app/routers/instances.py:42:        return HTTPException(status_code=409, detail=f"unknown profile: {exc}")
backend/app/routers/instances.py:44:        return HTTPException(status_code=503, detail=str(exc))
backend/app/routers/instances.py:46:        return HTTPException(status_code=400, detail=str(exc))
backend/app/routers/instances.py:47:    return HTTPException(status_code=500, detail="launch failed")
backend/app/routers/instances.py:50:@router.post("/{slug}/launch")
backend/app/routers/instances.py:54:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:55:    db: AsyncSession = Depends(get_db),
backend/app/routers/instances.py:56:    redis_client=Depends(get_redis),
backend/app/routers/instances.py:67:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/routers/instances.py:111:@router.delete("/{instance_id}")
backend/app/routers/instances.py:115:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:116:    db: AsyncSession = Depends(get_db),
backend/app/routers/instances.py:117:    redis_client=Depends(get_redis),
backend/app/routers/instances.py:124:        raise HTTPException(status_code=404, detail="Instance not found.")
backend/app/routers/instances.py:127:        raise HTTPException(status_code=403, detail="Not your instance.")
backend/app/routers/instances.py:132:        raise HTTPException(status_code=400, detail=str(e))
backend/app/routers/instances.py:149:@router.get("/")
backend/app/routers/instances.py:151:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:152:    db: AsyncSession = Depends(get_db),
backend/app/routers/instances.py:196:@router.post("/{instance_id}/reset")
backend/app/routers/instances.py:200:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:201:    db: AsyncSession = Depends(get_db),
backend/app/routers/instances.py:202:    redis_client=Depends(get_redis),
backend/app/routers/instances.py:209:        raise HTTPException(status_code=404, detail="Instance not found.")
backend/app/routers/instances.py:212:        raise HTTPException(status_code=403, detail="Not your instance.")
backend/app/routers/instances.py:219:        raise HTTPException(status_code=404, detail="Challenge not found.")
backend/app/services/challenge_loader/upsert.py:7:through the admin path after reviewing the diff.
backend/app/services/challenge_loader/upsert.py:92:    challenge.docker_image = manifest.container.image
backend/app/services/challenge_loader/upsert.py:93:    challenge.docker_port = manifest.container.port
backend/app/services/challenge_loader/upsert.py:94:    challenge.docker_config = {
backend/app/services/flag_dispatch.py:90:            # admin UI surfaces missing plugins via the registry's
backend/app/routers/v1/scoreboard.py:20:@router.get("/scoreboard", response_model=ScoreboardResponse)
backend/app/routers/v1/scoreboard.py:24:    _viewer: User = Depends(get_current_user),
backend/app/routers/v1/scoreboard.py:25:    db: AsyncSession = Depends(get_db),
backend/app/services/test_harness/runner.py:18:   spawns the resource-limited subprocess for
backend/app/services/test_harness/runner.py:19:   ``requires_subprocess=True`` validators.
backend/app/routers/v1/webhooks.py:1:"""``/api/v1/webhooks`` admin CRUD.
backend/app/routers/v1/webhooks.py:3:Phase 12 (slice 5). All endpoints require admin role via
backend/app/routers/v1/webhooks.py:4::func:`require_admin`. The create response surfaces the freshly-
backend/app/routers/v1/webhooks.py:5:generated signing secret **once**; subsequent reads omit it.
backend/app/routers/v1/webhooks.py:12:from fastapi import APIRouter, Depends, HTTPException, Query, status
backend/app/routers/v1/webhooks.py:28:from app.services.auth import require_admin
backend/app/routers/v1/webhooks.py:30:    generate_subscription_secret,
backend/app/routers/v1/webhooks.py:38:@router.post(
backend/app/routers/v1/webhooks.py:46:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:47:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:49:    secret = generate_subscription_secret()
backend/app/routers/v1/webhooks.py:51:        owner_user_id=admin.id,
backend/app/routers/v1/webhooks.py:54:        secret=secret,
backend/app/routers/v1/webhooks.py:61:    return _to_created(sub, secret)
backend/app/routers/v1/webhooks.py:64:@router.get(
backend/app/routers/v1/webhooks.py:70:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:71:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:86:@router.get(
backend/app/routers/v1/webhooks.py:96:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:97:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:103:@router.delete(
backend/app/routers/v1/webhooks.py:114:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:115:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:134:        raise HTTPException(status_code=404, detail="webhook not found")
backend/app/routers/v1/webhooks.py:152:def _to_created(sub: WebhookSubscription, secret: str) -> WebhookCreatedResponse:
backend/app/routers/v1/webhooks.py:154:    base["secret"] = secret
backend/app/routers/v1/webhooks.py:161:@router.get(
backend/app/routers/v1/webhooks.py:173:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:174:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:204:@router.post(
backend/app/routers/v1/webhooks.py:216:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:217:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:238:        raise HTTPException(status_code=404, detail="delivery not found")
backend/app/routers/v1/__init__.py:14:- ``POST/GET/DELETE /api/v1/webhooks`` — admin webhook CRUD (slice 5)
backend/app/routers/v1/__init__.py:25:    admin,
backend/app/routers/v1/__init__.py:41:router.include_router(admin.router)
backend/app/routers/v1/challenges.py:15:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/v1/challenges.py:39:@router.get("/challenges", response_model=PublicChallengeListResponse)
backend/app/routers/v1/challenges.py:49:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/challenges.py:50:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/challenges.py:71:@router.get("/challenges/{slug}", response_model=PublicChallengeDetail)
backend/app/routers/v1/challenges.py:74:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/challenges.py:75:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/challenges.py:79:        raise HTTPException(status_code=404, detail="challenge not found")
backend/app/routers/v1/progress.py:15:from fastapi import APIRouter, Depends, HTTPException
backend/app/routers/v1/progress.py:30:@router.get(
backend/app/routers/v1/progress.py:37:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/progress.py:38:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/progress.py:48:        raise HTTPException(status_code=404, detail="challenge not found")
backend/app/routers/v1/hints.py:10:from fastapi import APIRouter, Depends, HTTPException
backend/app/routers/v1/hints.py:28:@router.post(
backend/app/routers/v1/hints.py:38:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/hints.py:39:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/hints.py:49:        raise HTTPException(status_code=404, detail="challenge not found")
backend/app/routers/v1/hints.py:56:        raise HTTPException(status_code=409, detail="no hints available")
backend/app/routers/v1/hints.py:58:        raise HTTPException(status_code=409, detail="all hints already unlocked")
backend/app/routers/v1/submit.py:19:from fastapi import APIRouter, Depends, HTTPException, Request
backend/app/routers/v1/submit.py:39:@router.post(
backend/app/routers/v1/submit.py:53:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/submit.py:54:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/submit.py:55:    _rl=Depends(flag_rate_limit),
backend/app/routers/v1/submit.py:66:        raise HTTPException(status_code=404, detail="challenge not found")
backend/app/routers/v1/submit.py:72:        raise HTTPException(status_code=409, detail="challenge already solved")
backend/app/routers/v1/submit.py:81:        raise HTTPException(
backend/app/routers/v1/me.py:11:import secrets
backend/app/routers/v1/me.py:13:from fastapi import APIRouter, Depends, HTTPException, Request
backend/app/routers/v1/me.py:35:    hash_password,
backend/app/routers/v1/me.py:36:    verify_password,
backend/app/routers/v1/me.py:46:@router.get("/me", response_model=MeResponse)
backend/app/routers/v1/me.py:48:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/me.py:49:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/me.py:90:@router.get("/me/data")
backend/app/routers/v1/me.py:93:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/me.py:94:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/me.py:99:      - ``profile``: User row (no hashed_password)
backend/app/routers/v1/me.py:111:    profile = _row_dict(current_user, exclude=("hashed_password",))
backend/app/routers/v1/me.py:182:@router.delete("/me", response_model=AccountDeleteResponse)
backend/app/routers/v1/me.py:186:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/me.py:187:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/me.py:201:    - hashed_password → unguessable random hash (login disabled)
backend/app/routers/v1/me.py:205:    Pending password-reset tokens for the user are deleted.
backend/app/routers/v1/me.py:207:    Requires the current password in the body to defend against
backend/app/routers/v1/me.py:208:    drive-by deletes via stolen access tokens.
backend/app/routers/v1/me.py:211:    if not verify_password(payload.password, current_user.hashed_password):
backend/app/routers/v1/me.py:212:        raise HTTPException(status_code=401, detail="password incorrect")
backend/app/routers/v1/me.py:218:    current_user.hashed_password = hash_password(secrets.token_hex(32))
backend/app/routers/v1/auth.py:10:- ``POST /api/v1/auth/register`` — create user, return token pair.
backend/app/routers/v1/auth.py:11:- ``POST /api/v1/auth/login``    — authenticate, return token pair.
backend/app/routers/v1/auth.py:12:- ``POST /api/v1/auth/refresh``  — exchange refresh token for new access.
backend/app/routers/v1/auth.py:13:- ``POST /api/v1/auth/logout``   — revoke refresh token (best-effort).
backend/app/routers/v1/auth.py:16:Audit-ledger emit, account lockout, and refresh-token blacklist
backend/app/routers/v1/auth.py:26:from fastapi import APIRouter, Depends, HTTPException, Request, status
backend/app/routers/v1/auth.py:64:    decode_mfa_pending_token,
backend/app/routers/v1/auth.py:66:    issue_mfa_pending_token,
backend/app/routers/v1/auth.py:75:    create_access_token,
backend/app/routers/v1/auth.py:76:    create_refresh_token,
backend/app/routers/v1/auth.py:77:    decode_token,
backend/app/routers/v1/auth.py:79:    hash_password,
backend/app/routers/v1/auth.py:81:    verify_password,
backend/app/routers/v1/auth.py:113:@router.post(
backend/app/routers/v1/auth.py:122:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:130:        raise HTTPException(
backend/app/routers/v1/auth.py:138:        hashed_password=hash_password(payload.password),
backend/app/routers/v1/auth.py:161:    # Sprint 9 Phase B — issue an email-verification token and email
backend/app/routers/v1/auth.py:167:        issue_token as issue_verify_token,
backend/app/routers/v1/auth.py:172:        cleartext = await issue_verify_token(db, user)
backend/app/routers/v1/auth.py:175:            f"?token={cleartext}"
backend/app/routers/v1/auth.py:201:        # Don't fail register if SMTP / token issue blew up; the
backend/app/routers/v1/auth.py:209:        access_token=create_access_token(user.id, user.role.value),
backend/app/routers/v1/auth.py:210:        refresh_token=create_refresh_token(user.id),
backend/app/routers/v1/auth.py:214:@router.post(
backend/app/routers/v1/auth.py:218:        200: {"description": "Login success — token pair OR MFA pending"},
backend/app/routers/v1/auth.py:227:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:228:    redis_client=Depends(_get_redis),
backend/app/routers/v1/auth.py:230:    """Authenticate by email + password.
backend/app/routers/v1/auth.py:235:        ``{user, access_token, refresh_token, token_type}``).
backend/app/routers/v1/auth.py:237:        (``{mfa_required: true, mfa_pending_token: "..."}``). The
backend/app/routers/v1/auth.py:239:        pending token + the user's TOTP / recovery code to receive
backend/app/routers/v1/auth.py:240:        the real token pair.
backend/app/routers/v1/auth.py:248:    if not user or not verify_password(payload.password, user.hashed_password):
backend/app/routers/v1/auth.py:260:                "reason": "bad_password" if user else "unknown_user",
backend/app/routers/v1/auth.py:265:        raise HTTPException(status_code=401, detail="Invalid credentials")
backend/app/routers/v1/auth.py:279:        raise HTTPException(status_code=403, detail="Account is disabled")
backend/app/routers/v1/auth.py:299:        raise HTTPException(
backend/app/routers/v1/auth.py:306:    # pending token instead of the real pair. Login still counts as
backend/app/routers/v1/auth.py:309:    if user.mfa_enabled and user.mfa_secret:
backend/app/routers/v1/auth.py:326:            mfa_pending_token=issue_mfa_pending_token(user.id),
backend/app/routers/v1/auth.py:344:        access_token=create_access_token(user.id, user.role.value),
backend/app/routers/v1/auth.py:345:        refresh_token=create_refresh_token(user.id),
backend/app/routers/v1/auth.py:349:@router.post(
backend/app/routers/v1/auth.py:352:    responses={401: {"description": "Invalid or revoked refresh token"}},
backend/app/routers/v1/auth.py:357:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:358:    redis_client=Depends(_get_redis),
backend/app/routers/v1/auth.py:360:    token = payload.refresh_token
backend/app/routers/v1/auth.py:362:    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
backend/app/routers/v1/auth.py:364:        raise HTTPException(status_code=401, detail="Token has been revoked")
backend/app/routers/v1/auth.py:367:        decoded = decode_token(token)
backend/app/routers/v1/auth.py:368:    except HTTPException:
backend/app/routers/v1/auth.py:371:        raise HTTPException(status_code=401, detail="Invalid token")
backend/app/routers/v1/auth.py:374:        raise HTTPException(status_code=401, detail="Invalid token type")
backend/app/routers/v1/auth.py:379:        raise HTTPException(status_code=401, detail="Invalid token")
backend/app/routers/v1/auth.py:384:        raise HTTPException(status_code=401, detail="User not found")
backend/app/routers/v1/auth.py:386:    new_access = create_access_token(user.id, user.role.value)
backend/app/routers/v1/auth.py:398:    return AuthRefreshResponse(access_token=new_access)
backend/app/routers/v1/auth.py:401:@router.post("/logout", response_model=AuthLogoutResponse)
backend/app/routers/v1/auth.py:405:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:406:    redis_client=Depends(_get_redis),
backend/app/routers/v1/auth.py:408:    token = payload.refresh_token
backend/app/routers/v1/auth.py:410:    if token:
backend/app/routers/v1/auth.py:412:            decoded = decode_token(token)
backend/app/routers/v1/auth.py:417:                    f"siege:blacklist:{token}", "1", ex=ttl
backend/app/routers/v1/auth.py:435:        payload={"token_revoked": bool(token)},
backend/app/routers/v1/auth.py:442:@router.get("/me", response_model=AuthUser)
backend/app/routers/v1/auth.py:444:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:452:@router.post(
backend/app/routers/v1/auth.py:453:    "/forgot-password",
backend/app/routers/v1/auth.py:458:async def forgot_password_v1(
backend/app/routers/v1/auth.py:461:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:463:    """Issue a password-reset token and email the link.
backend/app/routers/v1/auth.py:478:    from app.services.password_reset import issue_token
backend/app/routers/v1/auth.py:488:        cleartext = await issue_token(db, user)
backend/app/routers/v1/auth.py:490:            f"{settings.frontend_url()}/reset-password"
backend/app/routers/v1/auth.py:491:            f"?token={cleartext}"
backend/app/routers/v1/auth.py:495:            f"Someone (hopefully you) requested a password reset on "
backend/app/routers/v1/auth.py:496:            f"siege-range. Click the link below to set a new password "
backend/app/routers/v1/auth.py:505:            subject="Reset your siege-range password",
backend/app/routers/v1/auth.py:539:            "If an account with that email exists, a password "
backend/app/routers/v1/auth.py:545:@router.post(
backend/app/routers/v1/auth.py:546:    "/reset-password",
backend/app/routers/v1/auth.py:548:    responses={400: {"description": "Invalid or expired reset token"}},
backend/app/routers/v1/auth.py:550:async def reset_password_v1(
backend/app/routers/v1/auth.py:553:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:555:    """Redeem a reset token and set a new password."""
backend/app/routers/v1/auth.py:563:    from app.services.password_reset import (
backend/app/routers/v1/auth.py:565:        redeem_token,
backend/app/routers/v1/auth.py:569:        user = await redeem_token(db, payload.token, payload.new_password)
backend/app/routers/v1/auth.py:584:        raise HTTPException(
backend/app/routers/v1/auth.py:585:            status_code=400, detail="invalid or expired token"
backend/app/routers/v1/auth.py:605:@router.post(
backend/app/routers/v1/auth.py:606:    "/change-password",
backend/app/routers/v1/auth.py:608:    responses={401: {"description": "Current password incorrect"}},
backend/app/routers/v1/auth.py:610:async def change_password_v1(
backend/app/routers/v1/auth.py:613:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:614:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:616:    """In-app password change. Requires current password."""
backend/app/routers/v1/auth.py:618:    if not verify_password(payload.current_password, current_user.hashed_password):
backend/app/routers/v1/auth.py:626:            payload={"success": False, "reason": "bad_current_password"},
backend/app/routers/v1/auth.py:630:        raise HTTPException(status_code=401, detail="current password incorrect")
backend/app/routers/v1/auth.py:632:    current_user.hashed_password = hash_password(payload.new_password)
backend/app/routers/v1/auth.py:647:@router.patch("/profile", response_model=AuthUser)
backend/app/routers/v1/auth.py:651:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:652:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:687:@router.post(
backend/app/routers/v1/auth.py:696:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:697:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:699:    """Generate a fresh TOTP secret + provisioning URI.
backend/app/routers/v1/auth.py:703:    MFA fully enabled rotates the secret to a new one and resets
backend/app/routers/v1/auth.py:720:        secret=result.secret,
backend/app/routers/v1/auth.py:725:@router.post(
backend/app/routers/v1/auth.py:736:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:737:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:761:        raise HTTPException(status_code=400, detail=str(exc))
backend/app/routers/v1/auth.py:780:@router.post(
backend/app/routers/v1/auth.py:792:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:793:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:795:    """Disable MFA after re-authenticating with password + code."""
backend/app/routers/v1/auth.py:797:    if not verify_password(payload.password, current_user.hashed_password):
backend/app/routers/v1/auth.py:805:            payload={"success": False, "reason": "bad_password"},
backend/app/routers/v1/auth.py:809:        raise HTTPException(status_code=401, detail="password incorrect")
backend/app/routers/v1/auth.py:825:        raise HTTPException(status_code=400, detail=str(exc))
backend/app/routers/v1/auth.py:841:@router.post(
backend/app/routers/v1/auth.py:845:        401: {"description": "Pending token invalid or code rejected"},
backend/app/routers/v1/auth.py:851:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:855:    Consumes the pending token from ``/auth/login`` (response body
backend/app/routers/v1/auth.py:857:    code). Returns the real access + refresh token pair on
backend/app/routers/v1/auth.py:864:        user_id = decode_mfa_pending_token(payload.mfa_pending_token)
backend/app/routers/v1/auth.py:866:        raise HTTPException(status_code=401, detail=str(exc))
backend/app/routers/v1/auth.py:872:        raise HTTPException(status_code=401, detail="user not found")
backend/app/routers/v1/auth.py:888:        raise HTTPException(status_code=401, detail="code rejected")
backend/app/routers/v1/auth.py:904:        access_token=access,
backend/app/routers/v1/auth.py:905:        refresh_token=refresh,
backend/app/routers/v1/auth.py:912:@router.post(
backend/app/routers/v1/auth.py:915:    responses={400: {"description": "Invalid or expired token"}},
backend/app/routers/v1/auth.py:920:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:922:    """Redeem an email-verification token and flip
backend/app/routers/v1/auth.py:927:        redeem_token,
backend/app/routers/v1/auth.py:931:        user = await redeem_token(db, payload.token)
backend/app/routers/v1/auth.py:944:        raise HTTPException(
backend/app/routers/v1/auth.py:945:            status_code=400, detail="invalid or expired token"
backend/app/routers/v1/auth.py:962:@router.post(
backend/app/routers/v1/auth.py:969:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:970:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:972:    """Issue a new verification token and email the link.
backend/app/routers/v1/auth.py:980:        issue_token as issue_verify_token,
backend/app/routers/v1/auth.py:985:        cleartext = await issue_verify_token(db, current_user)
backend/app/routers/v1/auth.py:988:            f"?token={cleartext}"
backend/app/routers/v1/admin.py:1:"""``/api/v1/admin/*`` — locked admin write surface.
backend/app/routers/v1/admin.py:6:- ``POST   /api/v1/admin/challenges``           — create
backend/app/routers/v1/admin.py:7:- ``PUT    /api/v1/admin/challenges/{slug}``    — update
backend/app/routers/v1/admin.py:8:- ``POST   /api/v1/admin/challenges/{slug}/release`` — release
backend/app/routers/v1/admin.py:9:- ``DELETE /api/v1/admin/challenges/{slug}``    — soft-delete
backend/app/routers/v1/admin.py:10:- ``PUT    /api/v1/admin/users/{user_id}``      — role/team/active
backend/app/routers/v1/admin.py:11:- ``POST   /api/v1/admin/seed``                 — seed from /challenges
backend/app/routers/v1/admin.py:13:The legacy ``/admin/*`` and ``/challenges/`` admin routes stay live;
backend/app/routers/v1/admin.py:24:from fastapi import APIRouter, Depends, HTTPException, Request, status
backend/app/routers/v1/admin.py:38:from app.schemas.v1.admin import (
backend/app/routers/v1/admin.py:51:from app.services.auth import require_admin
backend/app/routers/v1/admin.py:57:router = APIRouter(prefix="/admin", tags=["v1-admin"])
backend/app/routers/v1/admin.py:92:@router.post(
backend/app/routers/v1/admin.py:103:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:104:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:112:        raise HTTPException(
backend/app/routers/v1/admin.py:128:        docker_image=payload.docker_image,
backend/app/routers/v1/admin.py:129:        docker_port=payload.docker_port,
backend/app/routers/v1/admin.py:130:        docker_config=payload.docker_config,
backend/app/routers/v1/admin.py:142:@router.put(
backend/app/routers/v1/admin.py:155:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:156:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:162:        raise HTTPException(status_code=404, detail="Challenge not found")
backend/app/routers/v1/admin.py:175:            raise HTTPException(
backend/app/routers/v1/admin.py:189:            raise HTTPException(
backend/app/routers/v1/admin.py:205:@router.post(
backend/app/routers/v1/admin.py:216:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:217:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:223:        raise HTTPException(status_code=404, detail="Challenge not found")
backend/app/routers/v1/admin.py:253:        actor_id=admin.id,
backend/app/routers/v1/admin.py:281:@router.delete(
backend/app/routers/v1/admin.py:291:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:292:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:298:        raise HTTPException(status_code=404, detail="Challenge not found")
backend/app/routers/v1/admin.py:309:@router.get(
backend/app/routers/v1/admin.py:319:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:320:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:322:    """Admin-side full challenge view including docker fields.
backend/app/routers/v1/admin.py:325:    docker_image / docker_port / docker_config so competitors can't
backend/app/routers/v1/admin.py:326:    inspect challenge internals. The admin editor needs them.
backend/app/routers/v1/admin.py:333:        raise HTTPException(status_code=404, detail="Challenge not found")
backend/app/routers/v1/admin.py:350:        docker_image=chal.docker_image,
backend/app/routers/v1/admin.py:351:        docker_port=chal.docker_port,
backend/app/routers/v1/admin.py:352:        docker_config=dict(chal.docker_config or {}),
backend/app/routers/v1/admin.py:368:@router.post(
backend/app/routers/v1/admin.py:381:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:382:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:388:        raise HTTPException(status_code=404, detail="Challenge not found")
backend/app/routers/v1/admin.py:399:        raise HTTPException(
backend/app/routers/v1/admin.py:443:@router.put(
backend/app/routers/v1/admin.py:454:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:455:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:461:        raise HTTPException(status_code=404, detail="User not found")
backend/app/routers/v1/admin.py:480:@router.post(
backend/app/routers/v1/admin.py:489:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:490:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:494:        raise HTTPException(
backend/app/routers/v1/admin.py:532:            docker_image=data.get("docker_image", "alpine:3.19"),
backend/app/routers/v1/admin.py:533:            docker_port=data.get("docker_port", 8080),
backend/app/routers/v1/admin.py:534:            docker_config=data.get("docker_config", {}),
backend/app/routers/v1/leaderboard.py:39:@router.get("/leaderboard/teams", response_model=TeamLeaderboardResponse)
backend/app/routers/v1/leaderboard.py:41:    _viewer: User = Depends(get_current_user),
backend/app/routers/v1/leaderboard.py:42:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/leaderboard.py:85:@router.get("/leaderboard/weekly", response_model=WeeklyLeaderboardResponse)
backend/app/routers/v1/leaderboard.py:89:    _viewer: User = Depends(get_current_user),
backend/app/routers/v1/leaderboard.py:90:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/attack_coverage.py:17:@router.get("/attack-coverage", response_model=AttackCoverageResponse)
backend/app/routers/v1/attack_coverage.py:19:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/attack_coverage.py:20:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/workstation.py:16:from fastapi import APIRouter, Depends, HTTPException, Request
backend/app/routers/v1/workstation.py:48:    one_shot_password: Optional[str] = None
backend/app/routers/v1/workstation.py:108:@router.get("/status", response_model=WorkstationStatus)
backend/app/routers/v1/workstation.py:111:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/workstation.py:119:@router.post("/launch", response_model=WorkstationLaunchResponse)
backend/app/routers/v1/workstation.py:122:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/workstation.py:123:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/workstation.py:130:        raise HTTPException(status_code=503, detail=f"workstation unavailable: {exc}")
backend/app/routers/v1/workstation.py:133:    # workstation is idempotent and returns ``one_shot_password=None``.
backend/app/routers/v1/workstation.py:134:    if d.one_shot_password is not None:
backend/app/routers/v1/workstation.py:166:        one_shot_password=d.one_shot_password,
backend/app/routers/v1/workstation.py:170:@router.post("/stop", response_model=WorkstationStatus)
backend/app/routers/v1/workstation.py:173:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/workstation.py:174:    db: AsyncSession = Depends(get_db),

exec
/bin/bash -lc "nl -ba backend/app/routers/v1/webhooks.py | sed -n '1,230p'" in /data/projects/seige-range
 succeeded in 0ms:
     1	"""``/api/v1/webhooks`` admin CRUD.
     2	
     3	Phase 12 (slice 5). All endpoints require admin role via
     4	:func:`require_admin`. The create response surfaces the freshly-
     5	generated signing secret **once**; subsequent reads omit it.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	from typing import Optional
    11	
    12	from fastapi import APIRouter, Depends, HTTPException, Query, status
    13	from sqlalchemy import func, select
    14	from sqlalchemy.ext.asyncio import AsyncSession
    15	
    16	from app.database import get_db
    17	from app.models import User, WebhookDelivery, WebhookSubscription
    18	from app.schemas.v1.webhook_deliveries import (
    19	    WebhookDeliveryListResponse,
    20	    WebhookDeliveryResponse,
    21	)
    22	from app.schemas.v1.webhooks import (
    23	    WebhookCreateRequest,
    24	    WebhookCreatedResponse,
    25	    WebhookListResponse,
    26	    WebhookResponse,
    27	)
    28	from app.services.auth import require_admin
    29	from app.services.webhook_dispatch import (
    30	    generate_subscription_secret,
    31	    replay_delivery,
    32	)
    33	
    34	
    35	router = APIRouter()
    36	
    37	
    38	@router.post(
    39	    "/webhooks",
    40	    response_model=WebhookCreatedResponse,
    41	    status_code=status.HTTP_201_CREATED,
    42	    responses={403: {"description": "Admin role required"}},
    43	)
    44	async def create_webhook_v1(
    45	    payload: WebhookCreateRequest,
    46	    admin: User = Depends(require_admin),
    47	    db: AsyncSession = Depends(get_db),
    48	) -> WebhookCreatedResponse:
    49	    secret = generate_subscription_secret()
    50	    sub = WebhookSubscription(
    51	        owner_user_id=admin.id,
    52	        name=payload.name,
    53	        target_url=str(payload.target_url),
    54	        secret=secret,
    55	        events=list(payload.events),
    56	        is_active=True,
    57	    )
    58	    db.add(sub)
    59	    await db.commit()
    60	    await db.refresh(sub)
    61	    return _to_created(sub, secret)
    62	
    63	
    64	@router.get(
    65	    "/webhooks",
    66	    response_model=WebhookListResponse,
    67	    responses={403: {"description": "Admin role required"}},
    68	)
    69	async def list_webhooks_v1(
    70	    admin: User = Depends(require_admin),
    71	    db: AsyncSession = Depends(get_db),
    72	) -> WebhookListResponse:
    73	    rows = (
    74	        await db.execute(
    75	            select(WebhookSubscription).order_by(
    76	                WebhookSubscription.created_at.desc()
    77	            )
    78	        )
    79	    ).scalars().all()
    80	    return WebhookListResponse(
    81	        items=[_to_response(row) for row in rows],
    82	        total=len(rows),
    83	    )
    84	
    85	
    86	@router.get(
    87	    "/webhooks/{subscription_id}",
    88	    response_model=WebhookResponse,
    89	    responses={
    90	        403: {"description": "Admin role required"},
    91	        404: {"description": "Subscription not found"},
    92	    },
    93	)
    94	async def get_webhook_v1(
    95	    subscription_id: int,
    96	    admin: User = Depends(require_admin),
    97	    db: AsyncSession = Depends(get_db),
    98	) -> WebhookResponse:
    99	    sub = await _load(db, subscription_id)
   100	    return _to_response(sub)
   101	
   102	
   103	@router.delete(
   104	    "/webhooks/{subscription_id}",
   105	    status_code=status.HTTP_204_NO_CONTENT,
   106	    response_model=None,
   107	    responses={
   108	        403: {"description": "Admin role required"},
   109	        404: {"description": "Subscription not found"},
   110	    },
   111	)
   112	async def delete_webhook_v1(
   113	    subscription_id: int,
   114	    admin: User = Depends(require_admin),
   115	    db: AsyncSession = Depends(get_db),
   116	):
   117	    sub = await _load(db, subscription_id)
   118	    await db.delete(sub)
   119	    await db.commit()
   120	
   121	
   122	# ---------------------------------------------------------------------------
   123	# helpers
   124	# ---------------------------------------------------------------------------
   125	async def _load(db: AsyncSession, subscription_id: int) -> WebhookSubscription:
   126	    sub = (
   127	        await db.execute(
   128	            select(WebhookSubscription).where(
   129	                WebhookSubscription.id == subscription_id
   130	            )
   131	        )
   132	    ).scalars().first()
   133	    if sub is None:
   134	        raise HTTPException(status_code=404, detail="webhook not found")
   135	    return sub
   136	
   137	
   138	def _to_response(sub: WebhookSubscription) -> WebhookResponse:
   139	    return WebhookResponse(
   140	        id=sub.id,
   141	        name=sub.name,
   142	        target_url=sub.target_url,
   143	        events=list(sub.events or []),
   144	        is_active=bool(sub.is_active),
   145	        created_at=sub.created_at,
   146	        last_delivery_at=sub.last_delivery_at,
   147	        last_status=sub.last_status,
   148	        last_error=sub.last_error,
   149	    )
   150	
   151	
   152	def _to_created(sub: WebhookSubscription, secret: str) -> WebhookCreatedResponse:
   153	    base = _to_response(sub).model_dump()
   154	    base["secret"] = secret
   155	    return WebhookCreatedResponse(**base)
   156	
   157	
   158	# ---------------------------------------------------------------------------
   159	# Deliveries (slice 6)
   160	# ---------------------------------------------------------------------------
   161	@router.get(
   162	    "/webhooks/{subscription_id}/deliveries",
   163	    response_model=WebhookDeliveryListResponse,
   164	    responses={
   165	        403: {"description": "Admin role required"},
   166	        404: {"description": "Subscription not found"},
   167	    },
   168	)
   169	async def list_webhook_deliveries_v1(
   170	    subscription_id: int,
   171	    page: int = Query(1, ge=1, le=10_000),
   172	    per_page: int = Query(50, ge=1, le=200),
   173	    admin: User = Depends(require_admin),
   174	    db: AsyncSession = Depends(get_db),
   175	) -> WebhookDeliveryListResponse:
   176	    await _load(db, subscription_id)  # 404 if missing
   177	
   178	    total = (
   179	        await db.execute(
   180	            select(func.count(WebhookDelivery.id)).where(
   181	                WebhookDelivery.subscription_id == subscription_id
   182	            )
   183	        )
   184	    ).scalar() or 0
   185	
   186	    rows = (
   187	        await db.execute(
   188	            select(WebhookDelivery)
   189	            .where(WebhookDelivery.subscription_id == subscription_id)
   190	            .order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id.desc())
   191	            .offset((page - 1) * per_page)
   192	            .limit(per_page)
   193	        )
   194	    ).scalars().all()
   195	
   196	    return WebhookDeliveryListResponse(
   197	        items=[_to_delivery(r) for r in rows],
   198	        total=int(total),
   199	        page=page,
   200	        per_page=per_page,
   201	    )
   202	
   203	
   204	@router.post(
   205	    "/webhooks/{subscription_id}/deliveries/{delivery_id}/replay",
   206	    response_model=WebhookDeliveryResponse,
   207	    status_code=status.HTTP_201_CREATED,
   208	    responses={
   209	        403: {"description": "Admin role required"},
   210	        404: {"description": "Subscription or delivery not found"},
   211	    },
   212	)
   213	async def replay_webhook_delivery_v1(
   214	    subscription_id: int,
   215	    delivery_id: str,
   216	    admin: User = Depends(require_admin),
   217	    db: AsyncSession = Depends(get_db),
   218	) -> WebhookDeliveryResponse:
   219	    sub = await _load(db, subscription_id)
   220	
   221	    # The delivery_id is the ``X-Siege-Delivery-Id`` header value, not
   222	    # the integer row id. Pick the most recent attempt with that
   223	    # delivery_id on this subscription as the canonical replay
   224	    # source — any of them carries the same payload, and "most
   225	    # recent" is the one operators are most likely investigating.
   226	    delivery = (
   227	        await db.execute(
   228	            select(WebhookDelivery)
   229	            .where(
   230	                WebhookDelivery.subscription_id == subscription_id,

exec
/bin/bash -lc "nl -ba backend/app/routers/stats.py | sed -n '160,205p'" in /data/projects/seige-range
exec
/bin/bash -lc "nl -ba backend/app/routers/v1/auth.py | sed -n '605,760p'" in /data/projects/seige-range
exec
/bin/bash -lc "nl -ba backend/app/services/auth.py | sed -n '1,120p'" in /data/projects/seige-range
 succeeded in 0ms:
   160	    date_map: dict[str, dict[str, int]] = {}
   161	    for row in rows:
   162	        date_str = str(row.solve_date)
   163	        if date_str not in date_map:
   164	            date_map[date_str] = {"red_solves": 0, "blue_solves": 0}
   165	        if row.team == "red":
   166	            date_map[date_str]["red_solves"] = row.cnt
   167	        elif row.team == "blue":
   168	            date_map[date_str]["blue_solves"] = row.cnt
   169	
   170	    activity_list = [
   171	        {"date": date, "red_solves": data["red_solves"], "blue_solves": data["blue_solves"]}
   172	        for date, data in sorted(date_map.items())
   173	    ]
   174	
   175	    return activity_list
   176	
   177	
   178	@router.get("/user/{user_id}")
   179	async def user_stats(
   180	    user_id: int,
   181	    current_user: User = Depends(get_current_user),
   182	    db: AsyncSession = Depends(get_db),
   183	):
   184	    if current_user.id != user_id and current_user.role != "admin":
   185	        raise HTTPException(status_code=403, detail="Access denied.")
   186	
   187	    user_result = await db.execute(select(User).where(User.id == user_id))
   188	    user = user_result.scalars().first()
   189	    if not user:
   190	        raise HTTPException(status_code=404, detail="User not found.")
   191	
   192	    solves_by_category_result = await db.execute(
   193	        select(Challenge.category, func.count(Solve.id).label("cnt"))
   194	        .join(Challenge, Solve.challenge_id == Challenge.id)
   195	        .where(Solve.user_id == user_id)
   196	        .group_by(Challenge.category)
   197	    )
   198	    solves_by_category = [
   199	        {"category": row.category, "solve_count": row.cnt}
   200	        for row in solves_by_category_result.all()
   201	    ]
   202	
   203	    all_challenges_result = await db.execute(
   204	        select(Challenge).where(
   205	            Challenge.is_active == True, Challenge.is_released == True

 succeeded in 0ms:
   605	@router.post(
   606	    "/change-password",
   607	    response_model=ChangePasswordResponse,
   608	    responses={401: {"description": "Current password incorrect"}},
   609	)
   610	async def change_password_v1(
   611	    payload: ChangePasswordRequest,
   612	    request: Request,
   613	    current_user: User = Depends(get_current_user),
   614	    db: AsyncSession = Depends(get_db),
   615	) -> ChangePasswordResponse:
   616	    """In-app password change. Requires current password."""
   617	
   618	    if not verify_password(payload.current_password, current_user.hashed_password):
   619	        await audit_append(
   620	            db,
   621	            event_type=EventType.AUTH_PASSWORD_CHANGE,
   622	            actor_type=ActorType.USER,
   623	            actor_id=current_user.id,
   624	            resource_type="user",
   625	            resource_id=current_user.id,
   626	            payload={"success": False, "reason": "bad_current_password"},
   627	            **context_from_request(request),
   628	        )
   629	        await db.commit()
   630	        raise HTTPException(status_code=401, detail="current password incorrect")
   631	
   632	    current_user.hashed_password = hash_password(payload.new_password)
   633	    await audit_append(
   634	        db,
   635	        event_type=EventType.AUTH_PASSWORD_CHANGE,
   636	        actor_type=ActorType.USER,
   637	        actor_id=current_user.id,
   638	        resource_type="user",
   639	        resource_id=current_user.id,
   640	        payload={"success": True},
   641	        **context_from_request(request),
   642	    )
   643	    await db.commit()
   644	    return ChangePasswordResponse(message="Password changed.")
   645	
   646	
   647	@router.patch("/profile", response_model=AuthUser)
   648	async def update_profile_v1(
   649	    payload: ProfileUpdateRequest,
   650	    request: Request,
   651	    current_user: User = Depends(get_current_user),
   652	    db: AsyncSession = Depends(get_db),
   653	) -> AuthUser:
   654	    """Self-service mutation of display_name + team."""
   655	
   656	    updates = payload.model_dump(exclude_unset=True)
   657	    if not updates:
   658	        # No-op; return current shape.
   659	        return _to_auth_user(current_user)
   660	
   661	    if "team" in updates and updates["team"] is not None:
   662	        updates["team"] = TeamType(updates["team"])
   663	
   664	    for field, value in updates.items():
   665	        setattr(current_user, field, value)
   666	
   667	    await audit_append(
   668	        db,
   669	        event_type=EventType.AUTH_PROFILE_UPDATE,
   670	        actor_type=ActorType.USER,
   671	        actor_id=current_user.id,
   672	        resource_type="user",
   673	        resource_id=current_user.id,
   674	        payload={
   675	            "fields": list(updates.keys()),
   676	        },
   677	        **context_from_request(request),
   678	    )
   679	    await db.commit()
   680	    await db.refresh(current_user)
   681	    return _to_auth_user(current_user)
   682	
   683	
   684	# ---------------------------------------------------------------------------
   685	# MFA — Sprint 7 Phase C
   686	# ---------------------------------------------------------------------------
   687	@router.post(
   688	    "/mfa/enroll",
   689	    response_model=None,
   690	    responses={
   691	        200: {"description": "Enrolment started; pass code to /mfa/confirm"},
   692	    },
   693	)
   694	async def mfa_enroll_v1(
   695	    request: Request,
   696	    current_user: User = Depends(get_current_user),
   697	    db: AsyncSession = Depends(get_db),
   698	) -> MfaEnrolResponse:
   699	    """Generate a fresh TOTP secret + provisioning URI.
   700	
   701	    Does NOT enable MFA — that requires the user to confirm a code
   702	    via ``/mfa/confirm``. Calling this on a user who already has
   703	    MFA fully enabled rotates the secret to a new one and resets
   704	    them to the unconfirmed state — they have to re-confirm.
   705	    """
   706	
   707	    result = await start_enrolment(db, current_user)
   708	    await audit_append(
   709	        db,
   710	        event_type=EventType.AUTH_MFA_ENROLL,
   711	        actor_type=ActorType.USER,
   712	        actor_id=current_user.id,
   713	        resource_type="user",
   714	        resource_id=current_user.id,
   715	        payload={"rotated": True},
   716	        **context_from_request(request),
   717	    )
   718	    await db.commit()
   719	    return MfaEnrolResponse(
   720	        secret=result.secret,
   721	        provisioning_uri=result.provisioning_uri,
   722	    )
   723	
   724	
   725	@router.post(
   726	    "/mfa/confirm",
   727	    response_model=None,
   728	    responses={
   729	        200: {"description": "MFA enabled, recovery codes returned"},
   730	        400: {"description": "Code did not match or no enrolment in progress"},
   731	    },
   732	)
   733	async def mfa_confirm_v1(
   734	    payload: MfaConfirmRequest,
   735	    request: Request,
   736	    current_user: User = Depends(get_current_user),
   737	    db: AsyncSession = Depends(get_db),
   738	) -> MfaConfirmResponse:
   739	    """Verify the TOTP code and finalise enrolment.
   740	
   741	    On success: ``mfa_enabled=True``, recovery codes generated and
   742	    returned in cleartext **once**. The cleartext is never
   743	    persisted — only sha256 hashes live in
   744	    ``mfa_recovery_codes``.
   745	    """
   746	
   747	    try:
   748	        result = await confirm_enrolment(db, current_user, payload.code)
   749	    except (InvalidMfaCode, MfaNotEnrolled) as exc:
   750	        await audit_append(
   751	            db,
   752	            event_type=EventType.AUTH_MFA_CONFIRM,
   753	            actor_type=ActorType.USER,
   754	            actor_id=current_user.id,
   755	            resource_type="user",
   756	            resource_id=current_user.id,
   757	            payload={"success": False, "reason": str(exc)},
   758	            **context_from_request(request),
   759	        )
   760	        await db.commit()

 succeeded in 0ms:
     1	from datetime import datetime, timedelta, timezone
     2	
     3	from fastapi import Depends, HTTPException, Request, status
     4	from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
     5	from jose import JWTError, jwt
     6	from passlib.context import CryptContext
     7	from sqlalchemy import select
     8	from sqlalchemy.ext.asyncio import AsyncSession
     9	
    10	from app.config import get_settings
    11	from app.database import get_db
    12	from app.models import User
    13	
    14	pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    15	security = HTTPBearer(auto_error=False)
    16	settings = get_settings()
    17	
    18	ALGORITHM = "HS256"
    19	
    20	
    21	def hash_password(password: str) -> str:
    22	    return pwd_context.hash(password)
    23	
    24	
    25	def verify_password(plain_password: str, hashed_password: str) -> bool:
    26	    return pwd_context.verify(plain_password, hashed_password)
    27	
    28	
    29	def create_access_token(user_id: int, role: str) -> str:
    30	    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    31	    payload = {
    32	        "sub": str(user_id),
    33	        "role": role,
    34	        "type": "access",
    35	        "exp": expire,
    36	    }
    37	    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    38	
    39	
    40	def create_refresh_token(user_id: int) -> str:
    41	    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    42	    payload = {
    43	        "sub": str(user_id),
    44	        "type": "refresh",
    45	        "exp": expire,
    46	    }
    47	    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    48	
    49	
    50	def decode_token(token: str) -> dict:
    51	    try:
    52	        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    53	        return payload
    54	    except JWTError:
    55	        raise HTTPException(
    56	            status_code=status.HTTP_401_UNAUTHORIZED,
    57	            detail="Invalid or expired token",
    58	        )
    59	
    60	
    61	async def get_current_user(
    62	    credentials: HTTPAuthorizationCredentials = Depends(security),
    63	    db: AsyncSession = Depends(get_db),
    64	) -> User:
    65	    if credentials is None:
    66	        raise HTTPException(
    67	            status_code=status.HTTP_401_UNAUTHORIZED,
    68	            detail="Not authenticated",
    69	        )
    70	    payload = decode_token(credentials.credentials)
    71	    if payload.get("type") != "access":
    72	        raise HTTPException(
    73	            status_code=status.HTTP_401_UNAUTHORIZED,
    74	            detail="Invalid token type",
    75	        )
    76	    user_id = int(payload["sub"])
    77	    result = await db.execute(select(User).where(User.id == user_id))
    78	    user = result.scalar_one_or_none()
    79	    if user is None or not user.is_active:
    80	        raise HTTPException(
    81	            status_code=status.HTTP_401_UNAUTHORIZED,
    82	            detail="User not found or inactive",
    83	        )
    84	    return user
    85	
    86	
    87	async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    88	    if current_user.role.value != "admin":
    89	        raise HTTPException(
    90	            status_code=status.HTTP_403_FORBIDDEN,
    91	            detail="Admin access required",
    92	        )
    93	    return current_user
    94	
    95	
    96	async def check_account_lockout(email: str, redis_client) -> None:
    97	    key = f"login_failures:{email}"
    98	    failures = await redis_client.get(key)
    99	    if failures and int(failures) >= 5:
   100	        raise HTTPException(
   101	            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
   102	            detail="Account temporarily locked due to too many failed attempts. Try again in 15 minutes.",
   103	        )
   104	
   105	
   106	async def record_failed_login(email: str, redis_client) -> None:
   107	    key = f"login_failures:{email}"
   108	    await redis_client.incr(key)
   109	    await redis_client.expire(key, 900)
   110	
   111	
   112	async def clear_failed_logins(email: str, redis_client) -> None:
   113	    key = f"login_failures:{email}"
   114	    await redis_client.delete(key)

exec
/bin/bash -lc "rg -n \"Query\\(|Path\\(|Header\\(|Cookie\\(|Body\\(|str =|int =|Optional\\[|list\\[|dict\\[\" backend/app/routers backend/app/schemas | sed -n '1,260p'" in /data/projects/seige-range
 succeeded in 0ms:
backend/app/schemas/auth.py:7:    refresh_token: str = Field(..., min_length=1)
backend/app/schemas/auth.py:11:    refresh_token: Optional[str] = None
backend/app/schemas/auth.py:16:    token_type: str = "bearer"
backend/app/schemas/solve.py:14:    time_to_solve: Optional[int] = None
backend/app/schemas/solve.py:22:    points_awarded: Optional[int] = None
backend/app/schemas/solve.py:23:    is_first_blood: Optional[bool] = None
backend/app/schemas/solve.py:24:    message: Optional[str] = None
backend/app/schemas/writeup.py:8:    content: str = Field(..., min_length=1, max_length=50_000)
backend/app/schemas/writeup.py:9:    title: Optional[str] = Field(None, max_length=200)
backend/app/schemas/writeup.py:13:    rating: int = Field(..., ge=1, le=5)
backend/app/schemas/writeup.py:31:    author_display_name: Optional[str] = None
backend/app/schemas/writeup.py:38:    items: list[WriteupListItem]
backend/app/schemas/user.py:9:    username: str = Field(..., min_length=2)
backend/app/schemas/user.py:11:    display_name: Optional[str] = None
backend/app/schemas/user.py:12:    team: Optional[str] = None
backend/app/schemas/user.py:49:    display_name: Optional[str] = None
backend/app/schemas/user.py:51:    team: Optional[str] = None
backend/app/schemas/user.py:54:    last_login: Optional[datetime] = None
backend/app/schemas/user.py:55:    total_points: Optional[int] = None
backend/app/schemas/user.py:56:    total_solves: Optional[int] = None
backend/app/schemas/user.py:57:    current_streak: Optional[int] = None
backend/app/schemas/user.py:58:    rank: Optional[int] = None
backend/app/schemas/user.py:64:    display_name: Optional[str] = Field(None, max_length=100)
backend/app/schemas/user.py:65:    team: Optional[str] = None
backend/app/schemas/user.py:66:    role: Optional[str] = None
backend/app/schemas/user.py:67:    is_active: Optional[bool] = None
backend/app/schemas/user.py:71:    def _role(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/user.py:78:    def _team(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/user.py:87:    token_type: str = "bearer"
backend/app/schemas/leaderboard.py:10:    display_name: Optional[str] = None
backend/app/schemas/leaderboard.py:11:    team: Optional[str] = None
backend/app/schemas/leaderboard.py:12:    total_points: int = 0
backend/app/schemas/leaderboard.py:13:    total_solves: int = 0
backend/app/schemas/leaderboard.py:14:    current_streak: int = 0
backend/app/schemas/leaderboard.py:15:    longest_streak: int = 0
backend/app/schemas/leaderboard.py:20:    total_points: int = 0
backend/app/schemas/leaderboard.py:21:    total_solves: int = 0
backend/app/schemas/leaderboard.py:22:    member_count: int = 0
backend/app/schemas/leaderboard.py:30:    display_name: Optional[str] = None
backend/app/schemas/leaderboard.py:31:    team: Optional[str] = None
backend/app/schemas/leaderboard.py:32:    weekly_points: int = 0
backend/app/schemas/leaderboard.py:33:    weekly_solves: int = 0
backend/app/routers/notifications.py:14:    page: int = Query(1, ge=1),
backend/app/routers/notifications.py:15:    per_page: int = Query(20, ge=1, le=100),
backend/app/schemas/common.py:10:    detail: Optional[str] = None
backend/app/schemas/competition.py:8:    title: str = Field(..., min_length=1, max_length=200)
backend/app/schemas/competition.py:9:    description: Optional[str] = None
backend/app/schemas/competition.py:15:    format: str = "jeopardy"
backend/app/schemas/competition.py:34:    description: Optional[str] = None
backend/app/schemas/competition.py:41:    created_by: Optional[int] = None
backend/app/schemas/competition.py:43:    scoreboard: Optional[List[Dict[str, Any]]] = None
backend/app/routers/writeups.py:86:    page: int = Query(1, ge=1),
backend/app/routers/writeups.py:87:    per_page: int = Query(20, ge=1, le=100),
backend/app/routers/ws.py:15:    token: str = Query(None),
backend/app/schemas/instance.py:11:    container_id: Optional[str] = None
backend/app/schemas/instance.py:12:    container_name: Optional[str] = None
backend/app/schemas/instance.py:14:    assigned_ip: Optional[str] = None
backend/app/schemas/instance.py:15:    assigned_port: Optional[int] = None
backend/app/schemas/instance.py:17:    expires_at: Optional[datetime] = None
backend/app/schemas/instance.py:18:    stopped_at: Optional[datetime] = None
backend/app/schemas/instance.py:19:    challenge_slug: Optional[str] = None
backend/app/schemas/instance.py:27:    ip: Optional[str] = None
backend/app/routers/admin.py:24:    page: int = Query(1, ge=1),
backend/app/routers/admin.py:25:    per_page: int = Query(50, ge=1, le=200),
backend/app/routers/admin.py:110:    user_id: int | None = Query(None),
backend/app/routers/admin.py:111:    action: str | None = Query(None),
backend/app/routers/admin.py:112:    date_from: str | None = Query(None),
backend/app/routers/admin.py:113:    date_to: str | None = Query(None),
backend/app/routers/admin.py:114:    page: int = Query(1, ge=1),
backend/app/routers/admin.py:115:    per_page: int = Query(50, ge=1, le=200),
backend/app/routers/admin.py:179:    challenges_dir = Path("/challenges")
backend/app/routers/admin.py:311:    solves_by_category: dict[str, int] = {}
backend/app/routers/admin.py:320:    template_dir = Path(__file__).parent.parent / "templates"
backend/app/routers/health.py:40:_cache: dict[str, Any] = {"expires_at": 0.0, "report": None}
backend/app/routers/health.py:44:async def health() -> dict[str, str]:
backend/app/routers/health.py:78:_PROBES: dict[str, Any] = {
backend/app/routers/health.py:85:async def _run_probe(name: str, fn) -> dict[str, Any]:
backend/app/routers/health.py:110:async def _build_report() -> dict[str, Any]:
backend/app/routers/health.py:122:async def _cached_report() -> dict[str, Any]:
backend/app/routers/health.py:134:async def readyz(response: Response) -> dict[str, Any]:
backend/app/routers/leaderboard.py:21:    team: str | None = Query(None),
backend/app/routers/leaderboard.py:134:    team: str | None = Query(None),
backend/app/routers/stats.py:107:    technique_challenges: dict[str, list[int]] = {}
backend/app/routers/stats.py:160:    date_map: dict[str, dict[str, int]] = {}
backend/app/routers/stats.py:162:        date_str = str(row.solve_date)
backend/app/routers/stats.py:215:    skill_counts: dict[str, dict[str, int]] = {}
backend/app/routers/stats.py:237:    technique_counts: dict[str, dict[str, int]] = {}
backend/app/routers/competitions.py:46:    active: bool | None = Query(None),
backend/app/routers/competitions.py:168:) -> list[dict]:
backend/app/schemas/challenge.py:27:    title: str = Field(..., min_length=1, max_length=200)
backend/app/schemas/challenge.py:28:    slug: str = Field(..., min_length=2, max_length=64)
backend/app/schemas/challenge.py:29:    description: str = Field(..., min_length=1)
backend/app/schemas/challenge.py:30:    category: str = Field(..., min_length=1, max_length=100)
backend/app/schemas/challenge.py:32:    difficulty: int = Field(..., ge=1, le=5)
backend/app/schemas/challenge.py:33:    points: int = Field(..., ge=1, le=10000)
backend/app/schemas/challenge.py:38:    docker_image: str = Field(..., min_length=1, max_length=300)
backend/app/schemas/challenge.py:39:    docker_port: int = Field(..., ge=1, le=65535)
backend/app/schemas/challenge.py:62:    slug: Optional[str] = Field(None, min_length=2, max_length=64)
backend/app/schemas/challenge.py:63:    title: Optional[str] = Field(None, min_length=1, max_length=200)
backend/app/schemas/challenge.py:64:    description: Optional[str] = Field(None, min_length=1)
backend/app/schemas/challenge.py:65:    category: Optional[str] = Field(None, min_length=1, max_length=100)
backend/app/schemas/challenge.py:66:    team: Optional[str] = None
backend/app/schemas/challenge.py:67:    difficulty: Optional[int] = Field(None, ge=1, le=5)
backend/app/schemas/challenge.py:68:    points: Optional[int] = Field(None, ge=1, le=10000)
backend/app/schemas/challenge.py:69:    flag: Optional[str] = None
backend/app/schemas/challenge.py:70:    hints: Optional[List[Dict[str, Any]]] = None
backend/app/schemas/challenge.py:71:    skills: Optional[List[str]] = None
backend/app/schemas/challenge.py:72:    mitre_techniques: Optional[List[str]] = None
backend/app/schemas/challenge.py:73:    docker_image: Optional[str] = Field(None, min_length=1, max_length=300)
backend/app/schemas/challenge.py:74:    docker_port: Optional[int] = Field(None, ge=1, le=65535)
backend/app/schemas/challenge.py:75:    docker_config: Optional[Dict[str, Any]] = None
backend/app/schemas/challenge.py:76:    prerequisite_ids: Optional[List[int]] = None
backend/app/schemas/challenge.py:80:    def _slug(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/challenge.py:85:    def _flag(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/challenge.py:90:    def _team(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/challenge.py:112:    released_at: Optional[datetime] = None
backend/app/schemas/challenge.py:114:    solve_count: int = 0
backend/app/schemas/challenge.py:116:    first_blood_user: Optional[str] = None
backend/app/schemas/challenge.py:129:    flag: str = Field(..., min_length=1, max_length=512)
backend/app/schemas/challenge.py:141:    feedback_text: Optional[str] = None
backend/app/schemas/v1/hints.py:17:    index: int = Field(ge=0)
backend/app/schemas/v1/hints.py:19:    cost: int = Field(default=0, ge=0)
backend/app/routers/challenges/browse.py:27:    team: str | None = Query(None),
backend/app/routers/challenges/browse.py:28:    category: str | None = Query(None),
backend/app/routers/challenges/browse.py:29:    difficulty: str | None = Query(None),
backend/app/routers/challenges/browse.py:30:    search: str | None = Query(None),
backend/app/routers/challenges/browse.py:31:    mitre: str | None = Query(None),
backend/app/routers/challenges/browse.py:32:    sort: str = Query("newest"),
backend/app/routers/challenges/browse.py:33:    page: int = Query(1, ge=1),
backend/app/routers/challenges/browse.py:34:    per_page: int = Query(20, ge=1, le=100),
backend/app/schemas/v1/scoreboard.py:14:    rank: int = Field(ge=1)
backend/app/schemas/v1/scoreboard.py:20:    user_id: int = Field(ge=1)
backend/app/schemas/v1/scoreboard.py:23:    team: Optional[str] = None
backend/app/schemas/v1/scoreboard.py:24:    total_points: int = Field(ge=0)
backend/app/schemas/v1/scoreboard.py:25:    total_solves: int = Field(ge=0)
backend/app/schemas/v1/scoreboard.py:26:    current_streak: int = Field(ge=0)
backend/app/schemas/v1/scoreboard.py:33:    team_filter: Optional[str] = None
backend/app/schemas/v1/me.py:27:    id: int = Field(ge=1)
backend/app/schemas/v1/me.py:32:    team: Optional[str] = None
backend/app/schemas/v1/me.py:36:    total_points: int = Field(ge=0)
backend/app/schemas/v1/me.py:37:    total_solves: int = Field(ge=0)
backend/app/schemas/v1/me.py:38:    current_streak: int = Field(ge=0)
backend/app/schemas/v1/me.py:39:    rank: Optional[int] = Field(default=None, ge=1)
backend/app/routers/v1/scoreboard.py:22:    team: Optional[str] = Query(None, pattern="^(red|blue|purple)$"),
backend/app/routers/v1/scoreboard.py:23:    limit: int = Query(100, ge=1, le=500),
backend/app/schemas/v1/webhooks.py:59:    name: str = Field(min_length=1, max_length=200)
backend/app/schemas/v1/webhooks.py:97:    last_delivery_at: Optional[datetime] = None
backend/app/schemas/v1/webhooks.py:98:    last_status: Optional[str] = None
backend/app/schemas/v1/webhooks.py:99:    last_error: Optional[str] = None
backend/app/schemas/v1/webhooks.py:105:    secret: str = Field(min_length=32)
backend/app/schemas/v1/webhooks.py:112:    total: int = Field(ge=0)
backend/app/schemas/v1/submission.py:13:    flag: str = Field(min_length=1, max_length=8192)
backend/app/schemas/v1/submission.py:28:    points_awarded: Optional[int] = Field(default=None, ge=0)
backend/app/schemas/v1/submission.py:29:    is_first_blood: Optional[bool] = None
backend/app/schemas/v1/submission.py:30:    flag_id: Optional[str] = None
backend/app/schemas/v1/submission.py:31:    validator: Optional[str] = None
backend/app/routers/v1/webhooks.py:171:    page: int = Query(1, ge=1, le=10_000),
backend/app/routers/v1/webhooks.py:172:    per_page: int = Query(50, ge=1, le=200),
backend/app/schemas/v1/coverage.py:18:    technique_id: str = Field(min_length=1, max_length=16)
backend/app/schemas/v1/coverage.py:19:    challenge_count: int = Field(ge=0)
backend/app/schemas/v1/coverage.py:20:    solved_by_viewer: int = Field(ge=0)
backend/app/schemas/v1/coverage.py:27:    total_techniques: int = Field(ge=0)
backend/app/schemas/v1/coverage.py:28:    total_challenges: int = Field(ge=0)
backend/app/schemas/v1/progress.py:23:    label: Optional[str] = None
backend/app/schemas/v1/progress.py:29:    points: int = Field(ge=0)
backend/app/schemas/v1/progress.py:30:    points_awarded: Optional[int] = Field(default=None, ge=0)
backend/app/schemas/v1/progress.py:32:    captured_at: Optional[datetime] = None
backend/app/schemas/v1/progress.py:33:    is_first_blood_flag: Optional[bool] = None
backend/app/schemas/v1/progress.py:34:    validator_name: Optional[str] = None
backend/app/schemas/v1/progress.py:42:    total_flags: int = Field(ge=0)
backend/app/schemas/v1/progress.py:43:    captured_flags: int = Field(ge=0)
backend/app/schemas/v1/progress.py:44:    total_points_possible: int = Field(ge=0)
backend/app/schemas/v1/progress.py:45:    points_captured: int = Field(ge=0)
backend/app/schemas/v1/webhook_deliveries.py:30:    attempt: int = Field(ge=1)
backend/app/schemas/v1/webhook_deliveries.py:32:    http_status: Optional[int] = None
backend/app/schemas/v1/webhook_deliveries.py:33:    response_ms: Optional[int] = None
backend/app/schemas/v1/webhook_deliveries.py:34:    error: Optional[str] = None
backend/app/schemas/v1/webhook_deliveries.py:42:    total: int = Field(ge=0)
backend/app/schemas/v1/webhook_deliveries.py:43:    page: int = Field(ge=1)
backend/app/schemas/v1/webhook_deliveries.py:44:    per_page: int = Field(ge=1, le=200)
backend/app/schemas/v1/auth.py:30:    id: int = Field(ge=1)
backend/app/schemas/v1/auth.py:35:    team: Optional[str] = None
backend/app/schemas/v1/auth.py:38:    last_login: Optional[datetime] = None
backend/app/schemas/v1/auth.py:52:    email: str = Field(min_length=3, max_length=254)
backend/app/schemas/v1/auth.py:53:    username: str = Field(min_length=2, max_length=32)
backend/app/schemas/v1/auth.py:54:    password: str = Field(min_length=8, max_length=128)
backend/app/schemas/v1/auth.py:55:    display_name: Optional[str] = Field(default=None, max_length=64)
backend/app/schemas/v1/auth.py:56:    team: Optional[str] = None
backend/app/schemas/v1/auth.py:78:    def _team(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/v1/auth.py:90:    email: str = Field(min_length=3, max_length=254)
backend/app/schemas/v1/auth.py:91:    password: str = Field(min_length=1, max_length=128)
backend/app/schemas/v1/auth.py:102:    refresh_token: str = Field(min_length=1, max_length=4096)
backend/app/schemas/v1/auth.py:108:    refresh_token: Optional[str] = Field(default=None, max_length=4096)
backend/app/schemas/v1/auth.py:117:    token_type: str = "bearer"
backend/app/schemas/v1/auth.py:124:    token_type: str = "bearer"
backend/app/schemas/v1/auth.py:136:    email: str = Field(min_length=3, max_length=254)
backend/app/schemas/v1/auth.py:153:    token: str = Field(min_length=1, max_length=512)
backend/app/schemas/v1/auth.py:154:    new_password: str = Field(min_length=8, max_length=128)
backend/app/schemas/v1/auth.py:169:    current_password: str = Field(min_length=1, max_length=128)
backend/app/schemas/v1/auth.py:170:    new_password: str = Field(min_length=8, max_length=128)
backend/app/schemas/v1/auth.py:185:    password: str = Field(min_length=1, max_length=128)
backend/app/schemas/v1/auth.py:204:    display_name: Optional[str] = Field(default=None, max_length=64)
backend/app/schemas/v1/auth.py:205:    team: Optional[str] = None
backend/app/schemas/v1/auth.py:209:    def _display_name(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/v1/auth.py:219:    def _team(cls, v: Optional[str]) -> Optional[str]:
backend/app/schemas/v1/auth.py:248:    code: str = Field(min_length=6, max_length=8)
backend/app/schemas/v1/auth.py:258:    recovery_codes: list[str]
backend/app/schemas/v1/auth.py:264:    password: str = Field(min_length=1, max_length=128)
backend/app/schemas/v1/auth.py:265:    code: str = Field(min_length=6, max_length=8)
backend/app/schemas/v1/auth.py:289:    mfa_pending_token: str = Field(min_length=1, max_length=4096)
backend/app/schemas/v1/auth.py:290:    code: str = Field(min_length=6, max_length=8)
backend/app/schemas/v1/auth.py:299:    token: str = Field(min_length=1, max_length=512)
backend/app/routers/v1/workstation.py:35:    ssh_host_port: Optional[int] = None
backend/app/routers/v1/workstation.py:36:    web_host_port: Optional[int] = None
backend/app/routers/v1/workstation.py:41:    ssh_command: Optional[str] = None
backend/app/routers/v1/workstation.py:42:    web_url: Optional[str] = None
backend/app/routers/v1/workstation.py:48:    one_shot_password: Optional[str] = None
backend/app/schemas/v1/challenges.py:16:    index: int = Field(ge=0)
backend/app/schemas/v1/challenges.py:18:    text: Optional[str] = None
backend/app/schemas/v1/challenges.py:19:    cost: int = Field(default=0, ge=0)
backend/app/schemas/v1/challenges.py:51:    difficulty: int = Field(ge=1, le=5)
backend/app/schemas/v1/challenges.py:52:    points: int = Field(ge=0)
backend/app/schemas/v1/challenges.py:54:    solve_count: int = Field(ge=0)
backend/app/schemas/v1/challenges.py:56:    first_blood_user: Optional[str] = None
backend/app/schemas/v1/challenges.py:57:    released_at: Optional[datetime] = None
backend/app/schemas/v1/challenges.py:64:    total: int = Field(ge=0)
backend/app/schemas/v1/challenges.py:65:    page: int = Field(ge=1)
backend/app/schemas/v1/challenges.py:66:    per_page: int = Field(ge=1, le=100)
backend/app/schemas/v1/challenges.py:84:    difficulty: int = Field(ge=1, le=5)
backend/app/schemas/v1/challenges.py:85:    points: int = Field(ge=0)
backend/app/schemas/v1/challenges.py:90:    solve_count: int = Field(ge=0)
backend/app/schemas/v1/challenges.py:94:    writeup_count: int = Field(ge=0)
backend/app/schemas/v1/challenges.py:95:    released_at: Optional[datetime] = None
backend/app/schemas/v1/leaderboard.py:20:    total_points: int = Field(ge=0)
backend/app/schemas/v1/leaderboard.py:21:    total_solves: int = Field(ge=0)
backend/app/schemas/v1/leaderboard.py:22:    member_count: int = Field(ge=0)
backend/app/schemas/v1/leaderboard.py:36:    rank: int = Field(ge=1)
backend/app/schemas/v1/leaderboard.py:37:    user_id: int = Field(ge=1)
backend/app/schemas/v1/leaderboard.py:40:    team: Optional[str] = None
backend/app/schemas/v1/leaderboard.py:41:    total_points: int = Field(ge=0)
backend/app/schemas/v1/leaderboard.py:42:    total_solves: int = Field(ge=0)
backend/app/schemas/v1/leaderboard.py:43:    current_streak: int = Field(ge=0)
backend/app/schemas/v1/leaderboard.py:50:    team_filter: Optional[str] = None
backend/app/routers/v1/admin.py:492:    challenges_dir = Path("/challenges")
backend/app/schemas/v1/admin.py:30:    title: str = Field(min_length=1, max_length=200)
backend/app/schemas/v1/admin.py:31:    slug: str = Field(min_length=2, max_length=64)
backend/app/schemas/v1/admin.py:32:    description: str = Field(min_length=1)
backend/app/schemas/v1/admin.py:33:    category: str = Field(min_length=1, max_length=100)
backend/app/schemas/v1/admin.py:35:    difficulty: int = Field(ge=1, le=5)
backend/app/schemas/v1/admin.py:36:    points: int = Field(ge=1, le=10_000)
backend/app/schemas/v1/admin.py:41:    docker_image: str = Field(min_length=1, max_length=300)
backend/app/schemas/v1/admin.py:42:    docker_port: int = Field(ge=1, le=65_535)
backend/app/schemas/v1/admin.py:67:    slug: Optional[str] = Field(default=None, min_length=2, max_length=64)
backend/app/schemas/v1/admin.py:68:    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
backend/app/schemas/v1/admin.py:69:    description: Optional[str] = Field(default=None, min_length=1)
backend/app/schemas/v1/admin.py:70:    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
backend/app/schemas/v1/admin.py:71:    team: Optional[str] = None
backend/app/schemas/v1/admin.py:72:    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
backend/app/schemas/v1/admin.py:73:    points: Optional[int] = Field(default=None, ge=1, le=10_000)
backend/app/schemas/v1/admin.py:74:    flag: Optional[str] = None

exec
/bin/bash -lc "nl -ba backend/app/services/backup.py | sed -n '120,165p'" in /data/projects/seige-range
 succeeded in 0ms:
   120	    except OSError as exc:
   121	        return BackupResult(
   122	            ok=False, error=f"mkdir failed: {type(exc).__name__}: {exc}"
   123	        )
   124	
   125	    if shutil.which(pg_dump_path) is None:
   126	        return BackupResult(
   127	            ok=False, error=f"{pg_dump_path!r} not found on PATH"
   128	        )
   129	
   130	    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
   131	    out_path = target_dir / f"siege-{timestamp}.sql.gz"
   132	
   133	    env = os.environ.copy()
   134	    env.update(_parse_async_url(database_url))
   135	
   136	    started = datetime.now(timezone.utc)
   137	    try:
   138	        # ``pg_dump`` writes SQL to stdout; we shell-pipe to gzip
   139	        # via a single ``sh -c`` so we don't need a Python gzip
   140	        # buffer for multi-GB dumps. The double quotes around
   141	        # the path are safe — ``out_path`` is built from ASCII
   142	        # timestamp.
   143	        cmd = (
   144	            f"{pg_dump_path} --no-owner --no-privileges "
   145	            f"| gzip -c > '{out_path}'"
   146	        )
   147	        proc = await asyncio.create_subprocess_shell(
   148	            cmd,
   149	            env=env,
   150	            stdout=asyncio.subprocess.DEVNULL,
   151	            stderr=asyncio.subprocess.PIPE,
   152	        )
   153	        _, stderr = await proc.communicate()
   154	    except (OSError, asyncio.CancelledError) as exc:
   155	        return BackupResult(
   156	            ok=False, error=f"subprocess error: {type(exc).__name__}: {exc}"
   157	        )
   158	
   159	    duration = (datetime.now(timezone.utc) - started).total_seconds()
   160	
   161	    if proc.returncode != 0:
   162	        # Clean up the partial file so it can't be confused for a
   163	        # good backup later.
   164	        try:
   165	            out_path.unlink(missing_ok=True)

exec
/bin/bash -lc "nl -ba backend/app/routers/challenges/admin.py | sed -n '1,220p'" in /data/projects/seige-range
exec
/bin/bash -lc "nl -ba backend/app/schemas/user.py | sed -n '1,95p'; nl -ba backend/app/schemas/v1/auth.py | sed -n '45,100p'" in /data/projects/seige-range
 succeeded in 0ms:
     1	"""Admin CRUD endpoints for challenges: create, update, release, soft-delete."""
     2	
     3	from datetime import datetime, timezone
     4	
     5	from fastapi import APIRouter, Depends, HTTPException, Request
     6	from sqlalchemy import func, select
     7	from sqlalchemy.ext.asyncio import AsyncSession
     8	
     9	from app.database import get_db
    10	from app.models import Challenge, Notification, Solve, User
    11	from app.schemas import ChallengeCreate, ChallengeUpdate
    12	from app.services.audit import ActorType, EventType, append as audit_append
    13	from app.services.audit.request_context import context_from_request
    14	from app.services.auth import require_admin
    15	from app.services.webhook_dispatch import deliver_event as deliver_webhook_event
    16	from app.validators.exact import hash_exact_value
    17	from app.services.ws_manager import ws_manager
    18	
    19	router = APIRouter()
    20	
    21	
    22	@router.post("/")
    23	async def create_challenge(
    24	    data: ChallengeCreate,
    25	    admin: User = Depends(require_admin),
    26	    db: AsyncSession = Depends(get_db),
    27	):
    28	    existing = (
    29	        await db.execute(select(Challenge).where(Challenge.slug == data.slug))
    30	    ).scalars().first()
    31	    if existing:
    32	        raise HTTPException(status_code=409, detail="Challenge slug already exists.")
    33	
    34	    challenge = Challenge(
    35	        slug=data.slug,
    36	        title=data.title,
    37	        description=data.description,
    38	        category=data.category,
    39	        difficulty=data.difficulty,
    40	        points=data.points,
    41	        team=data.team,
    42	        flag_hash=hash_exact_value(data.flag),
    43	        hints=data.hints,
    44	        skills=data.skills,
    45	        mitre_techniques=data.mitre_techniques,
    46	        docker_image=data.docker_image,
    47	        docker_port=data.docker_port,
    48	        docker_config=data.docker_config,
    49	        prerequisite_ids=data.prerequisite_ids,
    50	        is_released=False,
    51	        is_active=True,
    52	        created_at=datetime.now(timezone.utc),
    53	    )
    54	    db.add(challenge)
    55	    await db.commit()
    56	    await db.refresh(challenge)
    57	
    58	    return {
    59	        "id": challenge.id,
    60	        "slug": challenge.slug,
    61	        "title": challenge.title,
    62	        "detail": "Challenge created.",
    63	    }
    64	
    65	
    66	@router.put("/{slug}")
    67	async def update_challenge(
    68	    slug: str,
    69	    data: ChallengeUpdate,
    70	    admin: User = Depends(require_admin),
    71	    db: AsyncSession = Depends(get_db),
    72	):
    73	    challenge = (
    74	        await db.execute(select(Challenge).where(Challenge.slug == slug))
    75	    ).scalars().first()
    76	    if not challenge:
    77	        raise HTTPException(status_code=404, detail="Challenge not found.")
    78	
    79	    updates = data.model_dump(exclude_unset=True)
    80	
    81	    if "flag" in updates:
    82	        solve_count = (
    83	            await db.execute(
    84	                select(func.count(Solve.id)).where(
    85	                    Solve.challenge_id == challenge.id
    86	                )
    87	            )
    88	        ).scalar()
    89	        if solve_count > 0:
    90	            raise HTTPException(
    91	                status_code=400,
    92	                detail="Cannot change flag after solves exist.",
    93	            )
    94	        challenge.flag_hash = hash_exact_value(updates.pop("flag"))
    95	
    96	    new_slug = updates.pop("slug", None)
    97	    if new_slug is not None and new_slug != slug:
    98	        existing = (
    99	            await db.execute(select(Challenge).where(Challenge.slug == new_slug))
   100	        ).scalars().first()
   101	        if existing:
   102	            raise HTTPException(status_code=409, detail="Slug already exists.")
   103	        challenge.slug = new_slug
   104	
   105	    for field, value in updates.items():
   106	        setattr(challenge, field, value)
   107	
   108	    await db.commit()
   109	    await db.refresh(challenge)
   110	
   111	    return {"detail": "Challenge updated.", "slug": challenge.slug}
   112	
   113	
   114	@router.post("/{slug}/release")
   115	async def release_challenge(
   116	    slug: str,
   117	    request: Request,
   118	    admin: User = Depends(require_admin),
   119	    db: AsyncSession = Depends(get_db),
   120	):
   121	    challenge = (
   122	        await db.execute(select(Challenge).where(Challenge.slug == slug))
   123	    ).scalars().first()
   124	    if not challenge:
   125	        raise HTTPException(status_code=404, detail="Challenge not found.")
   126	
   127	    challenge.is_released = True
   128	    challenge.released_at = datetime.now(timezone.utc)
   129	
   130	    from app.services.notifications import create_notification
   131	
   132	    await create_notification(
   133	        db,
   134	        title="New Challenge Released!",
   135	        message=(
   136	            f"'{challenge.title}' "
   137	            f"({challenge.category} - {challenge.difficulty}) is now available!"
   138	        ),
   139	        notification_type="release",
   140	        is_global=True,
   141	    )
   142	
   143	    # Phase 12 (slice 9): emit ``challenge.released`` to the
   144	    # audit ledger + fan out to v1 webhook subscriptions. Replaces
   145	    # the legacy env-var-driven notify_release Slack/Teams broadcast.
   146	    payload = {
   147	        "challenge_slug": challenge.slug,
   148	        "title": challenge.title,
   149	        "category": challenge.category,
   150	        "points": challenge.points,
   151	        "difficulty": challenge.difficulty,
   152	    }
   153	    await audit_append(
   154	        db,
   155	        event_type=EventType.CHALLENGE_RELEASED,
   156	        actor_type=ActorType.USER,
   157	        actor_id=admin.id,
   158	        resource_type="challenge",
   159	        resource_id=challenge.slug,
   160	        payload=payload,
   161	        **context_from_request(request),
   162	    )
   163	    await deliver_webhook_event(
   164	        db=db,
   165	        event_type=EventType.CHALLENGE_RELEASED,
   166	        payload=payload,
   167	    )
   168	    await db.commit()
   169	
   170	    await ws_manager.broadcast(
   171	        {
   172	            "type": "challenge_released",
   173	            "slug": challenge.slug,
   174	            "title": challenge.title,
   175	            "category": challenge.category,
   176	            "difficulty": challenge.difficulty,
   177	            "points": challenge.points,
   178	        }
   179	    )
   180	
   181	    return {"detail": "Challenge released.", "slug": challenge.slug}
   182	
   183	
   184	@router.delete("/{slug}")
   185	async def delete_challenge(
   186	    slug: str,
   187	    admin: User = Depends(require_admin),
   188	    db: AsyncSession = Depends(get_db),
   189	):
   190	    challenge = (
   191	        await db.execute(select(Challenge).where(Challenge.slug == slug))
   192	    ).scalars().first()
   193	    if not challenge:
   194	        raise HTTPException(status_code=404, detail="Challenge not found.")
   195	
   196	    challenge.is_active = False
   197	    await db.commit()
   198	    return {"detail": "Challenge soft-deleted.", "slug": slug}

 succeeded in 0ms:
     1	from datetime import datetime
     2	from typing import Optional
     3	
     4	from pydantic import BaseModel, EmailStr, Field, field_validator
     5	
     6	
     7	class UserCreate(BaseModel):
     8	    email: str
     9	    username: str = Field(..., min_length=2)
    10	    password: str
    11	    display_name: Optional[str] = None
    12	    team: Optional[str] = None
    13	
    14	    @field_validator("email")
    15	    @classmethod
    16	    def validate_email(cls, v: str) -> str:
    17	        v = (v or "").strip().lower()
    18	        if "@" not in v or "." not in v.split("@")[-1]:
    19	            raise ValueError("Invalid email format")
    20	        return v
    21	
    22	    @field_validator("username")
    23	    @classmethod
    24	    def normalize_username(cls, v: str) -> str:
    25	        return v.strip()
    26	
    27	    @field_validator("password")
    28	    @classmethod
    29	    def validate_password(cls, v: str) -> str:
    30	        if len(v) < 8:
    31	            raise ValueError("Password must be at least 8 characters")
    32	        return v
    33	
    34	
    35	class UserLogin(BaseModel):
    36	    email: str
    37	    password: str
    38	
    39	    @field_validator("email")
    40	    @classmethod
    41	    def normalize_email(cls, v: str) -> str:
    42	        return (v or "").strip().lower()
    43	
    44	
    45	class UserResponse(BaseModel):
    46	    id: int
    47	    email: str
    48	    username: str
    49	    display_name: Optional[str] = None
    50	    role: str
    51	    team: Optional[str] = None
    52	    is_active: bool
    53	    created_at: datetime
    54	    last_login: Optional[datetime] = None
    55	    total_points: Optional[int] = None
    56	    total_solves: Optional[int] = None
    57	    current_streak: Optional[int] = None
    58	    rank: Optional[int] = None
    59	
    60	    model_config = {"from_attributes": True}
    61	
    62	
    63	class UserUpdate(BaseModel):
    64	    display_name: Optional[str] = Field(None, max_length=100)
    65	    team: Optional[str] = None
    66	    role: Optional[str] = None
    67	    is_active: Optional[bool] = None
    68	
    69	    @field_validator("role")
    70	    @classmethod
    71	    def _role(cls, v: Optional[str]) -> Optional[str]:
    72	        if v is not None and v not in ("operator", "admin"):
    73	            raise ValueError("role must be 'operator' or 'admin'")
    74	        return v
    75	
    76	    @field_validator("team")
    77	    @classmethod
    78	    def _team(cls, v: Optional[str]) -> Optional[str]:
    79	        if v is not None and v not in ("red", "blue"):
    80	            raise ValueError("team must be 'red' or 'blue'")
    81	        return v
    82	
    83	
    84	class TokenResponse(BaseModel):
    85	    access_token: str
    86	    refresh_token: str
    87	    token_type: str = "bearer"
    88	    user: UserResponse
    45	    # an "unverified" banner / nudge.
    46	    email_verified: bool = False
    47	
    48	
    49	class AuthRegisterRequest(BaseModel):
    50	    model_config = ConfigDict(extra="forbid")
    51	
    52	    email: str = Field(min_length=3, max_length=254)
    53	    username: str = Field(min_length=2, max_length=32)
    54	    password: str = Field(min_length=8, max_length=128)
    55	    display_name: Optional[str] = Field(default=None, max_length=64)
    56	    team: Optional[str] = None
    57	
    58	    @field_validator("email")
    59	    @classmethod
    60	    def _email(cls, v: str) -> str:
    61	        v = (v or "").strip().lower()
    62	        if not _EMAIL_RE.match(v):
    63	            raise ValueError("invalid email format")
    64	        return v
    65	
    66	    @field_validator("username")
    67	    @classmethod
    68	    def _username(cls, v: str) -> str:
    69	        v = (v or "").strip()
    70	        if not _USERNAME_RE.match(v):
    71	            raise ValueError(
    72	                "username must be 2-32 chars of letters/digits/_/-/."
    73	            )
    74	        return v
    75	
    76	    @field_validator("team")
    77	    @classmethod
    78	    def _team(cls, v: Optional[str]) -> Optional[str]:
    79	        if v is None:
    80	            return v
    81	        v = v.strip().lower()
    82	        if v not in ("red", "blue"):
    83	            raise ValueError("team must be 'red' or 'blue'")
    84	        return v
    85	
    86	
    87	class AuthLoginRequest(BaseModel):
    88	    model_config = ConfigDict(extra="forbid")
    89	
    90	    email: str = Field(min_length=3, max_length=254)
    91	    password: str = Field(min_length=1, max_length=128)
    92	
    93	    @field_validator("email")
    94	    @classmethod
    95	    def _email(cls, v: str) -> str:
    96	        return (v or "").strip().lower()
    97	
    98	
    99	class AuthRefreshRequest(BaseModel):
   100	    model_config = ConfigDict(extra="forbid")

codex
[CRITICAL] backend/app/middleware/security_headers.py:108 — wrong HSTS/CSP header names
  Verdict: CONFIRMED — literals are `Strict-Transport-REDACTED` and `Content-REDACTED-Policy`.

[HIGH] backend/app/main.py:154 — FastAPI docs exposed
  Verdict: CONFIRMED — default `/docs`, `/redoc`, `/openapi.json` remain enabled.

[CRITICAL] backend/app/routers/auth.py:106 — legacy login bypasses MFA
  Verdict: CONFIRMED — v0 issues token pair; v1 returns MFA pending token.

[HIGH] backend/app/middleware/rate_limit.py:48 — auth rate limiter unused
  Verdict: CONFIRMED — helper exists/imported, no `Depends(auth_rate_limit)`.

[HIGH] backend/app/middleware/rate_limit.py:43 — proxy IP rate-limit key
  Verdict: CONFIRMED — uses `request.client.host`; no trusted-forwarded-IP handling seen.

[HIGH] backend/app/services/webhook_dispatch.py:228 — webhook SSRF to private IPs
  Verdict: DOWNGRADE — real SSRF sink, but create path is admin-only.

[HIGH] backend/app/routers/v1/auth.py:452 — forgot-password lacks rate limit
  Verdict: CONFIRMED — 429 documented, no limiter dependency.

[HIGH] backend/app/services/mfa.py:176 — MFA verify has no attempt counter
  Verdict: CONFIRMED — 5-minute pending JWT, unlimited code attempts in service/route.

[HIGH] backend/app/routers/v1/auth.py:248 — login timing oracle
  Verdict: CONFIRMED — bcrypt verify only runs for existing user.

[MEDIUM] backend/app/routers/v1/auth.py:258 — raw email in failed-login ledger
  Verdict: DOWNGRADE — privacy issue confirmed; severity is not HIGH security.

[LOW] backend/app/models.py:562 — files exceed 300-line standard
  Verdict: DOWNGRADE — confirmed standards violation, not a security vulnerability.

[HIGH] frontend/package.json:15 — floating dependency ranges
  Verdict: CONFIRMED — dependencies/devDependencies use `^`.

[HIGH] .github/workflows/ci.yml:47 — CI disables coverage/integration tests
  Verdict: CONFIRMED — `--no-cov` overrides pytest coverage gate; unit-only run.

[HIGH] frontend/src/hooks/useWebSocket.js:17 — WebSocket token in query string
  Verdict: CONFIRMED — frontend sends `?token=...`; server accepts `Query`.

[HIGH] backend/app/routers/v1/auth.py:687 — MISSED: MFA enroll rotates existing MFA with access token only
  Verdict: CONFIRMED — stolen access token can replace/reset MFA without password/current MFA.

[HIGH] backend/app/routers/auth.py:106 — MISSED: v0 login bypasses v1 email-verification gate
  Verdict: CONFIRMED — v1 checks `REQUIRE_EMAIL_VERIFIED`; legacy login does not.

[MEDIUM] backend/app/services/auth.py:50 — MISSED: JWT decode omits issuer/audience validation
  Verdict: CONFIRMED — violates project JWT standard; only signature/exp/type checked.

VERDICT: KICK-BACK
tokens used
86,309
[CRITICAL] backend/app/middleware/security_headers.py:108 — wrong HSTS/CSP header names
  Verdict: CONFIRMED — literals are `Strict-Transport-REDACTED` and `Content-REDACTED-Policy`.

[HIGH] backend/app/main.py:154 — FastAPI docs exposed
  Verdict: CONFIRMED — default `/docs`, `/redoc`, `/openapi.json` remain enabled.

[CRITICAL] backend/app/routers/auth.py:106 — legacy login bypasses MFA
  Verdict: CONFIRMED — v0 issues token pair; v1 returns MFA pending token.

[HIGH] backend/app/middleware/rate_limit.py:48 — auth rate limiter unused
  Verdict: CONFIRMED — helper exists/imported, no `Depends(auth_rate_limit)`.

[HIGH] backend/app/middleware/rate_limit.py:43 — proxy IP rate-limit key
  Verdict: CONFIRMED — uses `request.client.host`; no trusted-forwarded-IP handling seen.

[HIGH] backend/app/services/webhook_dispatch.py:228 — webhook SSRF to private IPs
  Verdict: DOWNGRADE — real SSRF sink, but create path is admin-only.

[HIGH] backend/app/routers/v1/auth.py:452 — forgot-password lacks rate limit
  Verdict: CONFIRMED — 429 documented, no limiter dependency.

[HIGH] backend/app/services/mfa.py:176 — MFA verify has no attempt counter
  Verdict: CONFIRMED — 5-minute pending JWT, unlimited code attempts in service/route.

[HIGH] backend/app/routers/v1/auth.py:248 — login timing oracle
  Verdict: CONFIRMED — bcrypt verify only runs for existing user.

[MEDIUM] backend/app/routers/v1/auth.py:258 — raw email in failed-login ledger
  Verdict: DOWNGRADE — privacy issue confirmed; severity is not HIGH security.

[LOW] backend/app/models.py:562 — files exceed 300-line standard
  Verdict: DOWNGRADE — confirmed standards violation, not a security vulnerability.

[HIGH] frontend/package.json:15 — floating dependency ranges
  Verdict: CONFIRMED — dependencies/devDependencies use `^`.

[HIGH] .github/workflows/ci.yml:47 — CI disables coverage/integration tests
  Verdict: CONFIRMED — `--no-cov` overrides pytest coverage gate; unit-only run.

[HIGH] frontend/src/hooks/useWebSocket.js:17 — WebSocket token in query string
  Verdict: CONFIRMED — frontend sends `?token=...`; server accepts `Query`.

[HIGH] backend/app/routers/v1/auth.py:687 — MISSED: MFA enroll rotates existing MFA with access token only
  Verdict: CONFIRMED — stolen access token can replace/reset MFA without password/current MFA.

[HIGH] backend/app/routers/auth.py:106 — MISSED: v0 login bypasses v1 email-verification gate
  Verdict: CONFIRMED — v1 checks `REQUIRE_EMAIL_VERIFIED`; legacy login does not.

[MEDIUM] backend/app/services/auth.py:50 — MISSED: JWT decode omits issuer/audience validation
  Verdict: CONFIRMED — violates project JWT standard; only signature/exp/type checked.

VERDICT: KICK-BACK
