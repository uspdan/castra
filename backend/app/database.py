import os

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = structlog.get_logger()

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Bootstrap the schema on startup.

    Two paths:

    * **Production / staging** — ``backend/entrypoint.sh`` runs
      ``alembic upgrade head`` *before* uvicorn boots, then exports
      ``DB_MIGRATIONS_MANAGED_EXTERNALLY=1``. We skip ``create_all``
      here so the schema is migration-driven (alembic owns DROPs,
      ALTERs, plpgsql triggers, etc.).

    * **Tests / dev without an entrypoint** — the env var is unset.
      ``Base.metadata.create_all`` runs as a safety net so a fresh
      developer can ``docker run python -m uvicorn …`` without
      a separate alembic step. (Tests use the
      ``conftest._bootstrap_env`` fixture which runs alembic
      explicitly anyway, so this branch is dev-only.)
    """

    if os.environ.get("DB_MIGRATIONS_MANAGED_EXTERNALLY") == "1":
        logger.info("init_db.skip_create_all", reason="alembic_managed")
        return

    from app.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("init_db.create_all_complete")
