"""Integration tests for the public API v1 surface.

Covers the five Phase 12 (slice 1) endpoints end-to-end through the
FastAPI test client. Each test asserts:

- 401 / 403 paths reject unauthenticated traffic.
- The response shape matches the locked DTO (ConfigDict
  extra="forbid" guarantees no leakage; we additionally check
  required fields explicitly).
- Internal columns (flag_hash, docker_image, manifest_sha256, etc.)
  are absent.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import Solve, TeamType, UserRole


pytestmark = pytest.mark.integration


_INTERNAL_FIELDS = {
    "id",
    "flag_hash",
    "docker_image",
    "docker_port",
    "docker_config",
    "manifest_sha256",
    "source_path",
    "loaded_at",
    "spec_version",
    "is_active",
    "is_released",
    "pending_review",
}


def _no_internal_fields(payload: dict) -> None:
    leaked = _INTERNAL_FIELDS & payload.keys()
    assert not leaked, f"v1 response leaked internal fields: {leaked}"


# ---------------------------------------------------------------------------
# /api/v1/challenges
# ---------------------------------------------------------------------------
class TestListChallenges:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/api/v1/challenges")
        assert r.status_code in (401, 403)

    async def test_happy_path(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-list-1", title="C1", points=100)
        await challenge_factory(slug="v1-list-2", title="C2", points=200)
        r = await client.get(
            "/api/v1/challenges?per_page=10", headers=auth_headers(user)
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"items", "total", "page", "per_page"}
        assert body["page"] == 1
        assert body["per_page"] == 10
        assert body["total"] >= 2
        slugs = {item["slug"] for item in body["items"]}
        assert {"v1-list-1", "v1-list-2"} <= slugs
        for item in body["items"]:
            _no_internal_fields(item)
            assert set(item.keys()) == {
                "slug", "title", "category", "difficulty", "points",
                "team", "solve_count", "user_solved", "first_blood_user",
                "released_at",
            }

    async def test_pagination(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        for i in range(5):
            await challenge_factory(slug=f"v1-page-{i}", points=10 * (i + 1))
        r = await client.get(
            "/api/v1/challenges?per_page=2&page=2", headers=auth_headers(user)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["page"] == 2
        assert body["per_page"] == 2
        assert len(body["items"]) <= 2

    async def test_team_filter(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-team-red", team=TeamType.red)
        await challenge_factory(slug="v1-team-blue", team=TeamType.blue)
        r = await client.get(
            "/api/v1/challenges?team=red", headers=auth_headers(user)
        )
        assert r.status_code == 200
        slugs = {item["slug"] for item in r.json()["items"]}
        assert "v1-team-red" in slugs
        assert "v1-team-blue" not in slugs


# ---------------------------------------------------------------------------
# /api/v1/challenges/{slug}
# ---------------------------------------------------------------------------
class TestChallengeDetail:
    async def test_404_for_missing_slug(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            "/api/v1/challenges/does-not-exist", headers=auth_headers(user)
        )
        assert r.status_code == 404

    async def test_happy_path(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(
            slug="v1-detail",
            title="Detail Title",
            points=150,
        )
        r = await client.get(
            "/api/v1/challenges/v1-detail", headers=auth_headers(user)
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["slug"] == "v1-detail"
        assert body["title"] == "Detail Title"
        assert body["points"] == 150
        _no_internal_fields(body)
        # Required v1 fields must be present.
        for required in (
            "description", "category", "difficulty", "team", "skills",
            "mitre_techniques", "hints", "solve_count", "user_solved",
            "top_solvers", "prerequisites", "writeup_count", "released_at",
        ):
            assert required in body


# ---------------------------------------------------------------------------
# /api/v1/scoreboard
# ---------------------------------------------------------------------------
class TestScoreboard:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/api/v1/scoreboard")
        assert r.status_code in (401, 403)

    async def test_empty_scoreboard_has_only_caller(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get("/api/v1/scoreboard", headers=auth_headers(user))
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"entries", "team_filter", "generated_at"}
        usernames = {e["username"] for e in body["entries"]}
        assert user.username in usernames
        # Every entry has the locked shape (slice 21 added user_id).
        for entry in body["entries"]:
            assert set(entry.keys()) == {
                "rank", "user_id", "username", "display_name", "team",
                "total_points", "total_solves", "current_streak",
            }
            assert entry["rank"] >= 1
            assert entry["user_id"] >= 1

    async def test_ranking_orders_by_points_desc(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        winner = await user_factory(username="winner")
        loser = await user_factory(username="loser")
        chal = await challenge_factory(slug="v1-board", points=100)
        # Manual solve insertion to set explicit point totals.
        db_session.add(
            Solve(
                user_id=winner.id,
                challenge_id=chal.id,
                points_awarded=500,
                solved_at=datetime.now(timezone.utc),
            )
        )
        db_session.add(
            Solve(
                user_id=loser.id,
                challenge_id=chal.id,
                points_awarded=100,
                solved_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        r = await client.get(
            "/api/v1/scoreboard", headers=auth_headers(winner)
        )
        assert r.status_code == 200
        entries = r.json()["entries"]
        winner_entry = next(e for e in entries if e["username"] == "winner")
        loser_entry = next(e for e in entries if e["username"] == "loser")
        assert winner_entry["rank"] < loser_entry["rank"]
        assert winner_entry["total_points"] == 500
        assert loser_entry["total_points"] == 100

    async def test_team_filter(
        self, client, user_factory, auth_headers
    ):
        red = await user_factory(username="red-1", team=TeamType.red)
        await user_factory(username="blue-1", team=TeamType.blue)
        r = await client.get(
            "/api/v1/scoreboard?team=red", headers=auth_headers(red)
        )
        assert r.status_code == 200
        teams = {e["team"] for e in r.json()["entries"]}
        assert teams.issubset({"red", None})

    async def test_invalid_team_rejected(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            "/api/v1/scoreboard?team=orange", headers=auth_headers(user)
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# /api/v1/attack-coverage
# ---------------------------------------------------------------------------
class TestAttackCoverage:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/api/v1/attack-coverage")
        assert r.status_code in (401, 403)

    async def test_aggregates_techniques_across_challenges(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        user = await user_factory()
        from app.models import Challenge
        # challenge_factory doesn't expose mitre_techniques; create
        # directly.
        c1 = Challenge(
            slug="v1-att-1", title="A", description="x",
            category="web", team=TeamType.red, difficulty=2, points=100,
            flag_hash="0" * 64, hints=[], skills=[],
            mitre_techniques=["T1059", "T1486"],
            docker_image="alpine:3.19", docker_port=80, docker_config={},
            prerequisite_ids=[], is_active=True, is_released=True,
            released_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        c2 = Challenge(
            slug="v1-att-2", title="B", description="y",
            category="web", team=TeamType.red, difficulty=2, points=100,
            flag_hash="0" * 64, hints=[], skills=[],
            mitre_techniques=["T1059"],
            docker_image="alpine:3.19", docker_port=80, docker_config={},
            prerequisite_ids=[], is_active=True, is_released=True,
            released_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db_session.add_all([c1, c2])
        await db_session.commit()
        await db_session.refresh(c1)

        # Mark one solve so solved_by_viewer reports >0 for T1059+T1486.
        db_session.add(
            Solve(
                user_id=user.id, challenge_id=c1.id, points_awarded=100,
                solved_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        r = await client.get(
            "/api/v1/attack-coverage", headers=auth_headers(user)
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"entries", "total_techniques", "total_challenges"}
        by_tech = {e["technique_id"]: e for e in body["entries"]}
        assert by_tech["T1059"]["challenge_count"] == 2
        assert by_tech["T1059"]["solved_by_viewer"] == 1
        assert by_tech["T1486"]["challenge_count"] == 1
        assert by_tech["T1486"]["solved_by_viewer"] == 1


# ---------------------------------------------------------------------------
# /api/v1/me
# ---------------------------------------------------------------------------
class TestMe:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/api/v1/me")
        assert r.status_code in (401, 403)

    async def test_unranked_user(self, client, user_factory, auth_headers):
        user = await user_factory()
        r = await client.get("/api/v1/me", headers=auth_headers(user))
        assert r.status_code == 200, r.text
        body = r.json()
        # Slice 21 added id so the leaderboard highlight cross-page
        # match (MeResponse.id ↔ ScoreboardEntry.user_id) works.
        assert set(body.keys()) == {
            "id", "username", "display_name", "email", "role", "team",
            "is_active", "created_at", "total_points", "total_solves",
            "current_streak", "rank",
        }
        assert body["id"] == user.id
        assert body["username"] == user.username
        assert body["total_points"] == 0
        assert body["total_solves"] == 0
        assert body["rank"] is None

    async def test_ranked_user(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        user = await user_factory()
        chal = await challenge_factory(slug="v1-me-rank", points=100)
        db_session.add(
            Solve(
                user_id=user.id, challenge_id=chal.id, points_awarded=250,
                solved_at=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        r = await client.get("/api/v1/me", headers=auth_headers(user))
        assert r.status_code == 200
        body = r.json()
        assert body["total_points"] == 250
        assert body["total_solves"] == 1
        assert body["rank"] is not None
        assert body["rank"] >= 1


# ---------------------------------------------------------------------------
# OpenAPI contract snapshot
# ---------------------------------------------------------------------------
async def test_openapi_v1_paths_present(client):
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = spec["paths"]
    expected = {
        "/api/v1/challenges",
        "/api/v1/challenges/{slug}",
        "/api/v1/scoreboard",
        "/api/v1/attack-coverage",
        "/api/v1/me",
    }
    assert expected.issubset(paths.keys())
    # Every v1 path declares a 200 response with a $ref schema.
    for path in expected:
        for method, op in paths[path].items():
            if method not in ("get", "post"):
                continue
            assert "200" in op["responses"], f"{path}: missing 200"
            content = op["responses"]["200"]["content"]
            ref = content["application/json"]["schema"].get("$ref")
            assert ref, f"{path}: 200 response is not a $ref"
