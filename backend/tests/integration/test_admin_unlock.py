"""Integration tests for POST /api/v1/admin/users/{id}/unlock.

The endpoint clears the Redis ``login_failures:{email}`` counter that
``check_account_lockout`` enforces, so a player locked out mid-event
doesn't have to wait out the 15-minute window.
"""

from __future__ import annotations

import pytest

from app.models import UserRole


pytestmark = pytest.mark.integration


class TestUnlockUserV1:
    async def test_requires_admin_role(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            f"/api/v1/admin/users/{user.id}/unlock",
            headers=auth_headers(user),
        )
        assert r.status_code == 403

    async def test_unauthenticated_rejected(self, client, user_factory):
        user = await user_factory()
        r = await client.post(f"/api/v1/admin/users/{user.id}/unlock")
        assert r.status_code in (401, 403)

    async def test_unknown_user_404(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/admin/users/999999/unlock",
            headers=auth_headers(admin),
        )
        assert r.status_code == 404

    async def test_clears_lockout_counter(
        self, client, user_factory, auth_headers, redis_client
    ):
        admin = await user_factory(role=UserRole.admin)
        user = await user_factory()
        key = f"login_failures:{user.email}"
        await redis_client.set(key, "5", ex=900)

        r = await client.post(
            f"/api/v1/admin/users/{user.id}/unlock",
            headers=auth_headers(admin),
        )

        assert r.status_code == 200
        assert r.json() == {"user_id": user.id, "was_locked": True}
        assert await redis_client.get(key) is None

    async def test_unlocked_account_reports_not_locked(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        user = await user_factory()

        r = await client.post(
            f"/api/v1/admin/users/{user.id}/unlock",
            headers=auth_headers(admin),
        )

        assert r.status_code == 200
        assert r.json() == {"user_id": user.id, "was_locked": False}

    async def test_locked_user_can_login_after_unlock(
        self, client, user_factory, auth_headers, redis_client
    ):
        admin = await user_factory(role=UserRole.admin)
        user = await user_factory(password="KnownPassw0rd!")
        key = f"login_failures:{user.email}"
        await redis_client.set(key, "5", ex=900)

        locked = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "KnownPassw0rd!"},
        )
        assert locked.status_code == 429

        r = await client.post(
            f"/api/v1/admin/users/{user.id}/unlock",
            headers=auth_headers(admin),
        )
        assert r.status_code == 200

        unlocked = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "KnownPassw0rd!"},
        )
        assert unlocked.status_code == 200
