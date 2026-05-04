"""Sprint 7 Phase B — GDPR endpoints.

Covers ``GET /api/v1/me/data`` (Article 15 right of access) and
``DELETE /api/v1/me`` (Article 17 right to erasure / anonymise).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# /api/v1/me/data
# ---------------------------------------------------------------------------
class TestExportData:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/api/v1/me/data")
        assert r.status_code in (401, 403)

    async def test_returns_all_sections(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            "/api/v1/me/data", headers=auth_headers(user)
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) >= {
            "profile", "solves", "solved_flags",
            "instances", "writeups", "hint_unlocks", "audit",
        }
        # Profile carries no hashed_password.
        assert "hashed_password" not in body["profile"]
        # Profile carries the user's id.
        assert body["profile"]["id"] == user.id

    async def test_includes_user_solves(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from datetime import datetime, timezone

        from app.models import Solve

        user = await user_factory()
        chal = await challenge_factory(slug="export-target")
        db_session.add(
            Solve(
                user_id=user.id,
                challenge_id=chal.id,
                points_awarded=100,
                is_first_blood=False,
                solved_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        r = await client.get(
            "/api/v1/me/data", headers=auth_headers(user)
        )
        body = r.json()
        assert any(s["challenge_id"] == chal.id for s in body["solves"])

    async def test_only_own_audit_rows(
        self, client, user_factory, auth_headers
    ):
        viewer = await user_factory(email="viewer@gdpr.local")
        other = await user_factory(email="other@gdpr.local")

        # Both users do something audit-emit-y.
        await client.get("/api/v1/auth/me", headers=auth_headers(viewer))
        await client.get("/api/v1/auth/me", headers=auth_headers(other))

        r = await client.get(
            "/api/v1/me/data", headers=auth_headers(viewer)
        )
        body = r.json()
        for row in body["audit"]:
            # actor_id stored as a string in the ledger.
            assert row["actor_id"] in (str(viewer.id), None)
            assert row["actor_id"] != str(other.id)

    async def test_emits_audit(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import AuditLedger

        user = await user_factory()
        await client.get(
            "/api/v1/me/data", headers=auth_headers(user)
        )
        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "auth.data.export",
                    AuditLedger.actor_id == str(user.id),
                )
            )
        ).scalars().all()
        assert rows


# ---------------------------------------------------------------------------
# DELETE /api/v1/me
# ---------------------------------------------------------------------------
class TestDeleteAccount:
    async def test_unauthenticated_rejected(self, client):
        r = await client.request(
            "DELETE", "/api/v1/me", json={"password": "anything"}
        )
        assert r.status_code in (401, 403)

    async def test_wrong_password_rejected(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory(password="GoodPass1!")
        r = await client.request(
            "DELETE",
            "/api/v1/me",
            headers=auth_headers(user),
            json={"password": "WrongPass1!"},
        )
        assert r.status_code == 401

    async def test_anonymises_user_row(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import User

        user = await user_factory(
            email="del@gdpr.local",
            username="delgdpr",
            password="GoodPass1!",
        )
        original_id = user.id

        r = await client.request(
            "DELETE",
            "/api/v1/me",
            headers=auth_headers(user),
            json={"password": "GoodPass1!"},
        )
        assert r.status_code == 200, r.text

        fresh = (
            await db_session.execute(
                select(User).where(User.id == original_id)
            )
        ).scalar_one()
        assert fresh.email == f"deleted-{original_id}@deleted.local"
        assert fresh.username == f"deleted_{original_id}"
        assert fresh.display_name == "deleted user"
        assert fresh.is_active is False
        assert fresh.team is None
        assert fresh.last_login is None

    async def test_deletes_pending_password_tokens(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import PasswordResetToken
        from app.services.password_reset import issue_token

        user = await user_factory(
            email="deltok@gdpr.local", password="GoodPass1!"
        )
        await issue_token(db_session, user)
        await db_session.commit()

        # Confirm pre-state.
        pre = (
            await db_session.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id
                )
            )
        ).scalars().all()
        assert pre

        r = await client.request(
            "DELETE",
            "/api/v1/me",
            headers=auth_headers(user),
            json={"password": "GoodPass1!"},
        )
        assert r.status_code == 200

        post = (
            await db_session.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id
                )
            )
        ).scalars().all()
        assert post == []

    async def test_emits_audit(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import AuditLedger

        user = await user_factory(
            email="delaudit@gdpr.local", password="GoodPass1!"
        )
        await client.request(
            "DELETE",
            "/api/v1/me",
            headers=auth_headers(user),
            json={"password": "GoodPass1!"},
        )
        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "auth.account.delete",
                    AuditLedger.actor_id == str(user.id),
                )
            )
        ).scalars().all()
        assert rows
