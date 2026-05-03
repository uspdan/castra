"""``/api/v1/leaderboard/*`` — locked team / weekly leaderboard contract.

The user-ranked scoreboard already lives at ``/api/v1/scoreboard``
(slice 1). This module covers the other two leaderboard surfaces the
front door uses:

- ``GET /api/v1/leaderboard/teams``  — red vs blue aggregate stats.
- ``GET /api/v1/leaderboard/weekly`` — current ISO week per-user
  ranking, with optional ``team`` filter.

Both endpoints re-derive on demand (no Redis cache) for contract
determinism — operators with hot leaderboard load can keep using the
legacy cached ``/leaderboard/`` route until a v1 cache plan lands.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Solve, Streak, TeamType, User
from app.schemas.v1.leaderboard import (
    TeamLeaderboardEntry,
    TeamLeaderboardResponse,
    WeeklyLeaderboardEntry,
    WeeklyLeaderboardResponse,
)
from app.services.auth import get_current_user


router = APIRouter()


@router.get("/leaderboard/teams", response_model=TeamLeaderboardResponse)
async def team_leaderboard_v1(
    _viewer: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeamLeaderboardResponse:
    teams: List[TeamLeaderboardEntry] = []
    for team_name in (TeamType.red, TeamType.blue):
        total_points = (
            await db.execute(
                select(func.coalesce(func.sum(Solve.points_awarded), 0))
                .join(User, Solve.user_id == User.id)
                .where(User.team == team_name, User.is_active.is_(True))
            )
        ).scalar() or 0
        total_solves = (
            await db.execute(
                select(func.count(Solve.id))
                .join(User, Solve.user_id == User.id)
                .where(User.team == team_name, User.is_active.is_(True))
            )
        ).scalar() or 0
        member_count = (
            await db.execute(
                select(func.count(User.id)).where(
                    User.team == team_name, User.is_active.is_(True)
                )
            )
        ).scalar() or 0

        avg = (total_points / member_count) if member_count else 0.0
        teams.append(
            TeamLeaderboardEntry(
                team=team_name.value,
                total_points=int(total_points),
                total_solves=int(total_solves),
                member_count=int(member_count),
                avg_points_per_member=round(float(avg), 2),
            )
        )

    return TeamLeaderboardResponse(
        teams=teams,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/leaderboard/weekly", response_model=WeeklyLeaderboardResponse)
async def weekly_leaderboard_v1(
    team: Optional[str] = Query(None, pattern="^(red|blue)$"),
    limit: int = Query(100, ge=1, le=500),
    _viewer: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WeeklyLeaderboardResponse:
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    user_stmt = select(User).where(User.is_active.is_(True))
    if team:
        user_stmt = user_stmt.where(User.team == TeamType(team))

    users = (await db.execute(user_stmt)).scalars().all()
    rows: list[dict] = []
    for user in users:
        weekly_points = (
            await db.execute(
                select(func.coalesce(func.sum(Solve.points_awarded), 0)).where(
                    Solve.user_id == user.id,
                    Solve.solved_at >= week_start,
                )
            )
        ).scalar() or 0
        weekly_solves = (
            await db.execute(
                select(func.count(Solve.id)).where(
                    Solve.user_id == user.id,
                    Solve.solved_at >= week_start,
                )
            )
        ).scalar() or 0
        if weekly_solves == 0:
            # Match the legacy router: only ranked users with at least
            # one solve this week appear in the table.
            continue

        streak_row = (
            await db.execute(select(Streak).where(Streak.user_id == user.id))
        ).scalars().first()
        rows.append(
            {
                "user_id": int(user.id),
                "username": user.username,
                "display_name": user.display_name or user.username,
                "team": user.team.value if user.team else None,
                "total_points": int(weekly_points),
                "total_solves": int(weekly_solves),
                "current_streak": int(
                    streak_row.current_streak if streak_row else 0
                ),
            }
        )

    rows.sort(
        key=lambda r: (-r["total_points"], -r["total_solves"], r["username"])
    )
    rows = rows[:limit]
    entries = [
        WeeklyLeaderboardEntry(rank=i + 1, **row)
        for i, row in enumerate(rows)
    ]
    return WeeklyLeaderboardResponse(
        entries=entries,
        team_filter=team,
        week_start=week_start,
        generated_at=now,
    )
