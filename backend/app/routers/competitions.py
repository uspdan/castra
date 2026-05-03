from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Challenge, Solve, Competition
from app.schemas import CompetitionCreate
from app.services.auth import get_current_user, require_admin

router = APIRouter(prefix="/competitions", tags=["competitions"])


@router.post("/")
async def create_competition(
    data: CompetitionCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    competition = Competition(
        title=data.title,
        description=data.description,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        challenge_ids=data.challenge_ids,
        is_active=data.is_active,
        hints_disabled=data.hints_disabled,
        format=data.format,
        created_by=admin.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(competition)
    await db.commit()
    await db.refresh(competition)

    return {
        "id": competition.id,
        "title": competition.title,
        "detail": "Competition created.",
    }


@router.get("/")
async def list_competitions(
    active: bool | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Competition)

    if active is True:
        now = datetime.now(timezone.utc)
        stmt = stmt.where(
            Competition.is_active == True,
            Competition.starts_at <= now,
            Competition.ends_at >= now,
        )

    stmt = stmt.order_by(Competition.created_at.desc())
    result = await db.execute(stmt)
    competitions = result.scalars().all()

    items = []
    for comp in competitions:
        now = datetime.now(timezone.utc)
        is_live = (
            comp.is_active
            and comp.starts_at
            and comp.ends_at
            and comp.starts_at <= now <= comp.ends_at
        )
        items.append(
            {
                "id": comp.id,
                "title": comp.title,
                "description": comp.description,
                "starts_at": str(comp.starts_at) if comp.starts_at else None,
                "ends_at": str(comp.ends_at) if comp.ends_at else None,
                "is_active": comp.is_active,
                "is_live": is_live,
                "challenge_count": len(comp.challenge_ids) if comp.challenge_ids else 0,
                "created_at": str(comp.created_at) if comp.created_at else None,
            }
        )

    return items


@router.get("/{competition_id}")
async def get_competition(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Competition).where(Competition.id == competition_id)
    )
    comp = result.scalars().first()
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found.")

    now = datetime.now(timezone.utc)
    is_live = (
        comp.is_active
        and comp.starts_at
        and comp.ends_at
        and comp.starts_at <= now <= comp.ends_at
    )

    response = {
        "id": comp.id,
        "title": comp.title,
        "description": comp.description,
        "starts_at": str(comp.starts_at) if comp.starts_at else None,
        "ends_at": str(comp.ends_at) if comp.ends_at else None,
        "is_active": comp.is_active,
        "is_live": is_live,
        "challenge_ids": comp.challenge_ids,
        "created_at": str(comp.created_at) if comp.created_at else None,
    }

    if is_live:
        scoreboard = await _build_competition_scoreboard(db, comp)
        response["scoreboard"] = scoreboard

    return response


@router.get("/{competition_id}/scoreboard")
async def competition_scoreboard(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Competition).where(Competition.id == competition_id)
    )
    comp = result.scalars().first()
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found.")

    scoreboard = await _build_competition_scoreboard(db, comp)
    return scoreboard


@router.post("/{competition_id}/activate")
async def activate_competition(
    competition_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Competition).where(Competition.id == competition_id)
    )
    comp = result.scalars().first()
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found.")

    comp.is_active = True
    await db.commit()

    return {"detail": "Competition activated.", "id": competition_id}


async def _build_competition_scoreboard(
    db: AsyncSession, competition: Competition
) -> list[dict]:
    challenge_ids = competition.challenge_ids if competition.challenge_ids else []
    if not challenge_ids:
        return []

    time_filter = []
    if competition.starts_at:
        time_filter.append(Solve.solved_at >= competition.starts_at)
    if competition.ends_at:
        time_filter.append(Solve.solved_at <= competition.ends_at)

    stmt = (
        select(
            Solve.user_id,
            User.username,
            User.display_name,
            User.team,
            func.coalesce(func.sum(Solve.points_awarded), 0).label("total_points"),
            func.count(Solve.id).label("total_solves"),
        )
        .join(User, Solve.user_id == User.id)
        .where(
            Solve.challenge_id.in_(challenge_ids),
            *time_filter,
        )
        .group_by(Solve.user_id, User.username, User.display_name, User.team)
        .order_by(func.sum(Solve.points_awarded).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    scoreboard = []
    for i, row in enumerate(rows, 1):
        scoreboard.append(
            {
                "rank": i,
                "user_id": row.user_id,
                "username": row.username,
                "display_name": row.display_name,
                "team": row.team,
                "total_points": row.total_points,
                "total_solves": row.total_solves,
            }
        )

    return scoreboard
