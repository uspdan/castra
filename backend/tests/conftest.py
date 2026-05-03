"""Pytest fixtures for the seige-range backend.

Lifecycle (session-scoped, in order):
    1. Set the env vars that ``app.config.Settings`` requires *before* any
       ``app.*`` module is imported. SECRET_KEY / ADMIN_PASSWORD / APP_ENV
       are static; DATABASE_URL / REDIS_URL come from testcontainers.
    2. Spin ephemeral Postgres + Redis via testcontainers.
    3. Run ``alembic upgrade head`` against the testcontainer Postgres so
       the audit-ledger immutability trigger from migration 002 is in place
       (closes the dev-only ``create_all`` gap noted in Phase 2).
    4. Lazy-import ``app.*`` modules — by this point ``get_settings()`` is
       still uncached and resolves to the testcontainer URLs.

Per-test isolation uses the canonical SQLAlchemy 2.0 "join external
transaction" pattern: a single connection holds an outer transaction;
the AsyncSession bound to it uses
``join_transaction_mode="create_savepoint"``, which converts every
``begin()`` / ``commit()`` the routers issue into a SAVEPOINT under the
outer tx. Rolling back the outer tx at teardown wipes everything,
regardless of how many ``await db.commit()`` calls the handler made.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator, Iterator

import pytest


# ---------------------------------------------------------------------------
# 1. Env defaults BEFORE any app.* import. Settings rejects placeholders, so
#    the secret here must look real (not 'change-me') and be ≥32 chars.
# ---------------------------------------------------------------------------
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault(
    "SECRET_KEY",
    "test-secret-not-for-production-0123456789abcdef0123456789abcdef",
)
os.environ.setdefault("ADMIN_PASSWORD", "TestAdminPasswordA1!")
os.environ.setdefault("ADMIN_EMAIL", "admin-test@siege.local")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")


# ---------------------------------------------------------------------------
# 2. Testcontainers — session-scoped. testcontainers 4.x exposes context
#    managers; we drive them as a session fixture so finalisation is tied
#    to pytest's own teardown.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def _postgres_url() -> Iterator[str]:
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        # PostgresContainer returns a psycopg2 URL; rewrite for asyncpg.
        url = pg.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )
        yield url


@pytest.fixture(scope="session")
def _redis_url() -> Iterator[str]:
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as r:
        host = r.get_container_host_ip()
        port = r.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


# ---------------------------------------------------------------------------
# 3. Push the testcontainer URLs into the env, clear get_settings cache,
#    then run alembic. Order matters: get_settings() must resolve to the
#    testcontainer URLs the first time it is consulted (notably by
#    migrations/env.py and app.database).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def _bootstrap_env(_postgres_url: str, _redis_url: str) -> Iterator[None]:
    os.environ["DATABASE_URL"] = _postgres_url
    os.environ["REDIS_URL"] = _redis_url

    # If anything imported app.config before us (it shouldn't — we're an
    # autouse fixture, but be defensive), drop the cache.
    from app.config import _build_settings

    _build_settings.cache_clear()

    # Defence in depth: if a test file imported ``app.database`` at module
    # top before this fixture ran, its ``engine`` is bound to whatever URL
    # the default Settings produced (a docker-network host that doesn't
    # exist on the test runner). Rebuild it against the testcontainer URL
    # so subsequent fixture calls hit the right DB regardless of import
    # order.
    import sys
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    # NullPool: pytest-asyncio 0.23 creates a fresh event loop per test by
    # default. Pooled asyncpg connections bound to a closed loop raise
    # "Event loop is closed" on the next test's teardown. NullPool avoids
    # that by never holding connections across tests — every connect()
    # opens a fresh asyncpg socket, every close() tears it down.
    from sqlalchemy.pool import NullPool

    db_module = sys.modules.get("app.database")
    if db_module is None:
        import app.database as db_module  # noqa: F811 — late import is intentional

    new_engine = create_async_engine(
        _postgres_url, echo=False, poolclass=NullPool
    )
    db_module.engine = new_engine
    db_module.async_session = async_sessionmaker(
        new_engine, class_=AsyncSession, expire_on_commit=False
    )

    # Run alembic upgrade head against the freshly created testcontainer DB.
    # alembic env.py reads DATABASE_URL via get_settings(), which now
    # resolves to the testcontainer URL.
    from alembic import command
    from alembic.config import Config

    backend_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", _postgres_url)
    command.upgrade(cfg, "head")

    yield


# ---------------------------------------------------------------------------
# 4. Per-test connection + outer transaction + savepoint-mode session.
# ---------------------------------------------------------------------------
@pytest.fixture
async def db_session(_bootstrap_env: None) -> AsyncIterator["AsyncSession"]:
    # Lazy import — env is now set up.
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.database import engine

    async with engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            if outer.is_active:
                await outer.rollback()


@pytest.fixture
async def redis_client(_bootstrap_env: None) -> AsyncIterator["aioredis.Redis"]:
    import redis.asyncio as aioredis
    from app.config import get_settings

    settings = get_settings()
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    await client.flushdb()
    try:
        yield client
    finally:
        try:
            await client.flushdb()
        finally:
            await client.aclose()


# ---------------------------------------------------------------------------
# 5. FastAPI client with overridden dependencies. The httpx.ASGITransport
#    does NOT trigger the lifespan handler — that's what we want, since
#    the app's lifespan creates an admin user, starts the scheduler, and
#    spawns a Redis pub/sub task that we don't need in tests.
# ---------------------------------------------------------------------------
@pytest.fixture
async def client(
    db_session: "AsyncSession",
    redis_client: "aioredis.Redis",
) -> AsyncIterator["AsyncClient"]:
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.database import get_db
    from app.routers.auth import get_redis

    async def _override_db():
        yield db_session

    async def _override_redis():
        yield redis_client

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_redis] = _override_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Factories — minimal, explicit. Keep tests readable; no faker.
# ---------------------------------------------------------------------------
@pytest.fixture
def user_factory(db_session):
    from datetime import datetime, timezone
    from app.models import User, UserRole, TeamType
    from app.services.auth import hash_password

    counter = {"n": 0}

    async def _make(
        *,
        email: str | None = None,
        username: str | None = None,
        password: str = "TestUserPasswordA1!",
        role: UserRole = UserRole.operator,
        team: TeamType | None = None,
        is_active: bool = True,
    ) -> User:
        counter["n"] += 1
        n = counter["n"]
        u = User(
            email=email or f"user{n}@test.local",
            username=username or f"user{n}",
            display_name=username or f"User {n}",
            hashed_password=hash_password(password),
            role=role,
            team=team,
            is_active=is_active,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(u)
        await db_session.commit()
        await db_session.refresh(u)
        return u

    return _make


@pytest.fixture
def challenge_factory(db_session):
    from datetime import datetime, timezone
    from app.models import Challenge, TeamType
    from app.validators.exact import hash_exact_value

    counter = {"n": 0}

    async def _make(
        *,
        slug: str | None = None,
        title: str | None = None,
        flag: str = "CTF{REDACTED}",
        points: int = 100,
        team: TeamType = TeamType.red,
        category: str = "web",
        difficulty: int = 2,
        is_released: bool = True,
        is_active: bool = True,
        prerequisite_ids: list[int] | None = None,
        hints: list[str] | None = None,
    ) -> Challenge:
        counter["n"] += 1
        n = counter["n"]
        c = Challenge(
            slug=slug or f"chal-{n}",
            title=title or f"Challenge {n}",
            description=f"Description for challenge {n}",
            category=category,
            team=team,
            difficulty=difficulty,
            points=points,
            flag_hash=hash_exact_value(flag),
            hints=hints or [],
            skills=[],
            mitre_techniques=[],
            docker_image="alpine:3.19",
            docker_port=8080,
            docker_config={},
            prerequisite_ids=prerequisite_ids or [],
            is_active=is_active,
            is_released=is_released,
            released_at=datetime.now(timezone.utc) if is_released else None,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(c)
        await db_session.commit()
        await db_session.refresh(c)
        return c

    return _make


@pytest.fixture
def auth_token():
    """Mint an access token for an existing User row without going through HTTP."""

    from app.services.auth import create_access_token

    def _make(user) -> str:
        return create_access_token(user.id, user.role.value)

    return _make


@pytest.fixture
def auth_headers(auth_token):
    def _make(user) -> dict[str, str]:
        return {"Authorization": f"Bearer {auth_token(user)}"}

    return _make
