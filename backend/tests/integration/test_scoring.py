"""Tests for app.services.scoring.

The scoring multipliers stack multiplicatively in this order, per
``calculate_points``:

    base                     ← challenge.points (or dynamic decay if enabled)
    × 1.25 if first blood
    × (1 + min(0.05 × current_streak, 0.50))
    × 1.10 if user has solved on both teams
    × 0.50 if a hint was unlocked

Final result is rounded to int, with a floor of 1 point.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _solve(db_session, user, challenge, *, points=10, is_first_blood=False):
    from app.models import Solve

    s = Solve(
        user_id=user.id,
        challenge_id=challenge.id,
        points_awarded=points,
        is_first_blood=is_first_blood,
        solved_at=datetime.now(timezone.utc),
    )
    db_session.add(s)
    await db_session.commit()
    return s


# ---------------------------------------------------------------------------
# calculate_points — base + bonuses
# ---------------------------------------------------------------------------
class TestCalculatePoints:
    async def test_base_points_with_no_bonuses(
        self, db_session, user_factory, challenge_factory
    ):
        # Disable first blood by pre-solving with a different user.
        from app.services.scoring import calculate_points

        solver = await user_factory(username="solver1")
        existing = await user_factory(username="firstblood1")
        challenge = await challenge_factory(points=100)
        await _solve(db_session, existing, challenge, points=100, is_first_blood=True)

        points = await calculate_points(challenge, solver.id, hint_used=False, db=db_session)
        # Base 100, no first blood, no streak, no cross-train, no hint → 100.
        assert points == 100

    async def test_first_blood_adds_25_percent(
        self, db_session, user_factory, challenge_factory
    ):
        from app.services.scoring import calculate_points

        user = await user_factory()
        challenge = await challenge_factory(points=100)

        points = await calculate_points(challenge, user.id, hint_used=False, db=db_session)
        # 100 × 1.25 = 125.
        assert points == 125

    async def test_hint_penalty_halves_points(
        self, db_session, user_factory, challenge_factory
    ):
        from app.services.scoring import calculate_points

        solver = await user_factory(username="hint-solver")
        first = await user_factory(username="hint-first")
        challenge = await challenge_factory(points=100)
        await _solve(db_session, first, challenge, points=100, is_first_blood=True)

        points = await calculate_points(challenge, solver.id, hint_used=True, db=db_session)
        # 100 × 0.5 = 50.
        assert points == 50

    async def test_streak_bonus_5_percent_per_day(
        self, db_session, user_factory, challenge_factory
    ):
        from app.models import Streak
        from app.services.scoring import calculate_points

        user = await user_factory()
        first = await user_factory(username="streak-first")
        challenge = await challenge_factory(points=100)
        await _solve(db_session, first, challenge, points=100, is_first_blood=True)

        streak = Streak(
            user_id=user.id,
            current_streak=4,
            longest_streak=4,
            last_solve_date=datetime.now(timezone.utc),
        )
        db_session.add(streak)
        await db_session.commit()

        points = await calculate_points(challenge, user.id, hint_used=False, db=db_session)
        # Base 100 × (1 + 0.05*4) = 100 × 1.20 = 120.
        assert points == 120

    async def test_streak_bonus_capped_at_50_percent(
        self, db_session, user_factory, challenge_factory
    ):
        from app.models import Streak
        from app.services.scoring import calculate_points

        user = await user_factory()
        first = await user_factory(username="streak-cap-first")
        challenge = await challenge_factory(points=100)
        await _solve(db_session, first, challenge, points=100, is_first_blood=True)

        streak = Streak(
            user_id=user.id,
            current_streak=20,  # would be +100% without the cap
            longest_streak=20,
            last_solve_date=datetime.now(timezone.utc),
        )
        db_session.add(streak)
        await db_session.commit()

        points = await calculate_points(challenge, user.id, hint_used=False, db=db_session)
        # Base 100 × 1.50 (capped) = 150.
        assert points == 150

    async def test_cross_training_bonus_when_both_teams(
        self, db_session, user_factory, challenge_factory
    ):
        from app.models import TeamType
        from app.services.scoring import calculate_points

        user = await user_factory()
        red = await challenge_factory(slug="red-1", team=TeamType.red)
        blue = await challenge_factory(slug="blue-1", team=TeamType.blue)

        # Pre-solve one of each team. Use a different user to take first
        # blood on the target challenge so the multiplier doesn't fire.
        first_user = await user_factory(username="cross-first")
        target = await challenge_factory(slug="cross-target", team=TeamType.red, points=100)
        await _solve(db_session, first_user, target, points=100, is_first_blood=True)

        await _solve(db_session, user, red, points=10)
        await _solve(db_session, user, blue, points=10)

        points = await calculate_points(target, user.id, hint_used=False, db=db_session)
        # Base 100 × 1.10 = 110.
        assert points == 110

    async def test_no_cross_training_bonus_when_only_one_team(
        self, db_session, user_factory, challenge_factory
    ):
        from app.models import TeamType
        from app.services.scoring import calculate_points

        user = await user_factory()
        red_only = await challenge_factory(slug="ro-1", team=TeamType.red)
        first = await user_factory(username="ro-first")
        target = await challenge_factory(slug="ro-target", team=TeamType.red, points=100)
        await _solve(db_session, first, target, points=100, is_first_blood=True)
        await _solve(db_session, user, red_only, points=10)

        points = await calculate_points(target, user.id, hint_used=False, db=db_session)
        # No first blood, no streak, only red → no cross-train bonus.
        assert points == 100

    async def test_minimum_one_point_floor(
        self, db_session, user_factory, challenge_factory, monkeypatch
    ):
        from app.services import scoring

        user = await user_factory()
        first = await user_factory(username="floor-first")
        challenge = await challenge_factory(points=1)
        await _solve(db_session, first, challenge, points=1, is_first_blood=True)

        points = await scoring.calculate_points(
            challenge, user.id, hint_used=True, db=db_session
        )
        # 1 × 0.5 = 0.5 → would round to 0; floored to 1.
        assert points == 1

    async def test_dynamic_decay_applied_when_mode_set(
        self, db_session, user_factory, challenge_factory, monkeypatch
    ):
        from app.config import _build_settings, get_settings
        from app.services import scoring

        # Force SCORING_MODE=dynamic for this test only. Bypass lru_cache by
        # patching the cached module-level reference inside scoring.py: it
        # calls get_settings() each time, so we just override the env and
        # clear the cache.
        import os

        monkeypatch.setenv("SCORING_MODE", "dynamic")
        _build_settings.cache_clear()
        try:
            user = await user_factory()
            challenge = await challenge_factory(points=100)

            # Two prior solves → decay factor = 0.95**2 = 0.9025.
            for i in range(2):
                u = await user_factory(username=f"prior{i}")
                await _solve(db_session, u, challenge, points=100, is_first_blood=(i == 0))

            points = await scoring.calculate_points(
                challenge, user.id, hint_used=False, db=db_session
            )
            # 100 × 0.9025 = 90.25, no first blood (already taken),
            # rounded → 90.
            assert points == 90
        finally:
            monkeypatch.delenv("SCORING_MODE", raising=False)
            _build_settings.cache_clear()

    async def test_dynamic_decay_floor_at_20_percent(
        self, db_session, user_factory, challenge_factory, monkeypatch
    ):
        from app.config import _build_settings
        from app.services import scoring

        monkeypatch.setenv("SCORING_MODE", "dynamic")
        _build_settings.cache_clear()
        try:
            user = await user_factory()
            challenge = await challenge_factory(points=100)
            # 50 prior solves; 0.95**50 ≈ 0.0769, well below floor.
            first = await user_factory(username="dyn-floor-first")
            await _solve(db_session, first, challenge, points=100, is_first_blood=True)
            for i in range(49):
                u = await user_factory(username=f"dynf{i}")
                await _solve(db_session, u, challenge, points=20)

            points = await scoring.calculate_points(
                challenge, user.id, hint_used=False, db=db_session
            )
            # Floor: 100 × 0.2 = 20.
            assert points == 20
        finally:
            monkeypatch.delenv("SCORING_MODE", raising=False)
            _build_settings.cache_clear()


# ---------------------------------------------------------------------------
# update_streak
# ---------------------------------------------------------------------------
class TestUpdateStreak:
    async def test_creates_streak_for_new_user(
        self, db_session, user_factory
    ):
        from app.models import Streak
        from app.services.scoring import update_streak

        user = await user_factory()
        await update_streak(user.id, db_session)
        await db_session.commit()

        streak = (
            await db_session.execute(select(Streak).where(Streak.user_id == user.id))
        ).scalar_one()
        assert streak.current_streak == 1
        assert streak.longest_streak == 1
        assert streak.last_solve_date is not None

    async def test_same_day_solve_does_not_increment(
        self, db_session, user_factory
    ):
        from app.models import Streak
        from app.services.scoring import update_streak

        user = await user_factory()
        streak = Streak(
            user_id=user.id,
            current_streak=3,
            longest_streak=3,
            last_solve_date=datetime.now(timezone.utc),
        )
        db_session.add(streak)
        await db_session.commit()

        await update_streak(user.id, db_session)
        await db_session.commit()
        await db_session.refresh(streak)
        assert streak.current_streak == 3

    async def test_consecutive_day_increments(
        self, db_session, user_factory
    ):
        from app.models import Streak
        from app.services.scoring import update_streak

        user = await user_factory()
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        streak = Streak(
            user_id=user.id,
            current_streak=5,
            longest_streak=5,
            last_solve_date=yesterday,
        )
        db_session.add(streak)
        await db_session.commit()

        await update_streak(user.id, db_session)
        await db_session.commit()
        await db_session.refresh(streak)
        assert streak.current_streak == 6
        assert streak.longest_streak == 6

    async def test_gap_resets_streak_to_one(
        self, db_session, user_factory
    ):
        from app.models import Streak
        from app.services.scoring import update_streak

        user = await user_factory()
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
        streak = Streak(
            user_id=user.id,
            current_streak=10,
            longest_streak=10,
            last_solve_date=three_days_ago,
        )
        db_session.add(streak)
        await db_session.commit()

        await update_streak(user.id, db_session)
        await db_session.commit()
        await db_session.refresh(streak)
        # Reset: gap > 1 day → current = 1, but longest preserved.
        assert streak.current_streak == 1
        assert streak.longest_streak == 10

    async def test_longest_only_updates_when_exceeded(
        self, db_session, user_factory
    ):
        from app.models import Streak
        from app.services.scoring import update_streak

        user = await user_factory()
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        streak = Streak(
            user_id=user.id,
            current_streak=2,
            longest_streak=10,  # historical high
            last_solve_date=yesterday,
        )
        db_session.add(streak)
        await db_session.commit()

        await update_streak(user.id, db_session)
        await db_session.commit()
        await db_session.refresh(streak)
        assert streak.current_streak == 3
        assert streak.longest_streak == 10  # unchanged: 3 < 10
