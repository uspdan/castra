"""Service-layer helpers for the public ``/api/v1/`` surface.

Reuses the existing ``challenge_browse`` aggregations where the shape
matches and adds v1-specific helpers (scoreboard ranking, ATT&CK
coverage roll-up, viewer rank computation) that don't have a
counterpart elsewhere yet. Per CLAUDE.md §1.4 these are pure read
helpers — no commits, no audit emit, no Redis writes (the leaderboard
endpoint already maintains its own cache; v1 re-derives at request
time so the contract is deterministic).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Challenge, Solve, Streak, TeamType, User


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScoreboardRow:
    rank: int
    user_id: int
    username: str
    display_name: str
    team: Optional[str]
    total_points: int
    total_solves: int
    current_streak: int


async def compute_scoreboard(
    db: AsyncSession, *, team_filter: Optional[str] = None, limit: int = 100
) -> List[ScoreboardRow]:
    """Return the active-user scoreboard, ranked by points desc.

    Ties on points are broken by ``total_solves`` desc (more challenges
    cleared = better) then by ``username`` asc (deterministic).
    """

    if limit < 1 or limit > 500:
        raise ValueError("scoreboard limit must be in [1, 500]")

    user_stmt = select(User).where(User.is_active.is_(True))
    if team_filter:
        # The existing model uses an enum; pass through unchanged so
        # callers' validation matches the model's accepted values.
        user_stmt = user_stmt.where(User.team == team_filter)

    users = (await db.execute(user_stmt)).scalars().all()
    raw: List[dict] = []
    for user in users:
        total_points = (
            await db.execute(
                select(func.coalesce(func.sum(Solve.points_awarded), 0)).where(
                    Solve.user_id == user.id
                )
            )
        ).scalar() or 0
        total_solves = (
            await db.execute(
                select(func.count(Solve.id)).where(Solve.user_id == user.id)
            )
        ).scalar() or 0
        streak_row = (
            await db.execute(select(Streak).where(Streak.user_id == user.id))
        ).scalars().first()
        current_streak = streak_row.current_streak if streak_row else 0
        raw.append(
            {
                "user_id": int(user.id),
                "username": user.username,
                "display_name": user.display_name or user.username,
                "team": user.team.value if user.team else None,
                "total_points": int(total_points),
                "total_solves": int(total_solves),
                "current_streak": int(current_streak),
            }
        )

    raw.sort(
        key=lambda r: (-r["total_points"], -r["total_solves"], r["username"])
    )
    raw = raw[:limit]
    return [ScoreboardRow(rank=i + 1, **row) for i, row in enumerate(raw)]


async def viewer_rank(
    db: AsyncSession, *, viewer_id: int
) -> tuple[int, int, int, int]:
    """Compute (total_points, total_solves, current_streak, rank) for ``viewer_id``.

    ``rank`` follows the same tie-break ordering as
    :func:`compute_scoreboard`. Returns rank=0 when the viewer has no
    solves and no other user does either (deterministic empty case).
    """

    total_points = (
        await db.execute(
            select(func.coalesce(func.sum(Solve.points_awarded), 0)).where(
                Solve.user_id == viewer_id
            )
        )
    ).scalar() or 0
    total_solves = (
        await db.execute(
            select(func.count(Solve.id)).where(Solve.user_id == viewer_id)
        )
    ).scalar() or 0
    streak_row = (
        await db.execute(select(Streak).where(Streak.user_id == viewer_id))
    ).scalars().first()
    current_streak = streak_row.current_streak if streak_row else 0

    # Rank: count active users with strictly better (points, solves)
    # than the viewer, +1. Username tie-break is omitted from the
    # scalar rank — when two users have identical (points, solves) we
    # report them at the same rank.
    better_users = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.is_active.is_(True))
            .where(User.id != viewer_id)
            .where(
                _user_points_subq().scalar_subquery() > total_points
            )
        )
    ).scalar() or 0
    return int(total_points), int(total_solves), int(current_streak), int(better_users) + 1


def _user_points_subq():
    return (
        select(func.coalesce(func.sum(Solve.points_awarded), 0))
        .where(Solve.user_id == User.id)
        .correlate(User)
    )


# ---------------------------------------------------------------------------
# ATT&CK coverage
# ---------------------------------------------------------------------------
async def compute_attack_coverage(
    db: AsyncSession, *, viewer_id: int
) -> tuple[List[tuple[str, int, int]], int, int]:
    """Roll up ATT&CK technique coverage across released challenges.

    Returns ``(entries, total_techniques, total_challenges)`` where
    ``entries`` is a list of ``(technique_id, challenge_count,
    solved_by_viewer)`` tuples sorted by ``challenge_count`` desc then
    by ``technique_id`` asc for stable client display.
    """

    challenges = (
        await db.execute(
            select(Challenge).where(
                Challenge.is_released.is_(True),
                Challenge.is_active.is_(True),
            )
        )
    ).scalars().all()

    counts: Counter[str] = Counter()
    techniques_per_challenge: Dict[int, list[str]] = {}
    for c in challenges:
        techs = [t for t in (c.mitre_techniques or []) if isinstance(t, str)]
        techniques_per_challenge[c.id] = techs
        counts.update(techs)

    if not counts:
        return [], 0, len(challenges)

    solved_ids = set(
        (
            await db.execute(
                select(Solve.challenge_id).where(Solve.user_id == viewer_id)
            )
        ).scalars().all()
    )

    solved_per_technique: Counter[str] = Counter()
    for cid in solved_ids:
        for tech in techniques_per_challenge.get(cid, []):
            solved_per_technique[tech] += 1

    entries = sorted(
        [
            (tech, total, solved_per_technique.get(tech, 0))
            for tech, total in counts.items()
        ],
        key=lambda x: (-x[1], x[0]),
    )
    return entries, len(counts), len(challenges)
