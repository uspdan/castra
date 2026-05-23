import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
import redis.asyncio as aioredis

# get_settings() fails fast with a structured JSON error + exit(1) on
# any validation problem (see app.config). Resolving it here means any
# downstream import that also calls get_settings() reuses the cached
# instance — and any boot misconfiguration aborts before FastAPI builds.
from app.config import get_settings
from app.database import async_session, init_db
from app.models import User
from app.security.seccomp import SeccompProfileError, validate_all_profiles
from app.services.auth import hash_password
from app.services.ws_manager import ws_manager

logger = logging.getLogger("siege_range")
logging.basicConfig(level=logging.INFO)

_settings = get_settings()


def _validate_seccomp_profiles_or_exit() -> dict[str, str]:
    """Phase 9: parse every bundled seccomp profile or fail boot loud.

    Mirrors the Phase 3 fail-fast pattern (one structured JSON line on
    stderr + ``sys.exit(1)``) so a malformed profile aborts before the
    FastAPI app accepts traffic.
    """
    try:
        return validate_all_profiles()
    except SeccompProfileError as exc:
        sys.stderr.write(
            json.dumps(
                {
                    "level": "fatal",
                    "event": "seccomp.profile.invalid",
                    "error": str(exc),
                    "hint": "fix or replace the bundled profile in app/security/seccomp/",
                }
            )
            + "\n"
        )
        sys.exit(1)


_SECCOMP_PROFILE_HASHES = _validate_seccomp_profiles_or_exit()


async def _create_admin_user():
    settings = get_settings()
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == settings.ADMIN_EMAIL))
        existing = result.scalar_one_or_none()
        if not existing:
            admin = User(
                username="admin",
                email=settings.ADMIN_EMAIL,
                display_name="Admin",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(admin)
            await db.commit()
            logger.info("Default admin user created: %s", settings.ADMIN_EMAIL)
        else:
            logger.info("Admin user already exists.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting Siege Range API...")

    await init_db()
    logger.info("Database initialized.")

    await _create_admin_user()

    # Init Redis
    redis_conn = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await redis_conn.ping()
        logger.info("Redis connection established.")
        ws_manager.set_redis(redis_conn)
    except Exception as e:
        logger.warning("Redis not available: %s", e)

    # Long-lived Docker client through the docker-socket-proxy.
    # Best-effort: the proxy may not be reachable at startup in dev.
    from app.services.orchestration import docker_client
    try:
        docker_client.warmup()
        logger.info("Docker client warmed (seccomp profiles=%s)", list(_SECCOMP_PROFILE_HASHES))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Docker client warmup failed: %s", exc)

    # Reconciliation sweep: any ``ChallengeInstance`` whose
    # container vanished while we were down (typical after an
    # orchestrator recreate) gets marked ``expired`` so future
    # launches against the same challenge aren't blocked by stale
    # rows.
    try:
        from app.database import async_session as _async_session
        from app.services.orchestration.cleanup import sweep_orphaned_instances
        async with _async_session() as _db:
            swept = await sweep_orphaned_instances(_db)
            if swept:
                logger.info("Startup orphan sweep", count=swept)
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup_orphan_sweep_failed", error=str(exc))

    # Start scheduler
    from app.services.scheduler import setup_scheduler
    setup_scheduler()

    # Start Redis pub/sub listener
    pubsub_task = asyncio.create_task(ws_manager.start_redis_listener(redis_conn))

    yield

    # Shutdown
    logger.info("Shutting down Siege Range API...")
    pubsub_task.cancel()
    try:
        await pubsub_task
    except asyncio.CancelledError:
        pass

    from app.services.scheduler import scheduler
    scheduler.shutdown(wait=False)

    try:
        docker_client.close()
    except Exception:
        pass

    try:
        await redis_conn.close()
    except Exception:
        pass
    logger.info("Shutdown complete.")


# Expose the OpenAPI spec + Swagger UI + ReDoc only in development.
# In test/staging/production the interactive surfaces are off — they
# leak the full route + schema inventory to anonymous traffic
# (audit finding R2). Spec generation can still be invoked locally
# via `python -m app.openapi_export`.
_DOCS_ENABLED = _settings.APP_ENV == "development"

app = FastAPI(
    title="Siege Range API",
    version="2.5.0",
    lifespan=lifespan,
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
)

# Sprint 11 Phase C — opt-in OpenTelemetry tracing. No-op when
# OTEL_EXPORTER_OTLP_ENDPOINT is unset. Failure to configure
# (missing dep, bad endpoint) logs WARN and degrades to disabled
# — the platform must always boot.
from app.database import engine as _db_engine
from app.observability.tracing import configure_tracing

configure_tracing(app, _db_engine)

from app.middleware.logging_mw import LoggingMiddleware
from app.middleware.metrics import PrometheusMetricsMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

# Middleware order: outer-most runs last on the response. We want the
# request-id logger to see the response **after** security headers have
# been attached, so register the headers middleware first (it ends up
# inner-most relative to LoggingMiddleware).
app.add_middleware(SecurityHeadersMiddleware, is_production=_settings.is_production)
app.add_middleware(LoggingMiddleware)
# Prometheus metrics — outermost, so it sees the actual response
# status code Starlette returns to the client (after any later
# middleware mutates it).
app.add_middleware(PrometheusMetricsMiddleware)

_allowed_origins = _settings.allowed_origins_list()
if not _allowed_origins:
    logger.warning(
        "CORS disabled: ALLOWED_ORIGINS is empty and APP_ENV=%s",
        _settings.APP_ENV,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

# Legacy /auth/* router (R3 audit finding) removed in v2.5.1 —
# bypassed MFA and email verification. All clients must use
# /api/v1/auth/*.
from app.routers.challenges import router as challenges_router
from app.routers.health import router as health_router
from app.routers.instances import router as instances_router
from app.routers.leaderboard import router as leaderboard_router
from app.routers.stats import router as stats_router
from app.routers.writeups import router as writeups_router
from app.routers.competitions import router as competitions_router
from app.routers.notifications import router as notifications_router
from app.routers.admin import router as admin_router
from app.routers.ws import router as ws_router
from app.routers.v1 import router as api_v1_router

app.include_router(health_router)
app.include_router(challenges_router)
app.include_router(instances_router)
app.include_router(leaderboard_router)
app.include_router(stats_router)
app.include_router(writeups_router)
app.include_router(competitions_router)
app.include_router(notifications_router)
app.include_router(admin_router)
app.include_router(ws_router)
# Phase 12 (slice 1): public API v1 namespace. Locked DTOs under
# /api/v1/. Legacy unversioned routes stay live alongside until the
# front door is migrated over in a later slice.
app.include_router(api_v1_router)
