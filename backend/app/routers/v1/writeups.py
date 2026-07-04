"""``/api/v1/writeups/*`` — versioned write-up surface.

Ports the legacy ``/writeups`` router onto the locked v1 contract with
``extra="forbid"`` DTOs. Gated behind ``FEATURE_API_V1_WRITEUPS`` — while
the flag is off the whole surface 404s (ships dark).

Endpoints:
- ``POST /api/v1/writeups/{slug}``            — submit (must have solved)
- ``GET  /api/v1/writeups/{slug}``            — list approved (must have solved)
- ``POST /api/v1/writeups/{writeup_id}/rate`` — rate 1..5
- ``PUT  /api/v1/writeups/{writeup_id}/approve`` — admin approve
"""

from __future__ import annotations

from datetime import datetime, timezone

import bleach
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Challenge, Solve, User, Writeup
from app.schemas.v1.writeups import (
    WriteupApproveResponse,
    WriteupCreatedResponse,
    WriteupCreateRequest,
    WriteupItem,
    WriteupListResponse,
    WriteupRateRequest,
    WriteupRatingResponse,
)
from app.services.auth import get_current_user, require_admin
from app.services.feature_flags import require_flag

router = APIRouter(
    prefix="/writeups",
    tags=["v1-writeups"],
    dependencies=[Depends(require_flag("FEATURE_API_V1_WRITEUPS"))],
)

_ALLOWED_TAGS = [
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "a", "img", "code", "pre", "em", "strong",
    "ul", "ol", "li", "blockquote", "hr",
]
_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target"],
    "img": ["src", "alt", "title", "width", "height"],
}


async def _load_solved_challenge(
    slug: str, user: User, db: AsyncSession, action: str
) -> Challenge:
    """Fetch an active challenge and assert the user has solved it."""
    result = await db.execute(
        select(Challenge).where(
            Challenge.slug == slug, Challenge.is_active == True  # noqa: E712
        )
    )
    challenge = result.scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    solved = await db.execute(
        select(
            exists().where(
                and_(
                    Solve.challenge_id == challenge.id,
                    Solve.user_id == user.id,
                )
            )
        )
    )
    if not solved.scalar():
        raise HTTPException(
            status_code=403,
            detail=f"You must solve the challenge to {action}.",
        )
    return challenge


@router.post("/{slug}", response_model=WriteupCreatedResponse, status_code=201)
async def create_writeup_v1(
    slug: str,
    data: WriteupCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WriteupCreatedResponse:
    challenge = await _load_solved_challenge(
        slug, current_user, db, "submit a writeup"
    )

    sanitized = bleach.clean(
        data.content,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        strip=True,
    )
    writeup = Writeup(
        user_id=current_user.id,
        challenge_id=challenge.id,
        title=data.title or f"Writeup for {challenge.title}",
        content=sanitized,
        is_approved=False,
        rating=0.0,
        rating_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(writeup)
    await db.commit()
    await db.refresh(writeup)

    return WriteupCreatedResponse(
        id=writeup.id,
        title=writeup.title,
        detail="Writeup submitted for review.",
    )


@router.get("/{slug}", response_model=WriteupListResponse)
async def list_writeups_v1(
    slug: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WriteupListResponse:
    challenge = await _load_solved_challenge(
        slug, current_user, db, "view writeups"
    )

    total = (
        await db.execute(
            select(func.count(Writeup.id)).where(
                Writeup.challenge_id == challenge.id,
                Writeup.is_approved == True,  # noqa: E712
            )
        )
    ).scalar() or 0

    rows = (
        await db.execute(
            select(Writeup, User.display_name)
            .join(User, Writeup.user_id == User.id)
            .where(
                Writeup.challenge_id == challenge.id,
                Writeup.is_approved == True,  # noqa: E712
            )
            .order_by(Writeup.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    items = [
        WriteupItem(
            id=writeup.id,
            title=writeup.title,
            content=writeup.content,
            author_display_name=display_name,
            rating=writeup.rating or 0.0,
            rating_count=writeup.rating_count or 0,
            created_at=writeup.created_at,
        )
        for writeup, display_name in rows
    ]
    return WriteupListResponse(
        items=items, total=total, page=page, per_page=per_page
    )


@router.post("/{writeup_id}/rate", response_model=WriteupRatingResponse)
async def rate_writeup_v1(
    writeup_id: int,
    data: WriteupRateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WriteupRatingResponse:
    writeup = (
        await db.execute(select(Writeup).where(Writeup.id == writeup_id))
    ).scalars().first()
    if not writeup:
        raise HTTPException(status_code=404, detail="Writeup not found.")

    old_rating = writeup.rating or 0.0
    old_count = writeup.rating_count or 0
    new_count = old_count + 1
    writeup.rating = round(((old_rating * old_count) + data.rating) / new_count, 2)
    writeup.rating_count = new_count
    await db.commit()

    return WriteupRatingResponse(
        rating=writeup.rating, rating_count=writeup.rating_count
    )


@router.put("/{writeup_id}/approve", response_model=WriteupApproveResponse)
async def approve_writeup_v1(
    writeup_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WriteupApproveResponse:
    writeup = (
        await db.execute(select(Writeup).where(Writeup.id == writeup_id))
    ).scalars().first()
    if not writeup:
        raise HTTPException(status_code=404, detail="Writeup not found.")

    writeup.is_approved = True
    await db.commit()
    return WriteupApproveResponse(id=writeup_id, detail="Writeup approved.")
