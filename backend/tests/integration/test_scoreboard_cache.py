"""Sprint 10 Phase D — scoreboard Redis cache."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.scoreboard_cache import (
    _cache_key,
    get_cached_scoreboard,
)


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# _cache_key
# ---------------------------------------------------------------------------
class TestCacheKey:
    def test_includes_team_and_limit(self):
        assert _cache_key(team="red", limit=50) == "siege:scoreboard:v1:red:50"
        assert _cache_key(team=None, limit=100) == "siege:scoreboard:v1:all:100"


# ---------------------------------------------------------------------------
# get_cached_scoreboard
# ---------------------------------------------------------------------------
class _FakeRedis:
    """In-memory key/value with TTL ignored (one test only checks
    miss + hit symmetry; another exercises the failure path)."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple] = []

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.set_calls.append((key, value, ex))
        self.store[key] = value

    async def delete(self, key):
        self.store.pop(key, None)

    async def aclose(self):
        return None


class TestCachedScoreboard:
    async def test_miss_then_hit_returns_same_rows(
        self, client, user_factory, auth_headers
    ):
        # Smoke: hit /api/v1/scoreboard twice; second call should
        # return identical entries (cache hit on a real Redis).
        user = await user_factory()
        r1 = await client.get(
            "/api/v1/scoreboard", headers=auth_headers(user)
        )
        assert r1.status_code == 200
        r2 = await client.get(
            "/api/v1/scoreboard", headers=auth_headers(user)
        )
        assert r2.status_code == 200
        assert r1.json()["entries"] == r2.json()["entries"]

    async def test_writes_to_redis_on_miss(self, db_session):
        fake = _FakeRedis()
        rows = await get_cached_scoreboard(
            db_session, team_filter=None, limit=10, redis_client=fake
        )
        # Cache write happened.
        assert any("siege:scoreboard:v1:" in c[0] for c in fake.set_calls)
        # Stored value parses back to a list.
        cached_value = fake.store[_cache_key(team=None, limit=10)]
        parsed = json.loads(cached_value)
        assert isinstance(parsed, list)
        assert len(parsed) == len(rows)

    async def test_returns_cache_on_hit(self, db_session):
        fake = _FakeRedis()
        # First call populates.
        await get_cached_scoreboard(
            db_session, team_filter=None, limit=10, redis_client=fake
        )
        # Second call should NOT trigger another set.
        before_sets = len(fake.set_calls)
        await get_cached_scoreboard(
            db_session, team_filter=None, limit=10, redis_client=fake
        )
        assert len(fake.set_calls) == before_sets

    async def test_corrupt_cache_falls_back(self, db_session):
        fake = _FakeRedis()
        fake.store[_cache_key(team=None, limit=10)] = "not-json"
        # Should not raise; falls through to live compute + rewrites.
        rows = await get_cached_scoreboard(
            db_session, team_filter=None, limit=10, redis_client=fake
        )
        assert isinstance(rows, list)

    async def test_redis_failure_degrades_gracefully(self, db_session):
        fake = AsyncMock()
        fake.get = AsyncMock(side_effect=RuntimeError("redis down"))
        # Should not raise; live-computes the scoreboard.
        rows = await get_cached_scoreboard(
            db_session, team_filter=None, limit=10, redis_client=fake
        )
        assert isinstance(rows, list)

    async def test_zero_ttl_disables_cache(self, db_session):
        fake = _FakeRedis()
        rows = await get_cached_scoreboard(
            db_session,
            team_filter=None,
            limit=10,
            redis_client=fake,
            ttl_seconds=0,
        )
        # No reads, no writes — cache bypassed entirely.
        assert fake.set_calls == []
        assert fake.store == {}
        assert isinstance(rows, list)
