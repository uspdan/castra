from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Challenge, ChallengeFlag, Solve, SolvedFlag, Streak, TeamType


async def calculate_points(
    challenge: Challenge,
    user_id: int,
    hint_used: bool,
    db: AsyncSession,
    redis_client=None,
) -> int:
    settings = get_settings()
    base = challenge.points

    if settings.SCORING_MODE == "dynamic":
        solve_count_result = await db.execute(
            select(func.count(Solve.id)).where(Solve.challenge_id == challenge.id)
        )
        solve_count = solve_count_result.scalar() or 0
        base = max(challenge.points * 0.2, challenge.points * (0.95 ** solve_count))

    points = base

    # First blood bonus +25%
    first_solve = await db.execute(
        select(Solve.id).where(Solve.challenge_id == challenge.id).limit(1)
    )
    if first_solve.scalar_one_or_none() is None:
        points *= 1.25

    # Streak bonus: +5% per day, capped at +50%
    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user_id)
    )
    streak = streak_result.scalar_one_or_none()
    if streak and streak.current_streak > 0:
        streak_bonus = min(0.05 * streak.current_streak, 0.50)
        points *= (1 + streak_bonus)

    # Cross-training bonus: +10% if user has solves on both teams
    red_solves = await db.execute(
        select(func.count(Solve.id))
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .where(Solve.user_id == user_id, Challenge.team == TeamType.red)
    )
    blue_solves = await db.execute(
        select(func.count(Solve.id))
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .where(Solve.user_id == user_id, Challenge.team == TeamType.blue)
    )
    if (red_solves.scalar() or 0) > 0 and (blue_solves.scalar() or 0) > 0:
        points *= 1.10

    # Hint penalty: -50%
    if hint_used:
        points *= 0.50

    return max(1, round(points))


async def calculate_flag_points(
    challenge: Challenge,
    flag: ChallengeFlag,
    user_id: int,
    hint_used: bool,
    db: AsyncSession,
) -> int:
    """Score a single per-flag capture for a multi-flag v1 challenge.

    Mirrors :func:`calculate_points` but operates on the per-flag
    base value declared in the manifest. The "first blood" bonus
    fires when no other user has yet captured *this specific flag*
    (read from ``solved_flags``), not when no one has fully solved
    the challenge — multi-flag scoring rewards the racer who got
    each flag first, which is what blue-team co-op challenges
    actually want.

    Streak, cross-training, and hint-penalty multipliers are applied
    identically to :func:`calculate_points` so a per-flag capture
    looks like a smaller scaled solve from the user's perspective.
    """

    settings = get_settings()
    base = float(flag.points)

    if settings.SCORING_MODE == "dynamic":
        # Dynamic-decay: count how many users have already captured
        # this same flag, decay base by 5% per prior capture, floor
        # at 20% of declared points.
        capture_count = (
            await db.execute(
                select(func.count(SolvedFlag.id)).where(
                    SolvedFlag.challenge_id == challenge.id,
                    SolvedFlag.flag_id == flag.flag_id,
                )
            )
        ).scalar() or 0
        base = max(flag.points * 0.2, flag.points * (0.95 ** capture_count))

    points = base

    # First-blood-flag bonus +25%: nobody else has captured this
    # specific (challenge, flag) pair yet.
    fb = (
        await db.execute(
            select(SolvedFlag.id).where(
                SolvedFlag.challenge_id == challenge.id,
                SolvedFlag.flag_id == flag.flag_id,
            ).limit(1)
        )
    ).scalar_one_or_none()
    if fb is None:
        points *= 1.25

    # Streak bonus: +5% per day, capped at +50%
    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user_id)
    )
    streak = streak_result.scalar_one_or_none()
    if streak and streak.current_streak > 0:
        streak_bonus = min(0.05 * streak.current_streak, 0.50)
        points *= (1 + streak_bonus)

    # Cross-training bonus: +10% if user has solves on both teams.
    # Reads ``solves`` (per-challenge) so this remains a
    # challenge-level signal — the user must have completed at
    # least one challenge on each side.
    red_solves = await db.execute(
        select(func.count(Solve.id))
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .where(Solve.user_id == user_id, Challenge.team == TeamType.red)
    )
    blue_solves = await db.execute(
        select(func.count(Solve.id))
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .where(Solve.user_id == user_id, Challenge.team == TeamType.blue)
    )
    if (red_solves.scalar() or 0) > 0 and (blue_solves.scalar() or 0) > 0:
        points *= 1.10

    if hint_used:
        points *= 0.50

    return max(1, round(points))


async def update_streak(user_id: int, db: AsyncSession) -> None:
    result = await db.execute(select(Streak).where(Streak.user_id == user_id))
    streak = result.scalar_one_or_none()

    today = datetime.now(timezone.utc).date()

    if streak is None:
        streak = Streak(user_id=user_id, current_streak=1, longest_streak=1, last_solve_date=datetime.now(timezone.utc))
        db.add(streak)
    else:
        if streak.last_solve_date:
            last_date = streak.last_solve_date.date() if hasattr(streak.last_solve_date, 'date') else streak.last_solve_date
            if last_date == today:
                return
            elif last_date == today - timedelta(days=1):
                streak.current_streak += 1
            else:
                streak.current_streak = 1
        else:
            streak.current_streak = 1

        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak
        streak.last_solve_date = datetime.now(timezone.utc)
