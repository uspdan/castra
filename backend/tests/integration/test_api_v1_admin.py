"""Integration tests for the v1 admin write surface."""

from __future__ import annotations

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


_CHAL_FIELDS = {
    "id",
    "slug",
    "title",
    "category",
    "team",
    "difficulty",
    "points",
    "is_released",
    "is_active",
    "released_at",
    "created_at",
}

_USER_FIELDS = {
    "id",
    "username",
    "email",
    "display_name",
    "role",
    "team",
    "is_active",
    "created_at",
}


def _challenge_payload(**overrides):
    base = {
        "title": "V1 Admin Challenge",
        "slug": "v1-admin-1",
        "description": "Created via /api/v1/admin/challenges",
        "category": "web",
        "team": "red",
        "difficulty": 2,
        "points": 100,
        "flag": "CTF{REDACTED}",
        "docker_image": "alpine:3.19",
        "docker_port": 8080,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Challenge create
# ---------------------------------------------------------------------------
class TestCreateChallengeV1:
    async def test_requires_admin_role(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            "/api/v1/admin/challenges",
            headers=auth_headers(user),
            json=_challenge_payload(),
        )
        assert r.status_code == 403

    async def test_unauthenticated_rejected(self, client):
        r = await client.post(
            "/api/v1/admin/challenges", json=_challenge_payload()
        )
        assert r.status_code in (401, 403)

    async def test_happy_path(self, client, user_factory, auth_headers):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/admin/challenges",
            headers=auth_headers(admin),
            json=_challenge_payload(slug="v1-admin-ok"),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert set(body.keys()) == _CHAL_FIELDS
        assert body["slug"] == "v1-admin-ok"
        assert body["is_released"] is False
        assert body["team"] == "red"

    async def test_rejects_unknown_field(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/admin/challenges",
            headers=auth_headers(admin),
            json=_challenge_payload(extra="reject-me"),
        )
        assert r.status_code == 422

    async def test_rejects_bad_flag(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/admin/challenges",
            headers=auth_headers(admin),
            json=_challenge_payload(flag="not-a-ctf-flag"),
        )
        assert r.status_code == 422

    async def test_rejects_duplicate_slug(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        await challenge_factory(slug="v1-admin-dup")
        r = await client.post(
            "/api/v1/admin/challenges",
            headers=auth_headers(admin),
            json=_challenge_payload(slug="v1-admin-dup"),
        )
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# Challenge update
# ---------------------------------------------------------------------------
class TestUpdateChallengeV1:
    async def test_happy_path(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        await challenge_factory(slug="v1-upd-1", title="Old")
        r = await client.put(
            "/api/v1/admin/challenges/v1-upd-1",
            headers=auth_headers(admin),
            json={"title": "New", "points": 250},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["title"] == "New"
        assert body["points"] == 250

    async def test_rename_slug(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        await challenge_factory(slug="v1-rename-from")
        r = await client.put(
            "/api/v1/admin/challenges/v1-rename-from",
            headers=auth_headers(admin),
            json={"slug": "v1-rename-to"},
        )
        assert r.status_code == 200
        assert r.json()["slug"] == "v1-rename-to"

    async def test_rejects_flag_change_after_solves(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import Solve, UserRole
        from datetime import datetime, timezone

        admin = await user_factory(role=UserRole.admin)
        solver = await user_factory()
        chal = await challenge_factory(slug="v1-flag-locked")
        db_session.add(
            Solve(
                user_id=solver.id,
                challenge_id=chal.id,
                points_awarded=100,
                is_first_blood=True,
                solved_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        r = await client.put(
            "/api/v1/admin/challenges/v1-flag-locked",
            headers=auth_headers(admin),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Challenge release
# ---------------------------------------------------------------------------
class TestReleaseChallengeV1:
    async def test_marks_released_and_emits_audit(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import AuditLedger, UserRole

        admin = await user_factory(role=UserRole.admin)
        await challenge_factory(slug="v1-rel", is_released=False)

        before = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "challenge.released"
                )
            )
        ).scalars().all()

        r = await client.post(
            "/api/v1/admin/challenges/v1-rel/release",
            headers=auth_headers(admin),
        )
        assert r.status_code == 200, r.text
        assert r.json()["is_released"] is True

        after = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "challenge.released"
                )
            )
        ).scalars().all()
        assert len(after) == len(before) + 1

    async def test_404_unknown_slug(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/admin/challenges/missing/release",
            headers=auth_headers(admin),
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Challenge soft-delete
# ---------------------------------------------------------------------------
class TestDeleteChallengeV1:
    async def test_soft_deletes(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import Challenge, UserRole

        admin = await user_factory(role=UserRole.admin)
        await challenge_factory(slug="v1-del")
        r = await client.delete(
            "/api/v1/admin/challenges/v1-del",
            headers=auth_headers(admin),
        )
        assert r.status_code == 200
        assert r.json()["is_active"] is False

        chal = (
            await db_session.execute(
                select(Challenge).where(Challenge.slug == "v1-del")
            )
        ).scalars().first()
        assert chal is not None
        assert chal.is_active is False


# ---------------------------------------------------------------------------
# User update
# ---------------------------------------------------------------------------
class TestUpdateUserV1:
    async def test_promote_to_admin(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import User, UserRole

        admin = await user_factory(role=UserRole.admin)
        target = await user_factory(role=UserRole.operator)

        r = await client.put(
            f"/api/v1/admin/users/{target.id}",
            headers=auth_headers(admin),
            json={"role": "admin"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == _USER_FIELDS
        assert body["role"] == "admin"

        fresh = (
            await db_session.execute(
                select(User).where(User.id == target.id)
            )
        ).scalars().first()
        assert fresh.role == UserRole.admin

    async def test_404_unknown_user(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        r = await client.put(
            "/api/v1/admin/users/9999999",
            headers=auth_headers(admin),
            json={"role": "admin"},
        )
        assert r.status_code == 404

    async def test_rejects_unknown_role(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        target = await user_factory()
        r = await client.put(
            f"/api/v1/admin/users/{target.id}",
            headers=auth_headers(admin),
            json={"role": "superadmin"},
        )
        assert r.status_code == 422

    async def test_requires_admin(
        self, client, user_factory, auth_headers
    ):
        operator = await user_factory()
        target = await user_factory()
        r = await client.put(
            f"/api/v1/admin/users/{target.id}",
            headers=auth_headers(operator),
            json={"role": "admin"},
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Multi-flag flags
# ---------------------------------------------------------------------------
class TestAddChallengeFlagV1:
    async def test_appends_flag(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        from app.models import ChallengeFlag, UserRole

        admin = await user_factory(role=UserRole.admin)
        chal = await challenge_factory(slug="v1-flag-add")

        r = await client.post(
            f"/api/v1/admin/challenges/{chal.slug}/flags",
            headers=auth_headers(admin),
            json={
                "flag_id": "primary",
                "flag_type": "exact",
                "points": 50,
                "label": "Primary",
                "value": "CTF{REDACTED}",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert set(body.keys()) == {"id", "flag_id", "flag_type", "points", "label"}
        assert body["flag_id"] == "primary"

        rows = (
            await db_session.execute(
                select(ChallengeFlag).where(
                    ChallengeFlag.challenge_id == chal.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1

    async def test_rejects_duplicate_flag_id(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        await challenge_factory(slug="v1-flag-dup")

        payload = {
            "flag_id": "dup",
            "flag_type": "exact",
            "points": 25,
            "value": "CTF{REDACTED}",
        }
        await client.post(
            "/api/v1/admin/challenges/v1-flag-dup/flags",
            headers=auth_headers(admin),
            json=payload,
        )
        r = await client.post(
            "/api/v1/admin/challenges/v1-flag-dup/flags",
            headers=auth_headers(admin),
            json=payload,
        )
        assert r.status_code == 409

    async def test_404_unknown_challenge(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        r = await client.post(
            "/api/v1/admin/challenges/no-such/flags",
            headers=auth_headers(admin),
            json={"flag_id": "x", "flag_type": "exact", "points": 1, "value": "y"},
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
class TestSeedV1:
    async def test_returns_400_when_dir_missing(
        self, client, user_factory, auth_headers, monkeypatch, tmp_path
    ):
        from app.models import UserRole
        from app.routers.v1 import admin as admin_module
        from pathlib import Path

        admin = await user_factory(role=UserRole.admin)
        # Point Path("/challenges") replacement at a known-missing dir.
        missing = tmp_path / "absent"
        original_path = admin_module.Path

        class _PatchedPath(Path):
            _flavour = type(original_path("."))._flavour

            def __new__(cls, *args, **kwargs):  # type: ignore[override]
                if args == ("/challenges",):
                    return original_path(missing)
                return original_path(*args, **kwargs)

        monkeypatch.setattr(admin_module, "Path", _PatchedPath)

        r = await client.post(
            "/api/v1/admin/seed", headers=auth_headers(admin)
        )
        assert r.status_code == 400

    async def test_seeds_from_directory(
        self, client, user_factory, auth_headers, tmp_path, monkeypatch
    ):
        import json
        from app.models import UserRole
        from app.routers.v1 import admin as admin_module
        from pathlib import Path

        admin = await user_factory(role=UserRole.admin)

        seed_dir = tmp_path / "challenges"
        seed_dir.mkdir()
        (seed_dir / "demo").mkdir()
        (seed_dir / "demo" / "challenge.json").write_text(
            json.dumps(
                {
                    "slug": "v1-seed-demo",
                    "title": "Seeded",
                    "description": "from /api/v1/admin/seed",
                    "category": "web",
                    "team": "red",
                    "difficulty": 1,
                    "points": 50,
                    "flag": "CTF{REDACTED}",
                    "docker_image": "alpine:3.19",
                    "docker_port": 8080,
                }
            )
        )

        original_path = admin_module.Path

        class _PatchedPath(Path):
            _flavour = type(original_path("."))._flavour

            def __new__(cls, *args, **kwargs):  # type: ignore[override]
                if args == ("/challenges",):
                    return original_path(seed_dir)
                return original_path(*args, **kwargs)

        monkeypatch.setattr(admin_module, "Path", _PatchedPath)

        r = await client.post(
            "/api/v1/admin/seed", headers=auth_headers(admin)
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"created", "skipped"}
        assert body["created"] == 1
        assert body["skipped"] == 0

        # Re-running should skip the existing slug.
        r2 = await client.post(
            "/api/v1/admin/seed", headers=auth_headers(admin)
        )
        assert r2.status_code == 200
        assert r2.json()["skipped"] == 1
