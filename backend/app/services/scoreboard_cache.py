"""Redis-backed cache for the v1 scoreboard.

Sprint 10 Phase D. The scoreboard endpoint receives heavy traffic
during competitions and re-derives via N+1 SQL each call (every
active user spawns a points + solves + streak query). This wrapper
caches the rendered :class:`ScoreboardRow` list under a key keyed
on ``(team_filter, limit)``, with a 60-second TTL.

Cache miss = compute + write. Cache hit = JSON parse + return.
TTL-only invalidation: a fresh solve becomes visible at most one
minute later. Operators can flip ``SCOREBOARD_CACHE_TTL_SECONDS=0``
in config to disable the cache entirely (forces every request to
re-derive — useful while debugging).
"""

from __future__ import annotations

import json
from typing import List, Optional

import redis.asyncio as aioredis
import structlog

from app.config import get_settings
from app.services.api_v1 import ScoreboardRow, compute_scoreboard


logger = structlog.get_logger()


_DEFAULT_TTL_SECONDS = 60


def _cache_key(*, team: Optional[str], limit: int) -> str:
    return f"siege:scoreboard:v1:{team or 'all'}:{limit}"


async def _redis_client():
    settings = get_settings()
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_cached_scoreboard(
    db,
    *,
    team_filter: Optional[str] = None,
    limit: int = 100,
    redis_client=None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> List[ScoreboardRow]:
    """Cached wrapper around :func:`compute_scoreboard`.

    On cache miss: computes, writes to Redis with ``ttl_seconds``.
    On cache hit: returns the parsed list. On any Redis error:
    logs a warning and falls through to the live computation
    (graceful degradation per CLAUDE.md §15.4).

    ``redis_client`` is for tests that want to inject a stub /
    fake. Production callers leave it None.

    ``ttl_seconds=0`` disables the cache entirely.
    """

    if ttl_seconds <= 0:
        return await compute_scoreboard(
            db, team_filter=team_filter, limit=limit
        )

    key = _cache_key(team=team_filter, limit=limit)
    owns_client = redis_client is None
    if owns_client:
        redis_client = await _redis_client()

    try:
        cached = await redis_client.get(key)
        if cached is not None:
            try:
                payload = json.loads(cached)
                return [ScoreboardRow(**row) for row in payload]
            except (json.JSONDecodeError, TypeError):
                # Corrupt cache entry — drop and re-derive.
                await redis_client.delete(key)

        rows = await compute_scoreboard(
            db, team_filter=team_filter, limit=limit
        )
        try:
            await redis_client.set(
                key,
                json.dumps([row.__dict__ for row in rows]),
                ex=ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort write
            logger.warning(
                "scoreboard.cache_write_failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        return rows
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning(
            "scoreboard.cache_read_failed",
            error=f"{type(exc).__name__}: {exc}",
        )
        return await compute_scoreboard(
            db, team_filter=team_filter, limit=limit
        )
    finally:
        if owns_client:
            try:
                await redis_client.aclose()
            except Exception:  # noqa: BLE001
                pass


__all__ = ["get_cached_scoreboard"]
