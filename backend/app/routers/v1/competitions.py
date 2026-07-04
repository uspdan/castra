"""``/api/v1/competitions/*`` — versioned competition surface.

Ports the legacy ``/competitions`` router onto the locked v1 contract.
Gated behind ``FEATURE_API_V1_COMPETITIONS`` (ships dark).

Endpoints:
- ``POST /api/v1/competitions``                       — admin create
- ``GET  /api/v1/competitions``                       — list (optional ?active)
- ``GET  /api/v1/competitions/{id}``                  — detail (+ live scoreboard)
- ``GET  /api/v1/competitions/{id}/scoreboard``       — scoreboard
- ``POST /api/v1/competitions/{id}/activate``         — admin activate
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Competition, Solve, User
from app.schemas.v1.competitions import (
    CompetitionActivateResponse,
    CompetitionCreatedResponse,
    CompetitionCreateRequest,
    CompetitionDetail,
    CompetitionScoreboardRow,
    CompetitionSummary,
)
from app.services.auth import get_current_user, require_admin
from app.services.feature_flags import require_flag

router = APIRouter(
    prefix="/competitions",
    tags=["v1-competitions"],
    dependencies=[Depends(require_flag("FEATURE_API_V1_COMPETITIONS"))],
)


def _team_value(team) -> Optional[str]:
    if team is None:
        return None
    return team.value if hasattr(team, "value") else str(team)


def _is_live(comp: Competition, now: datetime) -> bool:
    return bool(
        comp.is_active
        and comp.starts_at
        and comp.ends_at
        and comp.starts_at <= now <= comp.ends_at
    )


async def _load_competition(competition_id: int, db: AsyncSession) -> Competition:
    comp = (
        await db.execute(
            select(Competition).where(Competition.id == competition_id)
        )
    ).scalars().first()
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found.")
    return comp


async def _build_scoreboard(
    db: AsyncSession, competition: Competition
) -> List[CompetitionScoreboardRow]:
    challenge_ids = competition.challenge_ids or []
    if not challenge_ids:
        return []

    time_filter = []
    if competition.starts_at:
        time_filter.append(Solve.solved_at >= competition.starts_at)
    if competition.ends_at:
        time_filter.append(Solve.solved_at <= competition.ends_at)

    rows = (
        await db.execute(
            select(
                Solve.user_id,
                User.username,
                User.display_name,
                User.team,
                func.coalesce(func.sum(Solve.points_awarded), 0).label(
                    "total_points"
                ),
                func.count(Solve.id).label("total_solves"),
            )
            .join(User, Solve.user_id == User.id)
            .where(Solve.challenge_id.in_(challenge_ids), *time_filter)
            .group_by(Solve.user_id, User.username, User.display_name, User.team)
            .order_by(func.sum(Solve.points_awarded).desc())
        )
    ).all()

    return [
        CompetitionScoreboardRow(
            rank=i,
            user_id=row.user_id,
            username=row.username,
            display_name=row.display_name,
            team=_team_value(row.team),
            total_points=row.total_points,
            total_solves=row.total_solves,
        )
        for i, row in enumerate(rows, 1)
    ]


@router.post("", response_model=CompetitionCreatedResponse, status_code=201)
async def create_competition_v1(
    data: CompetitionCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CompetitionCreatedResponse:
    comp = Competition(
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
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return CompetitionCreatedResponse(
        id=comp.id, title=comp.title, detail="Competition created."
    )


@router.get("", response_model=List[CompetitionSummary])
async def list_competitions_v1(
    active: Optional[bool] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CompetitionSummary]:
    now = datetime.now(timezone.utc)
    stmt = select(Competition)
    if active is True:
        stmt = stmt.where(
            Competition.is_active == True,  # noqa: E712
            Competition.starts_at <= now,
            Competition.ends_at >= now,
        )
    stmt = stmt.order_by(Competition.created_at.desc())
    comps = (await db.execute(stmt)).scalars().all()

    return [
        CompetitionSummary(
            id=c.id,
            title=c.title,
            description=c.description,
            starts_at=c.starts_at,
            ends_at=c.ends_at,
            is_active=c.is_active,
            is_live=_is_live(c, now),
            challenge_count=len(c.challenge_ids) if c.challenge_ids else 0,
            created_at=c.created_at,
        )
        for c in comps
    ]


@router.get("/{competition_id}", response_model=CompetitionDetail)
async def get_competition_v1(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompetitionDetail:
    comp = await _load_competition(competition_id, db)
    now = datetime.now(timezone.utc)
    live = _is_live(comp, now)
    scoreboard = await _build_scoreboard(db, comp) if live else None
    return CompetitionDetail(
        id=comp.id,
        title=comp.title,
        description=comp.description,
        starts_at=comp.starts_at,
        ends_at=comp.ends_at,
        is_active=comp.is_active,
        is_live=live,
        challenge_ids=comp.challenge_ids or [],
        created_at=comp.created_at,
        scoreboard=scoreboard,
    )


@router.get(
    "/{competition_id}/scoreboard",
    response_model=List[CompetitionScoreboardRow],
)
async def competition_scoreboard_v1(
    competition_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[CompetitionScoreboardRow]:
    comp = await _load_competition(competition_id, db)
    return await _build_scoreboard(db, comp)


@router.post(
    "/{competition_id}/activate", response_model=CompetitionActivateResponse
)
async def activate_competition_v1(
    competition_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CompetitionActivateResponse:
    comp = await _load_competition(competition_id, db)
    comp.is_active = True
    await db.commit()
    return CompetitionActivateResponse(
        id=competition_id, detail="Competition activated."
    )
