"""Read-side challenge endpoints: list + detail.

Both handlers are thin wrappers around ``services.challenge_browse``.
Phase 12 will lock the response shapes down with explicit DTOs.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.services.auth import get_current_user
from app.services.challenge_browse import (
    ListFilters,
    get_challenge_detail as _service_get_detail,
    list_challenges as _service_list,
)

router = APIRouter()


# Handler names match the originals so FastAPI's auto-generated
# operationId / summary in the OpenAPI document are unchanged from the
# pre-split state. Phase 6's gate requires an empty OpenAPI diff.
@router.get("/")
async def list_challenges(
    team: str | None = Query(None),
    category: str | None = Query(None),
    difficulty: str | None = Query(None),
    search: str | None = Query(None),
    mitre: str | None = Query(None),
    sort: str = Query("newest"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _service_list(
        viewer=current_user,
        filters=ListFilters(
            team=team,
            category=category,
            difficulty=difficulty,
            search=search,
            mitre=mitre,
            sort=sort,
            page=page,
            per_page=per_page,
        ),
        db=db,
    )


@router.get("/{slug}")
async def get_challenge(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    detail = await _service_get_detail(slug=slug, viewer=current_user, db=db)
    if detail is None:
        raise HTTPException(status_code=404, detail="Challenge not found.")
    return detail
