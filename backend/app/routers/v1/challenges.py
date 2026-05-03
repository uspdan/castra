"""``GET /api/v1/challenges`` and ``GET /api/v1/challenges/{slug}``.

Locked DTOs in :mod:`app.schemas.v1.challenges`. Reuses the existing
:mod:`app.services.challenge_browse` aggregations and translates the
free-form dict shapes into the v1 response models. Translation is
explicit (field-by-field) rather than dict-passthrough so adding a
field to the legacy aggregation never silently leaks into v1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.v1.challenges import (
    PublicChallengeDetail,
    PublicChallengeListItem,
    PublicChallengeListResponse,
    PublicChallengePrerequisite,
    PublicHint,
    PublicTopSolver,
)
from app.services.auth import get_current_user
from app.services.challenge_browse import (
    ListFilters,
    get_challenge_detail,
    list_challenges,
)


router = APIRouter()


@router.get("/challenges", response_model=PublicChallengeListResponse)
async def list_challenges_v1(
    team: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    search: Optional[str] = Query(None, max_length=200),
    mitre: Optional[str] = Query(None, max_length=16),
    sort: str = Query("newest", pattern="^(newest|points|difficulty|solves)$"),
    page: int = Query(1, ge=1, le=10_000),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PublicChallengeListResponse:
    filters = ListFilters(
        team=team,
        category=category,
        difficulty=difficulty,
        search=search,
        mitre=mitre,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    raw = await list_challenges(viewer=current_user, filters=filters, db=db)
    return PublicChallengeListResponse(
        items=[_to_list_item(item) for item in raw["items"]],
        total=raw["total"],
        page=raw["page"],
        per_page=raw["per_page"],
    )


@router.get("/challenges/{slug}", response_model=PublicChallengeDetail)
async def get_challenge_v1(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PublicChallengeDetail:
    raw = await get_challenge_detail(slug=slug, viewer=current_user, db=db)
    if raw is None:
        raise HTTPException(status_code=404, detail="challenge not found")
    return _to_detail(raw)


# ---------------------------------------------------------------------------
# Translation: legacy dict → v1 DTO
# ---------------------------------------------------------------------------
def _to_list_item(raw: dict) -> PublicChallengeListItem:
    return PublicChallengeListItem(
        slug=raw["slug"],
        title=raw["title"],
        category=raw["category"],
        difficulty=int(raw["difficulty"]),
        points=int(raw["points"]),
        team=_team_str(raw["team"]),
        solve_count=int(raw["solve_count"] or 0),
        user_solved=bool(raw["user_solved"]),
        first_blood_user=raw.get("first_blood_user"),
        released_at=_parse_dt(raw.get("released_at")),
    )


def _to_detail(raw: dict) -> PublicChallengeDetail:
    return PublicChallengeDetail(
        slug=raw["slug"],
        title=raw["title"],
        description=raw["description"],
        category=raw["category"],
        difficulty=int(raw["difficulty"]),
        points=int(raw["points"]),
        team=_team_str(raw["team"]),
        skills=list(raw.get("skills") or []),
        mitre_techniques=list(raw.get("mitre_techniques") or []),
        hints=[_hint_to_dto(h) for h in raw.get("hints") or []],
        solve_count=int(raw.get("solve_count") or 0),
        user_solved=bool(raw.get("user_solved")),
        top_solvers=[
            _top_solver_to_dto(t) for t in raw.get("top_5_solvers") or []
        ],
        prerequisites=[
            _prereq_to_dto(p) for p in raw.get("prerequisites") or []
        ],
        writeup_count=int(raw.get("writeup_count") or 0),
        released_at=_parse_dt(raw.get("released_at")),
    )


def _hint_to_dto(raw: dict) -> PublicHint:
    text = raw.get("text") if not raw.get("locked") else None
    cost = 0
    if isinstance(text, dict):
        # Legacy seed format stores ``{"text": ..., "cost": ...}``
        # inside the JSON column. Surface text + cost separately.
        cost = int(text.get("cost") or 0)
        text = text.get("text")
    return PublicHint(
        index=int(raw.get("index") or 0),
        locked=bool(raw.get("locked")),
        text=None if raw.get("locked") else text,
        cost=cost,
    )


def _top_solver_to_dto(raw: dict) -> PublicTopSolver:
    return PublicTopSolver(
        display_name=raw["display_name"],
        username=raw["username"],
        solved_at=_parse_dt(raw["solved_at"]),
        points_awarded=int(raw["points_awarded"]),
    )


def _prereq_to_dto(raw: dict) -> PublicChallengePrerequisite:
    return PublicChallengePrerequisite(
        slug=raw["slug"],
        title=raw["title"],
        user_completed=bool(raw["user_completed"]),
    )


def _team_str(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    candidate = str(value)
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
