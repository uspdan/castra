"""``GET /api/v1/me`` — locked current-user contract."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.v1.me import MeResponse
from app.services.api_v1 import viewer_rank
from app.services.auth import get_current_user

router = APIRouter()


@router.get("/me", response_model=MeResponse)
async def me_v1(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    total_points, total_solves, current_streak, rank = await viewer_rank(
        db, viewer_id=current_user.id
    )
    # ``rank`` from ``viewer_rank`` is 1-based but defaults to 1 when
    # the viewer is alone in the table. Surface ``None`` when the user
    # has no solves AND no other ranked user is present, so clients can
    # render "unranked" rather than a misleading "1st place".
    rank_field = rank if total_points > 0 or total_solves > 0 else None
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name or current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        team=current_user.team.value if current_user.team else None,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        total_points=total_points,
        total_solves=total_solves,
        current_streak=current_streak,
        rank=rank_field,
    )
