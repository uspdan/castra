"""Integration tests for ``/api/v1/leaderboard/{teams,weekly}``.

Locks the response shape (no extra fields), happy-path math, team
filter behaviour, and that auth is enforced.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


_TEAM_ENTRY_FIELDS = {
    "team",
    "total_points",
    "total_solves",
    "member_count",
    "avg_points_per_member",
}

_TEAM_RESP_FIELDS = {"teams", "generated_at"}

_WEEKLY_ENTRY_FIELDS = {
    "rank",
    "user_id",
    "username",
    "display_name",
    "team",
    "total_points",
    "total_solves",
    "current_streak",
}

_WEEKLY_RESP_FIELDS = {
    "entries",
    "team_filter",
    "week_start",
    "generated_at",
}


async def _solve(db_session, user, challenge, points, when=None):
    from app.models import Solve

    s = Solve(
        user_id=user.id,
        challenge_id=challenge.id,
        points_awarded=points,
        is_first_blood=False,
        solved_at=when or datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()


# ---------------------------------------------------------------------------
# /api/v1/leaderboard/teams
# ---------------------------------------------------------------------------
class TestTeamLeaderboardV1:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/api/v1/leaderboard/teams")
        assert r.status_code in (401, 403)

    async def test_returns_locked_shape(
        self, client, user_factory, auth_headers
    ):
        from app.models import TeamType

        user = await user_factory(team=TeamType.red)
        r = await client.get(
            "/api/v1/leaderboard/teams", headers=auth_headers(user)
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == _TEAM_RESP_FIELDS
        assert isinstance(body["teams"], list)
        assert {t["team"] for t in body["teams"]} == {"red", "blue"}
        for t in body["teams"]:
            assert set(t.keys()) == _TEAM_ENTRY_FIELDS

    async def test_aggregates_points_per_team(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import TeamType

        red = await user_factory(team=TeamType.red, username="redder")
        blue = await user_factory(team=TeamType.blue, username="bluer")
        chal = await challenge_factory(slug="lb-team", points=150)
        await _solve(db_session, red, chal, 150)
        await _solve(db_session, blue, chal, 50)

        r = await client.get(
            "/api/v1/leaderboard/teams", headers=auth_headers(red)
        )
        body = r.json()
        teams = {t["team"]: t for t in body["teams"]}
        assert teams["red"]["total_points"] >= 150
        assert teams["red"]["total_solves"] >= 1
        assert teams["red"]["member_count"] >= 1
        assert teams["blue"]["total_points"] >= 50


# ---------------------------------------------------------------------------
# /api/v1/leaderboard/weekly
# ---------------------------------------------------------------------------
class TestWeeklyLeaderboardV1:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/api/v1/leaderboard/weekly")
        assert r.status_code in (401, 403)

    async def test_returns_locked_shape(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            "/api/v1/leaderboard/weekly", headers=auth_headers(user)
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == _WEEKLY_RESP_FIELDS
        assert isinstance(body["entries"], list)

    async def test_excludes_users_without_recent_solves(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        bystander = await user_factory(username="zzzzbystander")
        active = await user_factory(username="aaaactive")
        chal = await challenge_factory(slug="lb-weekly", points=80)
        await _solve(db_session, active, chal, 80)

        r = await client.get(
            "/api/v1/leaderboard/weekly", headers=auth_headers(active)
        )
        body = r.json()
        usernames = [e["username"] for e in body["entries"]]
        assert "aaaactive" in usernames
        assert "zzzzbystander" not in usernames

    async def test_excludes_solves_before_week_start(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        user = await user_factory(username="oldsolveuser")
        chal = await challenge_factory(slug="lb-weekly-old", points=200)
        # Pre-place a solve in a previous ISO week (10 days ago).
        await _solve(
            db_session,
            user,
            chal,
            200,
            when=datetime.now(timezone.utc) - timedelta(days=10),
        )
        r = await client.get(
            "/api/v1/leaderboard/weekly", headers=auth_headers(user)
        )
        body = r.json()
        # The user has no solves THIS week → excluded.
        assert all(e["username"] != "oldsolveuser" for e in body["entries"])

    async def test_team_filter(
        self,
        client,
        user_factory,
        auth_headers,
        challenge_factory,
        db_session,
    ):
        from app.models import TeamType

        red = await user_factory(team=TeamType.red, username="r1")
        blue = await user_factory(team=TeamType.blue, username="b1")
        chal = await challenge_factory(slug="lb-weekly-team", points=10)
        await _solve(db_session, red, chal, 10)
        await _solve(db_session, blue, chal, 10)

        r = await client.get(
            "/api/v1/leaderboard/weekly?team=red",
            headers=auth_headers(red),
        )
        body = r.json()
        assert body["team_filter"] == "red"
        assert all(e["team"] == "red" for e in body["entries"])

    async def test_invalid_team_filter_rejected(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            "/api/v1/leaderboard/weekly?team=purple",
            headers=auth_headers(user),
        )
        assert r.status_code == 422
