"""Sprint 7 Phase A — account settings endpoints.

Covers ``POST /api/v1/auth/change-password`` and
``PATCH /api/v1/auth/profile``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# /api/v1/auth/change-password
# ---------------------------------------------------------------------------
class TestChangePassword:
    async def test_unauthenticated_rejected(self, client):
        r = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "x", "new_password": "Newer123!"},
        )
        assert r.status_code in (401, 403)

    async def test_happy_path(self, client, user_factory, auth_headers, db_session):
        from app.models import User
        from app.services.auth import verify_password

        user = await user_factory(
            email="cp@test.local", username="cpuser", password="OriginalPass1!"
        )
        r = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers(user),
            json={
                "current_password": "OriginalPass1!",
                "new_password": "NewPass2@",
            },
        )
        assert r.status_code == 200, r.text
        assert "changed" in r.json()["message"].lower()

        fresh = (
            await db_session.execute(select(User).where(User.id == user.id))
        ).scalar_one()
        assert verify_password("NewPass2@", fresh.hashed_password)
        assert not verify_password("OriginalPass1!", fresh.hashed_password)

    async def test_wrong_current_rejected(self, client, user_factory, auth_headers):
        user = await user_factory(
            email="cpw@test.local", password="GoodPass1!"
        )
        r = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers(user),
            json={
                "current_password": "WrongPass1!",
                "new_password": "AnotherPass2@",
            },
        )
        assert r.status_code == 401

    async def test_short_new_rejected(self, client, user_factory, auth_headers):
        user = await user_factory(password="GoodPass1!")
        r = await client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers(user),
            json={
                "current_password": "GoodPass1!",
                "new_password": "tiny",
            },
        )
        assert r.status_code == 422

    async def test_audit_emitted(self, client, user_factory, auth_headers, db_session):
        from app.models import AuditLedger

        user = await user_factory(password="GoodPass1!")
        await client.post(
            "/api/v1/auth/change-password",
            headers=auth_headers(user),
            json={
                "current_password": "GoodPass1!",
                "new_password": "NewPass2@",
            },
        )
        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "auth.password.change"
                )
            )
        ).scalars().all()
        assert rows


# ---------------------------------------------------------------------------
# /api/v1/auth/profile (PATCH)
# ---------------------------------------------------------------------------
class TestProfileUpdate:
    async def test_updates_display_name(self, client, user_factory, auth_headers, db_session):
        from app.models import User

        user = await user_factory()
        r = await client.patch(
            "/api/v1/auth/profile",
            headers=auth_headers(user),
            json={"display_name": "New Name"},
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == "New Name"

        fresh = (
            await db_session.execute(select(User).where(User.id == user.id))
        ).scalar_one()
        assert fresh.display_name == "New Name"

    async def test_updates_team(self, client, user_factory, auth_headers, db_session):
        from app.models import TeamType, User

        user = await user_factory(team=TeamType.red)
        r = await client.patch(
            "/api/v1/auth/profile",
            headers=auth_headers(user),
            json={"team": "blue"},
        )
        assert r.status_code == 200
        assert r.json()["team"] == "blue"

        fresh = (
            await db_session.execute(select(User).where(User.id == user.id))
        ).scalar_one()
        assert fresh.team == TeamType.blue

    async def test_rejects_unknown_field(self, client, user_factory, auth_headers):
        user = await user_factory()
        r = await client.patch(
            "/api/v1/auth/profile",
            headers=auth_headers(user),
            json={"role": "admin"},  # not editable here
        )
        assert r.status_code == 422

    async def test_rejects_bad_team(self, client, user_factory, auth_headers):
        user = await user_factory()
        r = await client.patch(
            "/api/v1/auth/profile",
            headers=auth_headers(user),
            json={"team": "purple"},
        )
        assert r.status_code == 422

    async def test_no_op_returns_current(self, client, user_factory, auth_headers):
        user = await user_factory()
        r = await client.patch(
            "/api/v1/auth/profile",
            headers=auth_headers(user),
            json={},
        )
        assert r.status_code == 200
        assert r.json()["id"] == user.id

    async def test_audit_emitted(self, client, user_factory, auth_headers, db_session):
        from app.models import AuditLedger

        user = await user_factory()
        await client.patch(
            "/api/v1/auth/profile",
            headers=auth_headers(user),
            json={"display_name": "Audited"},
        )
        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "auth.profile.update"
                )
            )
        ).scalars().all()
        assert rows
