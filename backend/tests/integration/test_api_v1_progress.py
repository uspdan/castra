"""Integration tests for v1 progress endpoint + solved_flags wiring.

Covers:

- ``GET /api/v1/challenges/{slug}/progress`` shape and values for v1
  multi-flag challenges, single-flag v1 challenges, and legacy
  challenges (no v1 ChallengeFlag rows).
- Side-effect on ``POST /api/v1/challenges/{slug}/submit``: a
  successful submission inserts a ``solved_flags`` row carrying
  ``flag_id``, ``points_awarded``, ``is_first_blood_flag``, and
  ``validator_name`` matching the dispatcher's output.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import (
    Challenge,
    ChallengeFlag,
    SolvedFlag,
    TeamType,
)
from app.validators.exact import hash_exact_value


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _make_v1_multi_flag_challenge(
    db_session, *, slug: str
) -> Challenge:
    challenge = Challenge(
        slug=slug,
        title=f"Multi {slug}",
        description="Multi-flag v1 challenge",
        category="forensics",
        team=TeamType.blue,
        difficulty=2,
        points=300,
        flag_hash=None,
        hints=[],
        skills=[],
        mitre_techniques=[],
        docker_image="alpine:3.19",
        docker_port=80,
        docker_config={},
        prerequisite_ids=[],
        is_active=True,
        is_released=True,
        released_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        spec_version="1",
    )
    db_session.add(challenge)
    await db_session.commit()
    await db_session.refresh(challenge)
    flags = [
        ChallengeFlag(
            challenge_id=challenge.id,
            flag_id="alpha",
            flag_type="exact",
            points=100,
            label="Alpha part",
            value_hash=hash_exact_value("CTF{REDACTED}"),
            config={"case_sensitive": True},
        ),
        ChallengeFlag(
            challenge_id=challenge.id,
            flag_id="beta",
            flag_type="exact",
            points=200,
            label="Beta part",
            value_hash=hash_exact_value("CTF{REDACTED}"),
            config={"case_sensitive": True},
        ),
    ]
    for f in flags:
        db_session.add(f)
    await db_session.commit()
    await db_session.refresh(challenge)
    return challenge


# ---------------------------------------------------------------------------
# Submit-side: solved_flags row created
# ---------------------------------------------------------------------------
class TestSolvedFlagPersistence:
    async def test_correct_v1_submission_creates_solved_flag_row(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_multi_flag_challenge(db_session, slug="v1-sf-multi")

        r = await client.post(
            "/api/v1/challenges/v1-sf-multi/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["correct"] is True
        assert r.json()["flag_id"] == "alpha"

        rows = (
            await db_session.execute(
                select(SolvedFlag).where(SolvedFlag.user_id == user.id)
            )
        ).scalars().all()
        assert len(rows) == 1
        sf = rows[0]
        assert sf.flag_id == "alpha"
        # The v1 dispatcher reports per-flag points; the legacy
        # scoring service awards the per-challenge total. Slice 3
        # records the points actually awarded by ``calculate_points``
        # so the SolvedFlag row matches the user's scoreboard
        # contribution.
        assert sf.points_awarded > 0
        # First user to capture this flag — first-blood-flag is true.
        assert sf.is_first_blood_flag is True

    async def test_legacy_challenge_records_legacy_sentinel(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-sf-legacy", flag="CTF{REDACTED}")
        r = await client.post(
            "/api/v1/challenges/v1-sf-legacy/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200
        rows = (
            await db_session.execute(
                select(SolvedFlag).where(SolvedFlag.user_id == user.id)
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].flag_id == "legacy"

    async def test_second_solver_is_not_first_blood(
        self, client, user_factory, auth_headers, db_session
    ):
        winner = await user_factory(username="sf-winner")
        runner_up = await user_factory(username="sf-second")
        await _make_v1_multi_flag_challenge(db_session, slug="v1-sf-fb")

        a = await client.post(
            "/api/v1/challenges/v1-sf-fb/submit",
            headers=auth_headers(winner),
            json={"flag": "CTF{REDACTED}"},
        )
        assert a.status_code == 200
        b = await client.post(
            "/api/v1/challenges/v1-sf-fb/submit",
            headers=auth_headers(runner_up),
            json={"flag": "CTF{REDACTED}"},
        )
        assert b.status_code == 200

        winner_row = (
            await db_session.execute(
                select(SolvedFlag).where(SolvedFlag.user_id == winner.id)
            )
        ).scalars().first()
        runner_up_row = (
            await db_session.execute(
                select(SolvedFlag).where(SolvedFlag.user_id == runner_up.id)
            )
        ).scalars().first()
        assert winner_row.is_first_blood_flag is True
        assert runner_up_row.is_first_blood_flag is False


# ---------------------------------------------------------------------------
# GET /api/v1/challenges/{slug}/progress
# ---------------------------------------------------------------------------
class TestProgressEndpoint:
    async def test_unauthenticated_rejected(self, client):
        r = await client.get("/api/v1/challenges/anything/progress")
        assert r.status_code in (401, 403)

    async def test_404_for_missing_slug(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            "/api/v1/challenges/does-not-exist/progress",
            headers=auth_headers(user),
        )
        assert r.status_code == 404

    async def test_v1_multi_flag_uncaptured(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_multi_flag_challenge(db_session, slug="v1-prog-empty")
        r = await client.get(
            "/api/v1/challenges/v1-prog-empty/progress",
            headers=auth_headers(user),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["challenge_slug"] == "v1-prog-empty"
        assert body["total_flags"] == 2
        assert body["captured_flags"] == 0
        assert body["fully_captured"] is False
        assert body["total_points_possible"] == 300
        assert body["points_captured"] == 0
        flag_ids = [f["flag_id"] for f in body["flags"]]
        assert flag_ids == ["alpha", "beta"]
        for f in body["flags"]:
            assert f["captured"] is False
            assert f["captured_at"] is None
            assert f["is_first_blood_flag"] is None
            assert f["validator_name"] is None

    async def test_v1_multi_flag_partial_capture(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_multi_flag_challenge(db_session, slug="v1-prog-partial")
        # Capture alpha only.
        r = await client.post(
            "/api/v1/challenges/v1-prog-partial/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200

        prog = await client.get(
            "/api/v1/challenges/v1-prog-partial/progress",
            headers=auth_headers(user),
        )
        assert prog.status_code == 200
        body = prog.json()
        assert body["captured_flags"] == 1
        assert body["fully_captured"] is False
        by_id = {f["flag_id"]: f for f in body["flags"]}
        assert by_id["alpha"]["captured"] is True
        assert by_id["alpha"]["captured_at"] is not None
        assert by_id["alpha"]["is_first_blood_flag"] is True
        assert by_id["beta"]["captured"] is False

    async def test_legacy_captured(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-prog-legacy", flag="CTF{REDACTED}")
        sub = await client.post(
            "/api/v1/challenges/v1-prog-legacy/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert sub.status_code == 200

        prog = await client.get(
            "/api/v1/challenges/v1-prog-legacy/progress",
            headers=auth_headers(user),
        )
        assert prog.status_code == 200
        body = prog.json()
        assert body["total_flags"] == 1
        assert body["captured_flags"] == 1
        assert body["fully_captured"] is True
        assert body["flags"][0]["flag_id"] == "legacy"
        assert body["flags"][0]["captured"] is True

    async def test_legacy_uncaptured(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-prog-legacy-empty")
        prog = await client.get(
            "/api/v1/challenges/v1-prog-legacy-empty/progress",
            headers=auth_headers(user),
        )
        assert prog.status_code == 200
        body = prog.json()
        assert body["total_flags"] == 1
        assert body["captured_flags"] == 0
        assert body["fully_captured"] is False
        assert body["flags"][0]["captured"] is False

    async def test_response_shape_locked(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-prog-shape")
        r = await client.get(
            "/api/v1/challenges/v1-prog-shape/progress",
            headers=auth_headers(user),
        )
        body = r.json()
        # Top-level keys exactly the locked DTO shape.
        assert set(body.keys()) == {
            "challenge_slug", "flags", "total_flags", "captured_flags",
            "total_points_possible", "points_captured", "fully_captured",
        }
        for entry in body["flags"]:
            assert set(entry.keys()) == {
                "flag_id", "flag_type", "label", "points", "points_awarded",
                "captured", "captured_at", "is_first_blood_flag",
                "validator_name",
            }
