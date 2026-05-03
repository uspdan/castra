import json
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.database import get_db
from app.config import get_settings
from app.models import User, Solve, Streak
from app.services.auth import get_current_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

LEADERBOARD_CACHE_TTL = 60


@router.get("/")
async def leaderboard(
    team: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        cache_key = f"siege:leaderboard:{team or 'all'}"
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    user_stmt = select(User).where(User.is_active == True)
    if team:
        user_stmt = user_stmt.where(User.team == team)

    users_result = await db.execute(user_stmt)
    users = users_result.scalars().all()

    entries = []
    for user in users:
        points_result = await db.execute(
            select(func.coalesce(func.sum(Solve.points_awarded), 0)).where(
                Solve.user_id == user.id
            )
        )
        total_points = points_result.scalar()

        solves_result = await db.execute(
            select(func.count(Solve.id)).where(Solve.user_id == user.id)
        )
        total_solves = solves_result.scalar()

        streak_result = await db.execute(
            select(Streak).where(Streak.user_id == user.id)
        )
        streak_row = streak_result.scalars().first()
        current_streak = streak_row.current_streak if streak_row else 0

        entries.append(
            {
                "user_id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "team": user.team,
                "total_points": total_points,
                "total_solves": total_solves,
                "current_streak": current_streak,
            }
        )

    entries.sort(key=lambda e: e["total_points"], reverse=True)

    for i, entry in enumerate(entries, 1):
        entry["rank"] = i

    try:
        await r.set(cache_key, json.dumps(entries, default=str), ex=LEADERBOARD_CACHE_TTL)
    except Exception:
        pass
    finally:
        await r.aclose()

    return entries


@router.get("/teams")
async def team_leaderboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    teams = []
    for team_name in ["red", "blue"]:
        points_result = await db.execute(
            select(func.coalesce(func.sum(Solve.points_awarded), 0))
            .join(User, Solve.user_id == User.id)
            .where(User.team == team_name, User.is_active == True)
        )
        total_points = points_result.scalar()

        solves_result = await db.execute(
            select(func.count(Solve.id))
            .join(User, Solve.user_id == User.id)
            .where(User.team == team_name, User.is_active == True)
        )
        total_solves = solves_result.scalar()

        member_result = await db.execute(
            select(func.count(User.id)).where(
                User.team == team_name, User.is_active == True
            )
        )
        member_count = member_result.scalar()

        avg_points = total_points / member_count if member_count > 0 else 0

        teams.append(
            {
                "team": team_name,
                "total_points": total_points,
                "total_solves": total_solves,
                "member_count": member_count,
                "avg_points_per_member": round(avg_points, 2),
            }
        )

    return teams


@router.get("/weekly")
async def weekly_leaderboard(
    team: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    week_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)

    user_stmt = select(User).where(User.is_active == True)
    if team:
        user_stmt = user_stmt.where(User.team == team)

    users_result = await db.execute(user_stmt)
    users = users_result.scalars().all()

    entries = []
    for user in users:
        points_result = await db.execute(
            select(func.coalesce(func.sum(Solve.points_awarded), 0)).where(
                Solve.user_id == user.id,
                Solve.solved_at >= week_start,
            )
        )
        total_points = points_result.scalar()

        solves_result = await db.execute(
            select(func.count(Solve.id)).where(
                Solve.user_id == user.id,
                Solve.solved_at >= week_start,
            )
        )
        total_solves = solves_result.scalar()

        if total_solves == 0:
            continue

        streak_result = await db.execute(
            select(Streak).where(Streak.user_id == user.id)
        )
        streak_row = streak_result.scalars().first()
        current_streak = streak_row.current_streak if streak_row else 0

        entries.append(
            {
                "user_id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "team": user.team,
                "total_points": total_points,
                "total_solves": total_solves,
                "current_streak": current_streak,
            }
        )

    entries.sort(key=lambda e: e["total_points"], reverse=True)

    for i, entry in enumerate(entries, 1):
        entry["rank"] = i

    return entries
