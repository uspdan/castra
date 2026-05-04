"""Integration tests for the public ``/api/v1/auth/*`` surface.

The legacy ``/auth/*`` endpoints already have a coverage suite
(``test_auth.py``); this file freezes the v1 contract:

- Locked DTO: ``ConfigDict(extra="forbid")`` + explicit field set.
- Schema rejects malformed input (email, username, password, team).
- Response shapes contain only the documented fields — no SQL columns
  leak via the ``User`` row.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


_USER_FIELDS = {
    "id",
    "username",
    "display_name",
    "email",
    "role",
    "team",
    "is_active",
    "created_at",
    "last_login",
    "mfa_enabled",
}

_TOKEN_PAIR_FIELDS = {"user", "access_token", "refresh_token", "token_type"}


def _register_payload(**overrides):
    base = {
        "email": "v1user@test.local",
        "username": "v1user",
        "password": "GoodPassword1!",
        "display_name": "V1 User",
        "team": "red",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------
class TestRegisterV1:
    async def test_happy_path(self, client, db_session):
        r = await client.post(
            "/api/v1/auth/register", json=_register_payload()
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert set(body.keys()) == _TOKEN_PAIR_FIELDS
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["refresh_token"]
        assert set(body["user"].keys()) == _USER_FIELDS
        assert body["user"]["username"] == "v1user"
        assert body["user"]["email"] == "v1user@test.local"
        assert body["user"]["role"] == "operator"
        assert body["user"]["team"] == "red"
        assert body["user"]["is_active"] is True

        from app.models import User

        row = (
            await db_session.execute(
                select(User).where(User.username == "v1user")
            )
        ).scalar_one()
        assert row.email == "v1user@test.local"

    async def test_rejects_unknown_field(self, client):
        payload = _register_payload(extra_field="reject-me")
        r = await client.post("/api/v1/auth/register", json=payload)
        assert r.status_code == 422

    async def test_rejects_short_password(self, client):
        r = await client.post(
            "/api/v1/auth/register",
            json=_register_payload(password="short"),
        )
        assert r.status_code == 422

    async def test_rejects_invalid_email(self, client):
        r = await client.post(
            "/api/v1/auth/register",
            json=_register_payload(email="not-an-email"),
        )
        assert r.status_code == 422

    async def test_rejects_invalid_username(self, client):
        r = await client.post(
            "/api/v1/auth/register",
            json=_register_payload(username="x"),  # too short
        )
        assert r.status_code == 422

    async def test_rejects_invalid_team(self, client):
        r = await client.post(
            "/api/v1/auth/register",
            json=_register_payload(team="purple"),
        )
        assert r.status_code == 422

    async def test_rejects_duplicate_email(self, client, user_factory):
        await user_factory(email="dup@test.local", username="orig")
        r = await client.post(
            "/api/v1/auth/register",
            json=_register_payload(email="dup@test.local", username="other"),
        )
        assert r.status_code == 409

    async def test_rejects_duplicate_username(self, client, user_factory):
        await user_factory(email="orig@test.local", username="dupname")
        r = await client.post(
            "/api/v1/auth/register",
            json=_register_payload(
                email="newone@test.local", username="dupname"
            ),
        )
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------
class TestLoginV1:
    async def test_happy_path(self, client, user_factory):
        user = await user_factory(
            email="login@test.local",
            username="loginuser",
            password="LoginPassword1!",
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.local", "password": "LoginPassword1!"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == _TOKEN_PAIR_FIELDS
        assert set(body["user"].keys()) == _USER_FIELDS
        assert body["user"]["id"] == user.id
        assert body["access_token"]
        assert body["refresh_token"]

    async def test_rejects_bad_password(self, client, user_factory):
        await user_factory(
            email="badpw@test.local",
            username="badpwuser",
            password="GoodPassword1!",
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "badpw@test.local", "password": "WrongPassword1!"},
        )
        assert r.status_code == 401

    async def test_rejects_unknown_user(self, client):
        r = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "ghost@test.local",
                "password": "AnyPassword1!",
            },
        )
        assert r.status_code == 401

    async def test_rejects_inactive_user(self, client, user_factory):
        await user_factory(
            email="inactive@test.local",
            username="inactiveuser",
            password="GoodPassword1!",
            is_active=False,
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "inactive@test.local",
                "password": "GoodPassword1!",
            },
        )
        assert r.status_code == 403

    async def test_normalizes_email_case(self, client, user_factory):
        await user_factory(
            email="case@test.local",
            username="caseuser",
            password="GoodPassword1!",
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "CASE@TEST.REDACTED", "password": "GoodPassword1!"},
        )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------
class TestRefreshV1:
    async def test_happy_path(self, client, user_factory):
        from app.services.auth import create_refresh_token

        user = await user_factory(email="ref@test.local")
        rt = create_refresh_token(user.id)
        r = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": rt}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"access_token", "token_type"}
        assert body["token_type"] == "bearer"
        assert body["access_token"]

    async def test_rejects_access_token(self, client, user_factory):
        from app.services.auth import create_access_token

        user = await user_factory(email="ref-acc@test.local")
        at = create_access_token(user.id, user.role.value)
        r = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": at}
        )
        assert r.status_code == 401

    async def test_rejects_garbage(self, client):
        r = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not-a-real-token"},
        )
        assert r.status_code == 401

    async def test_rejects_inactive_user(self, client, user_factory):
        from app.services.auth import create_refresh_token

        user = await user_factory(
            email="ref-off@test.local", is_active=False
        )
        rt = create_refresh_token(user.id)
        r = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": rt}
        )
        assert r.status_code == 401

    async def test_rejects_blacklisted_token(self, client, user_factory, redis_client):
        from app.services.auth import create_refresh_token

        user = await user_factory(email="ref-bl@test.local")
        rt = create_refresh_token(user.id)
        await redis_client.set(f"siege:blacklist:{rt}", "1", ex=600)
        r = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": rt}
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------
class TestLogoutV1:
    async def test_happy_path_blacklists_refresh(
        self, client, user_factory, redis_client
    ):
        from app.services.auth import create_refresh_token

        user = await user_factory(email="logout@test.local")
        rt = create_refresh_token(user.id)
        r = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": rt}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"message"}
        assert body["message"] == "Logged out"
        assert await redis_client.get(f"siege:blacklist:{rt}") is not None

    async def test_logout_without_token_is_idempotent(self, client):
        r = await client.post("/api/v1/auth/logout", json={})
        assert r.status_code == 200
        assert r.json() == {"message": "Logged out"}


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------
class TestAuthMeV1:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/api/v1/auth/me")
        assert r.status_code in (401, 403)

    async def test_returns_locked_user_shape(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory(email="me@test.local", username="meu")
        r = await client.get("/api/v1/auth/me", headers=auth_headers(user))
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == _USER_FIELDS
        assert body["id"] == user.id
        assert body["username"] == "meu"
