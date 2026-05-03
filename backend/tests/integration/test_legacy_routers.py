"""Coverage sweep for legacy (pre-v1) routers.

Brings the following modules under the project-wide coverage gate:

- ``app.routers.admin``
- ``app.routers.competitions``
- ``app.routers.health``
- ``app.routers.instances`` (auth/error paths only — launch
  exercises real docker)
- ``app.routers.leaderboard``
- ``app.routers.notifications``
- ``app.routers.stats``
- ``app.routers.writeups``

The v1 surface owns the locked contract for new clients; this suite
guards the legacy endpoints from regressions while the migration is
in flight.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _solve(db_session, user, challenge, points=100, when=None):
    from app.models import Solve

    db_session.add(
        Solve(
            user_id=user.id,
            challenge_id=challenge.id,
            points_awarded=points,
            is_first_blood=False,
            solved_at=when or datetime.now(timezone.utc),
        )
    )
    await db_session.commit()


# ---------------------------------------------------------------------------
# /health and /readyz
# ---------------------------------------------------------------------------
class TestHealth:
    async def test_health_unauthenticated(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body

    async def test_readyz_returns_probe_breakdown(self, client):
        # First call evaluates the cache; second hits the cached path —
        # both should return a structured probe report regardless of
        # actual probe outcomes.
        from app.routers import health as health_module

        # Reset the in-process cache so this test sees a fresh build.
        health_module._cache["report"] = None
        health_module._cache["expires_at"] = 0.0

        r1 = await client.get("/readyz")
        assert r1.status_code in (200, 503)
        body = r1.json()
        assert "ok" in body
        assert "probes" in body
        assert set(body["probes"].keys()) == {"postgres", "redis", "docker"}

        r2 = await client.get("/readyz")
        assert r2.status_code == r1.status_code

    async def test_readyz_postgres_probe_failure(self, client, monkeypatch):
        from app.routers import health as health_module

        async def _boom():
            raise RuntimeError("postgres unreachable")

        monkeypatch.setitem(
            health_module._PROBES, "postgres", _boom
        )
        health_module._cache["report"] = None
        health_module._cache["expires_at"] = 0.0

        r = await client.get("/readyz")
        assert r.status_code == 503
        assert r.json()["probes"]["postgres"]["ok"] is False

    async def test_readyz_probe_timeout(self, client, monkeypatch):
        import asyncio

        from app.routers import health as health_module

        async def _slow():
            await asyncio.sleep(10)

        monkeypatch.setitem(health_module._PROBES, "redis", _slow)
        monkeypatch.setattr(health_module, "_PROBE_TIMEOUT_S", 0.05)
        health_module._cache["report"] = None
        health_module._cache["expires_at"] = 0.0

        r = await client.get("/readyz")
        assert r.status_code == 503
        assert r.json()["probes"]["redis"]["error"] == "timeout"


# ---------------------------------------------------------------------------
# /leaderboard (legacy)
# ---------------------------------------------------------------------------
class TestLegacyLeaderboard:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/leaderboard/")
        assert r.status_code in (401, 403)

    async def test_returns_active_users(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import TeamType

        user = await user_factory(team=TeamType.red, username="lbruser")
        chal = await challenge_factory(slug="lb-legacy-1", points=100)
        await _solve(db_session, user, chal, 100)

        r = await client.get("/leaderboard/", headers=auth_headers(user))
        assert r.status_code == 200
        rows = r.json()
        assert any(row["username"] == "lbruser" for row in rows)
        # Verify rank is assigned.
        assert all("rank" in row for row in rows)

    async def test_team_filter(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import TeamType

        red = await user_factory(team=TeamType.red, username="lbteamred")
        blue = await user_factory(team=TeamType.blue, username="lbteamblue")
        chal = await challenge_factory(slug="lb-team-filter", points=80)
        await _solve(db_session, red, chal, 80)
        await _solve(db_session, blue, chal, 80)

        r = await client.get(
            "/leaderboard/?team=red", headers=auth_headers(red)
        )
        assert r.status_code == 200
        usernames = [row["username"] for row in r.json()]
        assert "lbteamred" in usernames
        assert "lbteamblue" not in usernames


# ---------------------------------------------------------------------------
# /admin
# ---------------------------------------------------------------------------
class TestLegacyAdmin:
    async def test_list_users_requires_admin(
        self, client, user_factory, auth_headers
    ):
        operator = await user_factory()
        r = await client.get(
            "/admin/users", headers=auth_headers(operator)
        )
        assert r.status_code == 403

    async def test_list_users_paginated(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        for i in range(3):
            await user_factory(username=f"adminlist{i}")
        r = await client.get(
            "/admin/users?page=1&per_page=50", headers=auth_headers(admin)
        )
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert body["per_page"] == 50

    async def test_update_user_role(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import User, UserRole

        admin = await user_factory(role=UserRole.admin)
        target = await user_factory(role=UserRole.operator)
        r = await client.put(
            f"/admin/users/{target.id}",
            headers=auth_headers(admin),
            json={"role": "admin"},
        )
        assert r.status_code == 200
        fresh = (
            await db_session.execute(
                select(User).where(User.id == target.id)
            )
        ).scalar_one()
        assert fresh.role == UserRole.admin

    async def test_update_unknown_user_is_404(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        r = await client.put(
            "/admin/users/999999",
            headers=auth_headers(admin),
            json={"role": "admin"},
        )
        assert r.status_code == 404

    async def test_audit_log_returns_paginated(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        # Seed at least one audit row by promoting another user.
        target = await user_factory()
        await client.put(
            f"/admin/users/{target.id}",
            headers=auth_headers(admin),
            json={"role": "admin"},
        )
        # Seed an explicit audit-ledger row by registering via legacy
        # endpoint (which writes auth.register).
        await client.post(
            "/auth/register",
            json={
                "email": "auditseed@test.local",
                "username": "auditseed",
                "password": "GoodPassword1!",
                "team": "red",
            },
        )
        r = await client.get("/admin/audit", headers=auth_headers(admin))
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "total" in body

    async def test_audit_filtered_by_action(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        await client.post(
            "/auth/register",
            json={
                "email": "afilt@test.local",
                "username": "afilt",
                "password": "GoodPassword1!",
                "team": "red",
            },
        )
        r = await client.get(
            "/admin/audit?action=auth.register",
            headers=auth_headers(admin),
        )
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["action"] == "auth.register"

    async def test_system_info(self, client, user_factory, auth_headers):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        r = await client.get("/admin/system", headers=auth_headers(admin))
        assert r.status_code == 200
        body = r.json()
        assert "db_tables" in body
        assert "version" in body

    async def test_seed_400_when_dir_missing(
        self, client, user_factory, auth_headers, monkeypatch, tmp_path
    ):
        from app.models import UserRole
        from app.routers import admin as admin_module
        from pathlib import Path

        admin = await user_factory(role=UserRole.admin)
        missing = tmp_path / "absent"
        original_path = admin_module.Path

        class _PatchedPath(Path):
            _flavour = type(original_path("."))._flavour

            def __new__(cls, *args, **kwargs):
                if args == ("/challenges",):
                    return original_path(missing)
                return original_path(*args, **kwargs)

        monkeypatch.setattr(admin_module, "Path", _PatchedPath)
        r = await client.post("/admin/seed", headers=auth_headers(admin))
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# /competitions
# ---------------------------------------------------------------------------
class TestCompetitions:
    async def test_create_requires_admin(
        self, client, user_factory, auth_headers
    ):
        operator = await user_factory()
        starts = datetime.now(timezone.utc)
        r = await client.post(
            "/competitions/",
            headers=auth_headers(operator),
            json={
                "title": "Forbidden",
                "starts_at": starts.isoformat(),
                "ends_at": (starts + timedelta(hours=1)).isoformat(),
            },
        )
        assert r.status_code == 403

    async def test_create_and_list(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        starts = datetime.now(timezone.utc)
        ends = starts + timedelta(hours=2)
        r = await client.post(
            "/competitions/",
            headers=auth_headers(admin),
            json={
                "title": "Spring CTF",
                "description": "test",
                "starts_at": starts.isoformat(),
                "ends_at": ends.isoformat(),
                "challenge_ids": [],
                "is_active": True,
                "hints_disabled": True,
                "format": "jeopardy",
            },
        )
        assert r.status_code == 200, r.text
        created = r.json()
        comp_id = created["id"]

        r2 = await client.get(
            "/competitions/", headers=auth_headers(admin)
        )
        assert r2.status_code == 200
        ids = [c["id"] for c in r2.json()]
        assert comp_id in ids

    async def test_get_competition_404(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            "/competitions/9999999", headers=auth_headers(user)
        )
        assert r.status_code == 404

    async def test_get_live_competition_includes_scoreboard(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import Competition, UserRole

        admin = await user_factory(role=UserRole.admin)
        chal = await challenge_factory(slug="comp-target")
        starts = datetime.now(timezone.utc) - timedelta(hours=1)
        ends = datetime.now(timezone.utc) + timedelta(hours=1)
        comp = Competition(
            title="Live",
            starts_at=starts,
            ends_at=ends,
            is_active=True,
            challenge_ids=[chal.id],
            hints_disabled=True,
            format="jeopardy",
            created_by=admin.id,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(comp)
        await db_session.commit()
        await db_session.refresh(comp)

        await _solve(db_session, admin, chal, 100)

        r = await client.get(
            f"/competitions/{comp.id}", headers=auth_headers(admin)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["is_live"] is True
        assert "scoreboard" in body

    async def test_competition_scoreboard(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import Competition, UserRole

        admin = await user_factory(role=UserRole.admin)
        chal = await challenge_factory(slug="comp-sb")
        starts = datetime.now(timezone.utc) - timedelta(hours=1)
        ends = datetime.now(timezone.utc) + timedelta(hours=1)
        comp = Competition(
            title="Scoreboard",
            starts_at=starts,
            ends_at=ends,
            is_active=True,
            challenge_ids=[chal.id],
            hints_disabled=True,
            format="jeopardy",
            created_by=admin.id,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(comp)
        await db_session.commit()
        await db_session.refresh(comp)
        await _solve(db_session, admin, chal, 100)

        r = await client.get(
            f"/competitions/{comp.id}/scoreboard",
            headers=auth_headers(admin),
        )
        assert r.status_code == 200
        rows = r.json()
        assert any(row["user_id"] == admin.id for row in rows)

    async def test_activate_competition_requires_admin(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import Competition, UserRole

        admin = await user_factory(role=UserRole.admin)
        comp = Competition(
            title="To Activate",
            starts_at=datetime.now(timezone.utc),
            ends_at=datetime.now(timezone.utc) + timedelta(hours=1),
            is_active=False,
            challenge_ids=[],
            hints_disabled=True,
            format="jeopardy",
            created_by=admin.id,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(comp)
        await db_session.commit()
        await db_session.refresh(comp)

        operator = await user_factory()
        r_block = await client.post(
            f"/competitions/{comp.id}/activate",
            headers=auth_headers(operator),
        )
        assert r_block.status_code == 403

        r_ok = await client.post(
            f"/competitions/{comp.id}/activate",
            headers=auth_headers(admin),
        )
        assert r_ok.status_code == 200


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------
class TestStats:
    async def test_overview_unauthenticated_rejected(self, client):
        r = await client.get("/stats/overview")
        assert r.status_code in (401, 403)

    async def test_overview(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="stats-chal-1")
        r = await client.get(
            "/stats/overview", headers=auth_headers(user)
        )
        assert r.status_code == 200
        body = r.json()
        assert "total_challenges" in body
        assert "total_solves" in body
        assert "active_users_this_week" in body

    async def test_mitre(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="stats-mitre-1")
        r = await client.get("/stats/mitre", headers=auth_headers(user))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_activity(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        user = await user_factory()
        chal = await challenge_factory(slug="stats-activity")
        await _solve(db_session, user, chal, 50)
        r = await client.get(
            "/stats/activity", headers=auth_headers(user)
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_user_stats_self(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="stats-user-self")
        r = await client.get(
            f"/stats/user/{user.id}", headers=auth_headers(user)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == user.id
        assert "skill_percentages" in body

    async def test_user_stats_forbidden_for_other(
        self, client, user_factory, auth_headers
    ):
        viewer = await user_factory()
        target = await user_factory()
        r = await client.get(
            f"/stats/user/{target.id}", headers=auth_headers(viewer)
        )
        assert r.status_code == 403

    async def test_user_stats_admin_can_view_other(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        target = await user_factory()
        r = await client.get(
            f"/stats/user/{target.id}", headers=auth_headers(admin)
        )
        assert r.status_code == 200

    async def test_user_stats_404_unknown(
        self, client, user_factory, auth_headers
    ):
        from app.models import UserRole

        admin = await user_factory(role=UserRole.admin)
        r = await client.get(
            "/stats/user/9999999", headers=auth_headers(admin)
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# /writeups
# ---------------------------------------------------------------------------
class TestWriteups:
    async def test_create_requires_solve(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="wu-unsolved")
        r = await client.post(
            "/writeups/wu-unsolved",
            headers=auth_headers(user),
            json={"content": "<p>my walkthrough</p>"},
        )
        assert r.status_code == 403

    async def test_create_404_when_challenge_missing(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            "/writeups/no-such-thing",
            headers=auth_headers(user),
            json={"content": "anything"},
        )
        assert r.status_code == 404

    async def test_create_after_solve(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        user = await user_factory()
        chal = await challenge_factory(slug="wu-solved")
        await _solve(db_session, user, chal, 100)
        r = await client.post(
            "/writeups/wu-solved",
            headers=auth_headers(user),
            json={
                "content": "<p>great <script>alert(1)</script>walkthrough</p>",
                "title": "How I cracked it",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["title"] == "How I cracked it"

    async def test_list_requires_solve(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="wu-list-locked")
        r = await client.get(
            "/writeups/wu-list-locked", headers=auth_headers(user)
        )
        assert r.status_code == 403

    async def test_list_visible_after_solve(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import Writeup

        user = await user_factory()
        chal = await challenge_factory(slug="wu-list-ok")
        await _solve(db_session, user, chal, 100)
        # Pre-place an approved writeup.
        wu = Writeup(
            user_id=user.id,
            challenge_id=chal.id,
            title="Approved",
            content="content",
            is_approved=True,
            rating=0.0,
            rating_count=0,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(wu)
        await db_session.commit()

        r = await client.get(
            "/writeups/wu-list-ok", headers=auth_headers(user)
        )
        assert r.status_code == 200
        body = r.json()
        assert any(item["title"] == "Approved" for item in body["items"])

    async def test_rate_writeup(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import Writeup

        user = await user_factory()
        chal = await challenge_factory(slug="wu-rate")
        wu = Writeup(
            user_id=user.id,
            challenge_id=chal.id,
            title="Ratable",
            content="content",
            is_approved=True,
            rating=0.0,
            rating_count=0,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(wu)
        await db_session.commit()
        await db_session.refresh(wu)

        r = await client.post(
            f"/writeups/{wu.id}/rate",
            headers=auth_headers(user),
            json={"rating": 5},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["rating"] == 5.0
        assert body["rating_count"] == 1

    async def test_rate_404(self, client, user_factory, auth_headers):
        user = await user_factory()
        r = await client.post(
            "/writeups/9999999/rate",
            headers=auth_headers(user),
            json={"rating": 4},
        )
        assert r.status_code == 404

    async def test_approve_requires_admin(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        from app.models import UserRole, Writeup

        admin = await user_factory(role=UserRole.admin)
        author = await user_factory()
        chal = await challenge_factory(slug="wu-approve")
        wu = Writeup(
            user_id=author.id,
            challenge_id=chal.id,
            title="Pending",
            content="...",
            is_approved=False,
            rating=0.0,
            rating_count=0,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(wu)
        await db_session.commit()
        await db_session.refresh(wu)

        # Operator blocked, admin allowed.
        r_block = await client.put(
            f"/writeups/{wu.id}/approve",
            headers=auth_headers(author),
        )
        assert r_block.status_code == 403

        r_ok = await client.put(
            f"/writeups/{wu.id}/approve",
            headers=auth_headers(admin),
        )
        assert r_ok.status_code == 200


# ---------------------------------------------------------------------------
# /notifications
# ---------------------------------------------------------------------------
class TestNotifications:
    async def test_list_unauthenticated_rejected(self, client):
        r = await client.get("/notifications/")
        assert r.status_code in (401, 403)

    async def test_list_user_and_global(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import Notification

        user = await user_factory()
        db_session.add_all(
            [
                Notification(
                    title="Global",
                    message="hello",
                    notification_type="info",
                    is_global=True,
                    created_at=datetime.now(timezone.utc),
                ),
                Notification(
                    title="ForMe",
                    message="hello",
                    notification_type="info",
                    target_user_id=user.id,
                    is_global=False,
                    created_at=datetime.now(timezone.utc),
                ),
            ]
        )
        await db_session.commit()

        r = await client.get("/notifications/", headers=auth_headers(user))
        assert r.status_code == 200
        titles = [n["title"] for n in r.json()["items"]]
        assert "Global" in titles
        assert "ForMe" in titles

    async def test_unread_count(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import Notification

        user = await user_factory()
        db_session.add(
            Notification(
                title="Unread",
                message="x",
                notification_type="info",
                is_global=True,
                created_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        r = await client.get(
            "/notifications/unread-count", headers=auth_headers(user)
        )
        assert r.status_code == 200
        assert r.json()["unread_count"] >= 1

    async def test_mark_read(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import Notification

        user = await user_factory()
        n = Notification(
            title="ToRead",
            message="x",
            notification_type="info",
            target_user_id=user.id,
            is_global=False,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(n)
        await db_session.commit()
        await db_session.refresh(n)

        r = await client.put(
            f"/notifications/{n.id}/read", headers=auth_headers(user)
        )
        assert r.status_code == 200

        await db_session.refresh(n)
        assert n.is_read is True

    async def test_mark_read_forbidden_for_other_user(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import Notification

        owner = await user_factory()
        intruder = await user_factory()
        n = Notification(
            title="Private",
            message="x",
            notification_type="info",
            target_user_id=owner.id,
            is_global=False,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(n)
        await db_session.commit()
        await db_session.refresh(n)

        r = await client.put(
            f"/notifications/{n.id}/read",
            headers=auth_headers(intruder),
        )
        assert r.status_code == 403

    async def test_mark_read_404(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.put(
            "/notifications/9999999/read", headers=auth_headers(user)
        )
        assert r.status_code == 404

    async def test_mark_all_read(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import Notification

        user = await user_factory()
        db_session.add(
            Notification(
                title="A",
                message="x",
                notification_type="info",
                target_user_id=user.id,
                is_global=False,
                created_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        r = await client.put(
            "/notifications/read-all", headers=auth_headers(user)
        )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# /instances (legacy paths — auth/error only; live launch needs docker)
# ---------------------------------------------------------------------------
class TestLegacyInstances:
    async def test_launch_404_for_unknown_slug(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            "/instances/no-such-slug/launch", headers=auth_headers(user)
        )
        assert r.status_code == 404

    async def test_stop_404_for_unknown_id(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.delete(
            "/instances/9999999", headers=auth_headers(user)
        )
        assert r.status_code == 404

    async def test_stop_forbidden_for_other_user(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        from app.models import ChallengeInstance, InstanceStatus

        owner = await user_factory()
        intruder = await user_factory()
        chal = await challenge_factory(slug="inst-perm")
        instance = ChallengeInstance(
            user_id=owner.id,
            challenge_id=chal.id,
            container_id=None,
            container_name=None,
            status=InstanceStatus.running,
            assigned_port=20_000,
            assigned_ip="0.0.0.0",
            network_name=None,
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            applied_profile="default-strict",
        )
        db_session.add(instance)
        await db_session.commit()
        await db_session.refresh(instance)

        r = await client.delete(
            f"/instances/{instance.id}", headers=auth_headers(intruder)
        )
        assert r.status_code == 403

    async def test_list_only_running(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        from app.models import ChallengeInstance, InstanceStatus

        user = await user_factory()
        chal = await challenge_factory(slug="inst-list")
        for status in (InstanceStatus.running, InstanceStatus.stopped):
            db_session.add(
                ChallengeInstance(
                    user_id=user.id,
                    challenge_id=chal.id,
                    container_id=None,
                    container_name=None,
                    status=status,
                    assigned_port=10_000,
                    assigned_ip="0.0.0.0",
                    network_name=None,
                    started_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                    applied_profile="default-strict",
                )
            )
        await db_session.commit()

        r = await client.get("/instances/", headers=auth_headers(user))
        assert r.status_code == 200
        body = r.json()
        assert all(item["status"] == "running" for item in body["instances"])

    async def test_reset_404_for_unknown_id(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            "/instances/9999999/reset", headers=auth_headers(user)
        )
        assert r.status_code == 404

    async def test_reset_forbidden_for_other_user(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        from app.models import ChallengeInstance, InstanceStatus

        owner = await user_factory()
        intruder = await user_factory()
        chal = await challenge_factory(slug="inst-reset-perm")
        instance = ChallengeInstance(
            user_id=owner.id,
            challenge_id=chal.id,
            container_id=None,
            container_name=None,
            status=InstanceStatus.running,
            assigned_port=20_001,
            assigned_ip="0.0.0.0",
            network_name=None,
            started_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            applied_profile="default-strict",
        )
        db_session.add(instance)
        await db_session.commit()
        await db_session.refresh(instance)

        r = await client.post(
            f"/instances/{instance.id}/reset",
            headers=auth_headers(intruder),
        )
        assert r.status_code == 403
