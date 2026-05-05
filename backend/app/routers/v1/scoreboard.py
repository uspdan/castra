"""``GET /api/v1/scoreboard`` — locked scoreboard contract."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.v1.scoreboard import ScoreboardEntry, ScoreboardResponse
from app.services.auth import get_current_user
from app.services.scoreboard_cache import get_cached_scoreboard

router = APIRouter()


@router.get("/scoreboard", response_model=ScoreboardResponse)
async def scoreboard_v1(
    team: Optional[str] = Query(None, pattern="^(red|blue|purple)$"),
    limit: int = Query(100, ge=1, le=500),
    _viewer: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScoreboardResponse:
    rows = await get_cached_scoreboard(db, team_filter=team, limit=limit)
    return ScoreboardResponse(
        entries=[
            ScoreboardEntry(
                rank=row.rank,
                user_id=row.user_id,
                username=row.username,
                display_name=row.display_name,
                team=row.team,
                total_points=row.total_points,
                total_solves=row.total_solves,
                current_streak=row.current_streak,
            )
            for row in rows
        ],
        team_filter=team,
        generated_at=datetime.now(timezone.utc),
    )
