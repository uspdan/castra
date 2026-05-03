"""Integration tests for the auth router.

Covers register / login / refresh / logout / me + lockout flow + audit
ledger emission. Uses the testcontainer Postgres + Redis spun by
conftest, with per-test savepoint rollback.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers — local to this file because they couple to the auth response
# shape, which is documented but not yet codified as a response_model
# (Phase 12 follow-up).
# ---------------------------------------------------------------------------
def _register_payload(**overrides):
    base = {
        "email": "newuser@test.local",
        "username": "newuser",
        "password": "GoodPassword1!",
        "display_name": "New User",
        "team": "red",
    }
    base.update(overrides)
    return base


async def _ledger_event_count(db_session, event_type: str) -> int:
    from app.models import AuditLedger

    result = await db_session.execute(
        select(AuditLedger).where(AuditLedger.event_type == event_type)
    )
    return len(result.scalars().all())


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
class TestRegister:
    async def test_creates_user_and_returns_tokens(self, client, db_session):
        response = await client.post("/auth/register", json=_register_payload())
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["username"] == "newuser"
        assert body["user"]["email"] == "newuser@test.local"
        assert body["user"]["role"] == "operator"
        assert body["access_token"]
        assert body["refresh_token"]

        from app.models import User

        result = await db_session.execute(
            select(User).where(User.username == "newuser")
        )
        user = result.scalar_one()
        assert user.email == "newuser@test.local"

    async def test_emits_audit_register_to_ledger(self, client, db_session):
        before = await _ledger_event_count(db_session, "auth.register")
        response = await client.post("/auth/register", json=_register_payload())
        assert response.status_code == 201
        after = await _ledger_event_count(db_session, "auth.register")
        assert after == before + 1

    async def test_rejects_duplicate_email(self, client, user_factory):
        await user_factory(email="dup@test.local", username="orig")
        response = await client.post(
            "/auth/register",
            json=_register_payload(email="dup@test.local", username="other"),
        )
        assert response.status_code == 409

    async def test_rejects_duplicate_username(self, client, user_factory):
        await user_factory(email="orig@test.local", username="taken")
        response = await client.post(
            "/auth/register",
            json=_register_payload(email="other@test.local", username="taken"),
        )
        assert response.status_code == 409

    async def test_rejects_short_password(self, client):
        response = await client.post(
            "/auth/register",
            json=_register_payload(password="short"),
        )
        assert response.status_code == 422

    async def test_rejects_invalid_email_format(self, client):
        response = await client.post(
            "/auth/register",
            json=_register_payload(email="not-an-email"),
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Login + lockout
# ---------------------------------------------------------------------------
class TestLogin:
    async def test_success_returns_tokens(self, client, user_factory):
        user = await user_factory(
            email="login@test.local",
            username="loginuser",
            password="LoginPassword1!",
        )
        response = await client.post(
            "/auth/login",
            json={"email": "login@test.local", "password": "LoginPassword1!"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["user"]["id"] == user.id

    async def test_emits_audit_login_success(self, client, user_factory, db_session):
        await user_factory(email="ok@test.local", password="LoginPassword1!")
        before = await _ledger_event_count(db_session, "auth.login.success")
        response = await client.post(
            "/auth/login",
            json={"email": "ok@test.local", "password": "LoginPassword1!"},
        )
        assert response.status_code == 200
        after = await _ledger_event_count(db_session, "auth.login.success")
        assert after == before + 1

    async def test_rejects_wrong_password(self, client, user_factory, db_session):
        await user_factory(email="bad@test.local", password="LoginPassword1!")
        before = await _ledger_event_count(db_session, "auth.login.failed")
        response = await client.post(
            "/auth/login",
            json={"email": "bad@test.local", "password": "WrongPassword!"},
        )
        assert response.status_code == 401
        after = await _ledger_event_count(db_session, "auth.login.failed")
        assert after == before + 1

    async def test_rejects_unknown_user(self, client, db_session):
        before = await _ledger_event_count(db_session, "auth.login.failed")
        response = await client.post(
            "/auth/login",
            json={"email": "nobody@test.local", "password": "Whatever1!"},
        )
        assert response.status_code == 401
        after = await _ledger_event_count(db_session, "auth.login.failed")
        # Even unknown-user attempts must be audited; otherwise enumeration
        # against the API leaves no trace.
        assert after == before + 1

    async def test_rejects_disabled_account(self, client, user_factory):
        await user_factory(
            email="off@test.local", password="LoginPassword1!", is_active=False
        )
        response = await client.post(
            "/auth/login",
            json={"email": "off@test.local", "password": "LoginPassword1!"},
        )
        assert response.status_code == 403

    async def test_lockout_after_five_failed_attempts(
        self, client, user_factory, redis_client
    ):
        # Lockout is enforced via Redis counter; the testcontainer Redis
        # gets flushed per-test, so 5 misses → 6th call is 429.
        await user_factory(email="lock@test.local", password="LoginPassword1!")
        for _ in range(5):
            r = await client.post(
                "/auth/login",
                json={"email": "lock@test.local", "password": "wrong!"},
            )
            assert r.status_code == 401

        r = await client.post(
            "/auth/login",
            json={"email": "lock@test.local", "password": "LoginPassword1!"},
        )
        assert r.status_code == 429

    async def test_successful_login_clears_failure_counter(
        self, client, user_factory, redis_client
    ):
        await user_factory(email="reset@test.local", password="LoginPassword1!")
        for _ in range(3):
            await client.post(
                "/auth/login",
                json={"email": "reset@test.local", "password": "wrong!"},
            )

        r = await client.post(
            "/auth/login",
            json={"email": "reset@test.local", "password": "LoginPassword1!"},
        )
        assert r.status_code == 200

        failures = await redis_client.get(b"login_failures:reset@test.local")
        assert failures is None or int(failures) == 0


# ---------------------------------------------------------------------------
# Refresh + logout
# ---------------------------------------------------------------------------
class TestRefresh:
    async def _login(self, client, user_factory, **kwargs):
        user = await user_factory(
            email="rf@test.local", password="LoginPassword1!", **kwargs
        )
        r = await client.post(
            "/auth/login",
            json={"email": "rf@test.local", "password": "LoginPassword1!"},
        )
        assert r.status_code == 200
        return user, r.json()

    async def test_returns_new_access_token(self, client, user_factory):
        _, tokens = await self._login(client, user_factory)
        r = await client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert r.status_code == 200
        assert r.json()["access_token"]
        assert r.json()["token_type"] == "bearer"

    async def test_rejects_access_token_used_as_refresh(self, client, user_factory):
        _, tokens = await self._login(client, user_factory)
        r = await client.post(
            "/auth/refresh", json={"refresh_token": tokens["access_token"]}
        )
        assert r.status_code == 401

    async def test_rejects_blacklisted_refresh_token(self, client, user_factory):
        _, tokens = await self._login(client, user_factory)

        logout = await client.post(
            "/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        )
        assert logout.status_code == 200

        r = await client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert r.status_code == 401


class TestLogout:
    async def test_revokes_refresh_token(self, client, user_factory, redis_client):
        user = await user_factory(email="lo@test.local", password="LoginPassword1!")
        login = await client.post(
            "/auth/login",
            json={"email": "lo@test.local", "password": "LoginPassword1!"},
        )
        refresh_token = login.json()["refresh_token"]

        r = await client.post(
            "/auth/logout", json={"refresh_token": refresh_token}
        )
        assert r.status_code == 200
        # MessageResponse adds an optional `detail` field — ignore it.
        assert r.json()["message"] == "Logged out"

        blacklisted = await redis_client.get(
            f"siege:blacklist:{refresh_token}".encode()
        )
        assert blacklisted == b"1"

    async def test_logout_with_no_token_still_succeeds(self, client):
        # Anonymous logout (no token in body) must still 200 — clients
        # call logout on app close regardless of session state.
        r = await client.post("/auth/logout", json={})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------
class TestMe:
    async def test_returns_user_with_aggregates(self, client, user_factory, auth_headers):
        user = await user_factory(email="me@test.local", username="meuser")
        r = await client.get("/auth/me", headers=auth_headers(user))
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == user.id
        assert body["username"] == "meuser"
        assert body["total_points"] == 0
        assert body["total_solves"] == 0
        assert body["current_streak"] == 0
        assert body["rank"] == 1  # nobody else has points

    async def test_rejects_missing_auth(self, client):
        r = await client.get("/auth/me")
        assert r.status_code == 401

    async def test_rejects_invalid_token(self, client):
        r = await client.get(
            "/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert r.status_code == 401
