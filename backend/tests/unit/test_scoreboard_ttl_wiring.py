"""The v1 scoreboard router honours ``SCOREBOARD_CACHE_TTL_SECONDS``.

``services/scoreboard_cache`` has documented this knob since Sprint 10
("Operators can flip ``SCOREBOARD_CACHE_TTL_SECONDS=0`` in config to
disable the cache entirely") but nothing ever read it: there was no such
config field, and the router called ``get_cached_scoreboard`` without
``ttl_seconds``, so the module default always won. Setting the
documented env var did nothing at all.

The cache behaviour itself is covered in
``tests/integration/test_scoreboard_cache.py``; what is asserted here is
the wiring — that the router forwards the configured value.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.routers.v1.scoreboard as scoreboard_router


@pytest.fixture
def captured_call(monkeypatch: pytest.MonkeyPatch) -> dict:
    captured: dict = {}

    async def fake_get_cached_scoreboard(db, *, team_filter, limit, ttl_seconds):
        captured.update(
            team_filter=team_filter, limit=limit, ttl_seconds=ttl_seconds
        )
        return []

    monkeypatch.setattr(
        scoreboard_router, "get_cached_scoreboard", fake_get_cached_scoreboard
    )
    return captured


def _with_ttl(monkeypatch: pytest.MonkeyPatch, ttl: int) -> None:
    monkeypatch.setattr(
        scoreboard_router,
        "get_settings",
        lambda: SimpleNamespace(SCOREBOARD_CACHE_TTL_SECONDS=ttl),
    )


class TestTtlWiring:
    async def test_forwards_the_default_ttl(self, captured_call, monkeypatch):
        _with_ttl(monkeypatch, 60)
        await scoreboard_router.scoreboard_v1(
            team=None, limit=100, _viewer=object(), db=object()
        )
        assert captured_call["ttl_seconds"] == 60

    async def test_forwards_a_zero_ttl(self, captured_call, monkeypatch):
        # 0 is the documented "disable the cache" value — the one that
        # previously had no effect whatsoever.
        _with_ttl(monkeypatch, 0)
        await scoreboard_router.scoreboard_v1(
            team=None, limit=100, _viewer=object(), db=object()
        )
        assert captured_call["ttl_seconds"] == 0

    async def test_forwards_a_custom_ttl(self, captured_call, monkeypatch):
        _with_ttl(monkeypatch, 5)
        await scoreboard_router.scoreboard_v1(
            team="red", limit=25, _viewer=object(), db=object()
        )
        assert captured_call["ttl_seconds"] == 5
        # The other query params must survive the change too.
        assert captured_call["team_filter"] == "red"
        assert captured_call["limit"] == 25


class TestConfigField:
    def test_setting_exists_with_the_audited_default(self):
        from app.config import Settings

        field = Settings.model_fields["SCOREBOARD_CACHE_TTL_SECONDS"]
        assert field.default == 60

    def test_negative_ttl_is_rejected(self):
        from pydantic import ValidationError

        from app.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="test-secret-not-a-placeholder-0123456789abcdef",
                ADMIN_PASSWORD="TestAdminPasswordA1!",
                SCOREBOARD_CACHE_TTL_SECONDS=-1,
            )
