"""Integration tests for /api/v1/writeups — flag gating + full flow."""

from __future__ import annotations

import pytest

from app.models import Solve, UserRole


@pytest.fixture
def enable_flag(monkeypatch):
    def _enable(*names: str) -> None:
        allowed = set(names)
        monkeypatch.setattr(
            "app.services.feature_flags.is_enabled",
            lambda name: name in allowed,
        )

    return _enable


async def _seed_solve(db_session, user, challenge) -> None:
    db_session.add(
        Solve(user_id=user.id, challenge_id=challenge.id, points_awarded=100)
    )
    await db_session.commit()


async def test_writeups_v1_dark_when_flag_off(
    client, user_factory, auth_headers
) -> None:
    user = await user_factory()
    r = await client.get("/api/v1/writeups/anything", headers=auth_headers(user))
    assert r.status_code == 404


async def test_writeups_v1_requires_solve(
    client, user_factory, auth_headers, challenge_factory, enable_flag
) -> None:
    enable_flag("FEATURE_API_V1_WRITEUPS")
    user = await user_factory()
    chal = await challenge_factory()

    r = await client.post(
        f"/api/v1/writeups/{chal.slug}",
        json={"content": "my writeup"},
        headers=auth_headers(user),
    )
    assert r.status_code == 403


async def test_writeups_v1_create_approve_list_rate(
    client, user_factory, auth_headers, challenge_factory, db_session, enable_flag
) -> None:
    enable_flag("FEATURE_API_V1_WRITEUPS")
    author = await user_factory()
    admin = await user_factory(role=UserRole.admin)
    chal = await challenge_factory()
    await _seed_solve(db_session, author, chal)

    # Create — sanitised, unapproved.
    created = await client.post(
        f"/api/v1/writeups/{chal.slug}",
        json={"content": "<p>legit</p><script>alert(1)</script>", "title": "T"},
        headers=auth_headers(author),
    )
    assert created.status_code == 201
    wid = created.json()["id"]

    # Author has solved, so they may list — but it's unapproved yet.
    listed = await client.get(
        f"/api/v1/writeups/{chal.slug}", headers=auth_headers(author)
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    # Admin approves.
    approved = await client.put(
        f"/api/v1/writeups/{wid}/approve", headers=auth_headers(admin)
    )
    assert approved.status_code == 200

    # Now it shows up, with the script stripped by bleach.
    listed2 = await client.get(
        f"/api/v1/writeups/{chal.slug}", headers=auth_headers(author)
    )
    body = listed2.json()
    assert body["total"] == 1
    assert "<script>" not in body["items"][0]["content"]

    # Rate it.
    rated = await client.post(
        f"/api/v1/writeups/{wid}/rate",
        json={"rating": 4},
        headers=auth_headers(author),
    )
    assert rated.status_code == 200
    assert rated.json() == {"rating": 4.0, "rating_count": 1}
