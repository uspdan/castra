"""Integration tests for /api/v1/competitions — flag gating + CRUD flow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import UserRole


@pytest.fixture
def enable_flag(monkeypatch):
    def _enable(*names: str) -> None:
        allowed = set(names)
        monkeypatch.setattr(
            "app.services.feature_flags.is_enabled",
            lambda name: name in allowed,
        )

    return _enable


def _window() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "starts_at": (now - timedelta(hours=1)).isoformat(),
        "ends_at": (now + timedelta(hours=1)).isoformat(),
    }


async def test_competitions_v1_dark_when_flag_off(
    client, user_factory, auth_headers
) -> None:
    user = await user_factory()
    r = await client.get("/api/v1/competitions", headers=auth_headers(user))
    assert r.status_code == 404


async def test_competitions_v1_create_requires_admin(
    client, user_factory, auth_headers, enable_flag
) -> None:
    enable_flag("FEATURE_API_V1_COMPETITIONS")
    user = await user_factory()
    r = await client.post(
        "/api/v1/competitions",
        json={"title": "Spring CTF", **_window()},
        headers=auth_headers(user),
    )
    assert r.status_code == 403


async def test_competitions_v1_full_flow(
    client, user_factory, auth_headers, enable_flag
) -> None:
    enable_flag("FEATURE_API_V1_COMPETITIONS")
    admin = await user_factory(role=UserRole.admin)
    player = await user_factory()

    # Admin creates a live competition.
    created = await client.post(
        "/api/v1/competitions",
        json={"title": "Spring CTF", "is_active": True, **_window()},
        headers=auth_headers(admin),
    )
    assert created.status_code == 201
    cid = created.json()["id"]

    # Player can list — sees it as live.
    listed = await client.get(
        "/api/v1/competitions", headers=auth_headers(player)
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert any(row["id"] == cid and row["is_live"] for row in rows)

    # Detail includes a (possibly empty) scoreboard when live.
    detail = await client.get(
        f"/api/v1/competitions/{cid}", headers=auth_headers(player)
    )
    assert detail.status_code == 200
    assert detail.json()["scoreboard"] == []

    # Scoreboard endpoint works standalone.
    sb = await client.get(
        f"/api/v1/competitions/{cid}/scoreboard", headers=auth_headers(player)
    )
    assert sb.status_code == 200
    assert sb.json() == []

    # Reject a bad window at validation time.
    now = datetime.now(timezone.utc)
    bad = await client.post(
        "/api/v1/competitions",
        json={
            "title": "Bad",
            "starts_at": now.isoformat(),
            "ends_at": (now - timedelta(hours=1)).isoformat(),
        },
        headers=auth_headers(admin),
    )
    assert bad.status_code == 422


async def test_competition_not_found_when_enabled(
    client, user_factory, auth_headers, enable_flag
) -> None:
    enable_flag("FEATURE_API_V1_COMPETITIONS")
    user = await user_factory()
    r = await client.get("/api/v1/competitions/99999", headers=auth_headers(user))
    assert r.status_code == 404
