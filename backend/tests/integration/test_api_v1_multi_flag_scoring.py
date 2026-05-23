"""Integration tests for true per-flag scoring (Phase 12 slice 4).

Multi-flag v1 challenges award per-flag points incrementally; the
``Solve`` row is created only when every declared flag has been
captured. Single-flag v1 + legacy challenges keep the historical
one-shot behaviour.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import (
    AuditLedger,
    Challenge,
    ChallengeFlag,
    Solve,
    SolvedFlag,
    TeamType,
)
from app.validators.exact import hash_exact_value


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _make_multi_flag(
    db_session, *, slug: str, parts: list[tuple[str, str, int]]
) -> Challenge:
    """Build a challenge with a list of (flag_id, value, points) tuples."""

    challenge = Challenge(
        slug=slug,
        title=f"Multi {slug}",
        description="Multi-flag v1 challenge",
        category="forensics",
        team=TeamType.blue,
        difficulty=2,
        points=sum(p for _, _, p in parts),
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
    for flag_id, value, points in parts:
        db_session.add(
            ChallengeFlag(
                challenge_id=challenge.id,
                flag_id=flag_id,
                flag_type="exact",
                points=points,
                label=flag_id.title(),
                value_hash=hash_exact_value(value),
                config={"case_sensitive": True},
            )
        )
    await db_session.commit()
    await db_session.refresh(challenge)
    return challenge


# ---------------------------------------------------------------------------
# Multi-flag incremental capture
# ---------------------------------------------------------------------------
class TestMultiFlagIncrementalCapture:
    async def test_first_flag_captured_no_solve_yet(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_multi_flag(
            db_session,
            slug="v1-mf-incr",
            parts=[("alpha", "value-alpha", 100), ("beta", "value-beta", 200)],
        )
        r = await client.post(
            "/api/v1/challenges/v1-mf-incr/submit",
            headers=auth_headers(user),
            json={"flag": "value-alpha"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["correct"] is True
        assert body["flag_id"] == "alpha"
        # Per-flag points (with first-blood-flag bonus). Alpha base
        # is 100, * 1.25 = 125 (first-blood-flag).
        assert body["points_awarded"] == 125
        # No Solve row yet — beta still uncaptured.
        solve = (
            await db_session.execute(
                select(Solve).where(Solve.user_id == user.id)
            )
        ).scalars().first()
        assert solve is None
        # SolvedFlag row exists for alpha.
        flags = (
            await db_session.execute(
                select(SolvedFlag).where(SolvedFlag.user_id == user.id)
            )
        ).scalars().all()
        assert [f.flag_id for f in flags] == ["alpha"]

    async def test_full_capture_creates_solve_with_summed_points(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_multi_flag(
            db_session,
            slug="v1-mf-full",
            parts=[("alpha", "value-alpha", 100), ("beta", "value-beta", 200)],
        )
        first = await client.post(
            "/api/v1/challenges/v1-mf-full/submit",
            headers=auth_headers(user),
            json={"flag": "value-alpha"},
        )
        assert first.status_code == 200
        first_points = first.json()["points_awarded"]

        second = await client.post(
            "/api/v1/challenges/v1-mf-full/submit",
            headers=auth_headers(user),
            json={"flag": "value-beta"},
        )
        assert second.status_code == 200
        second_points = second.json()["points_awarded"]

        # Solve row is now present with summed points.
        solve = (
            await db_session.execute(
                select(Solve).where(Solve.user_id == user.id)
            )
        ).scalars().first()
        assert solve is not None
        assert solve.points_awarded == first_points + second_points
        # Both SolvedFlag rows present.
        flag_ids = {
            r.flag_id
            for r in (
                await db_session.execute(
                    select(SolvedFlag).where(SolvedFlag.user_id == user.id)
                )
            ).scalars().all()
        }
        assert flag_ids == {"alpha", "beta"}

    async def test_progress_endpoint_reflects_partial_capture(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_multi_flag(
            db_session,
            slug="v1-mf-prog",
            parts=[("alpha", "value-alpha", 100), ("beta", "value-beta", 200)],
        )
        await client.post(
            "/api/v1/challenges/v1-mf-prog/submit",
            headers=auth_headers(user),
            json={"flag": "value-alpha"},
        )
        prog = await client.get(
            "/api/v1/challenges/v1-mf-prog/progress",
            headers=auth_headers(user),
        )
        body = prog.json()
        assert body["captured_flags"] == 1
        assert body["fully_captured"] is False
        assert body["points_captured"] == 125  # 100 * 1.25 first-blood-flag

    async def test_recapture_same_flag_returns_409(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_multi_flag(
            db_session,
            slug="v1-mf-dup",
            parts=[("alpha", "value-alpha", 100), ("beta", "value-beta", 200)],
        )
        first = await client.post(
            "/api/v1/challenges/v1-mf-dup/submit",
            headers=auth_headers(user),
            json={"flag": "value-alpha"},
        )
        assert first.status_code == 200
        # Resubmitting the same already-captured flag must 409.
        dup = await client.post(
            "/api/v1/challenges/v1-mf-dup/submit",
            headers=auth_headers(user),
            json={"flag": "value-alpha"},
        )
        assert dup.status_code == 409

    async def test_submit_after_full_capture_returns_409(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_multi_flag(
            db_session,
            slug="v1-mf-after",
            parts=[("alpha", "value-alpha", 100), ("beta", "value-beta", 200)],
        )
        await client.post(
            "/api/v1/challenges/v1-mf-after/submit",
            headers=auth_headers(user),
            json={"flag": "value-alpha"},
        )
        await client.post(
            "/api/v1/challenges/v1-mf-after/submit",
            headers=auth_headers(user),
            json={"flag": "value-beta"},
        )
        # Challenge is now fully captured. Any further submission is 409.
        r = await client.post(
            "/api/v1/challenges/v1-mf-after/submit",
            headers=auth_headers(user),
            json={"flag": "value-alpha"},
        )
        assert r.status_code == 409

    async def test_wrong_flag_does_not_capture(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_multi_flag(
            db_session,
            slug="v1-mf-wrong",
            parts=[("alpha", "value-alpha", 100), ("beta", "value-beta", 200)],
        )
        r = await client.post(
            "/api/v1/challenges/v1-mf-wrong/submit",
            headers=auth_headers(user),
            json={"flag": "definitely-not-the-flag"},
        )
        assert r.status_code == 200
        assert r.json()["correct"] is False
        rows = (
            await db_session.execute(
                select(SolvedFlag).where(SolvedFlag.user_id == user.id)
            )
        ).scalars().all()
        assert rows == []

    async def test_audit_ledger_emits_per_flag_pass_events(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_multi_flag(
            db_session,
            slug="v1-mf-audit",
            parts=[("alpha", "value-alpha", 100), ("beta", "value-beta", 200)],
        )
        await client.post(
            "/api/v1/challenges/v1-mf-audit/submit",
            headers=auth_headers(user),
            json={"flag": "value-alpha"},
        )
        await client.post(
            "/api/v1/challenges/v1-mf-audit/submit",
            headers=auth_headers(user),
            json={"flag": "value-beta"},
        )
        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "challenge.flag.submit.pass",
                    AuditLedger.actor_id == str(user.id),
                )
            )
        ).scalars().all()
        # Two pass events, one per captured flag.
        assert len(rows) == 2
        flag_ids = sorted(r.payload["flag_id"] for r in rows)
        assert flag_ids == ["alpha", "beta"]
        # Only the second event is fully_captured.
        captured_states = sorted(bool(r.payload["fully_captured"]) for r in rows)
        assert captured_states == [False, True]

    async def test_per_flag_first_blood_attribution(
        self, client, user_factory, auth_headers, db_session
    ):
        a_user = await user_factory(username="mf-a")
        b_user = await user_factory(username="mf-b")
        await _make_multi_flag(
            db_session,
            slug="v1-mf-fb",
            parts=[("alpha", "value-alpha", 100), ("beta", "value-beta", 200)],
        )
        # User A captures alpha first → first-blood for alpha.
        ra = await client.post(
            "/api/v1/challenges/v1-mf-fb/submit",
            headers=auth_headers(a_user),
            json={"flag": "value-alpha"},
        )
        # User B captures beta first → first-blood for beta.
        rb = await client.post(
            "/api/v1/challenges/v1-mf-fb/submit",
            headers=auth_headers(b_user),
            json={"flag": "value-beta"},
        )
        assert ra.json()["is_first_blood"] is True
        assert rb.json()["is_first_blood"] is True

        # User B then captures alpha second → not first-blood.
        rb2 = await client.post(
            "/api/v1/challenges/v1-mf-fb/submit",
            headers=auth_headers(b_user),
            json={"flag": "value-alpha"},
        )
        assert rb2.json()["is_first_blood"] is False


# ---------------------------------------------------------------------------
# Single-flag v1 + legacy paths unchanged
# ---------------------------------------------------------------------------
class TestSingleFlagBackwardCompat:
    async def test_single_flag_v1_creates_solve_immediately(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_multi_flag(
            db_session,
            slug="v1-single",
            parts=[("only", "value-only", 100)],
        )
        r = await client.post(
            "/api/v1/challenges/v1-single/submit",
            headers=auth_headers(user),
            json={"flag": "value-only"},
        )
        assert r.status_code == 200
        assert r.json()["correct"] is True
        solve = (
            await db_session.execute(
                select(Solve).where(Solve.user_id == user.id)
            )
        ).scalars().first()
        assert solve is not None
        # Subsequent submission returns 409.
        r2 = await client.post(
            "/api/v1/challenges/v1-single/submit",
            headers=auth_headers(user),
            json={"flag": "value-only"},
        )
        assert r2.status_code == 409

    async def test_legacy_challenge_unchanged(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-mf-legacy", flag="legacy-flag")
        r = await client.post(
            "/api/v1/challenges/v1-mf-legacy/submit",
            headers=auth_headers(user),
            json={"flag": "legacy-flag"},
        )
        assert r.status_code == 200
        solve = (
            await db_session.execute(
                select(Solve).where(Solve.user_id == user.id)
            )
        ).scalars().first()
        assert solve is not None
        # Re-submit returns 409.
        r2 = await client.post(
            "/api/v1/challenges/v1-mf-legacy/submit",
            headers=auth_headers(user),
            json={"flag": "legacy-flag"},
        )
        assert r2.status_code == 409
