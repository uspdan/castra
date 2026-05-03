from datetime import datetime, timezone

import bleach
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, exists, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Challenge, Solve, Writeup
from app.schemas import WriteupCreate, WriteupRate, WriteupRatingResponse
from app.services.auth import get_current_user, require_admin

router = APIRouter(prefix="/writeups", tags=["writeups"])

ALLOWED_TAGS = [
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "a", "img", "code", "pre", "em", "strong",
    "ul", "ol", "li", "blockquote", "hr",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target"],
    "img": ["src", "alt", "title", "width", "height"],
}


@router.post("/{slug}")
async def create_writeup(
    slug: str,
    data: WriteupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Challenge).where(Challenge.slug == slug, Challenge.is_active == True)
    )
    challenge = result.scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    solved_result = await db.execute(
        select(exists().where(
            and_(
                Solve.challenge_id == challenge.id,
                Solve.user_id == current_user.id,
            )
        ))
    )
    if not solved_result.scalar():
        raise HTTPException(
            status_code=403,
            detail="You must solve the challenge before submitting a writeup.",
        )

    sanitized_content = bleach.clean(
        data.content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True,
    )

    writeup = Writeup(
        user_id=current_user.id,
        challenge_id=challenge.id,
        title=data.title or f"Writeup for {challenge.title}",
        content=sanitized_content,
        is_approved=False,
        rating=0.0,
        rating_count=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(writeup)
    await db.commit()
    await db.refresh(writeup)

    return {
        "id": writeup.id,
        "title": writeup.title,
        "detail": "Writeup submitted for review.",
    }


@router.get("/{slug}")
async def list_writeups(
    slug: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Challenge).where(Challenge.slug == slug, Challenge.is_active == True)
    )
    challenge = result.scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    solved_result = await db.execute(
        select(exists().where(
            and_(
                Solve.challenge_id == challenge.id,
                Solve.user_id == current_user.id,
            )
        ))
    )
    if not solved_result.scalar():
        raise HTTPException(
            status_code=403,
            detail="You must solve the challenge to view writeups.",
        )

    total_result = await db.execute(
        select(func.count(Writeup.id)).where(
            Writeup.challenge_id == challenge.id,
            Writeup.is_approved == True,
        )
    )
    total = total_result.scalar()

    writeups_result = await db.execute(
        select(Writeup, User.display_name)
        .join(User, Writeup.user_id == User.id)
        .where(
            Writeup.challenge_id == challenge.id,
            Writeup.is_approved == True,
        )
        .order_by(Writeup.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = writeups_result.all()

    items = [
        {
            "id": writeup.id,
            "title": writeup.title,
            "content": writeup.content,
            "author_display_name": display_name,
            "rating": writeup.rating,
            "rating_count": writeup.rating_count,
            "created_at": str(writeup.created_at),
        }
        for writeup, display_name in rows
    ]

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("/{writeup_id}/rate", response_model=WriteupRatingResponse)
async def rate_writeup(
    writeup_id: int,
    data: WriteupRate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Writeup).where(Writeup.id == writeup_id))
    writeup = result.scalars().first()
    if not writeup:
        raise HTTPException(status_code=404, detail="Writeup not found.")

    old_rating = writeup.rating or 0.0
    old_count = writeup.rating_count or 0
    new_count = old_count + 1
    new_rating = ((old_rating * old_count) + data.rating) / new_count

    writeup.rating = round(new_rating, 2)
    writeup.rating_count = new_count
    await db.commit()

    return {
        "rating": writeup.rating,
        "rating_count": writeup.rating_count,
    }


@router.put("/{writeup_id}/approve")
async def approve_writeup(
    writeup_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Writeup).where(Writeup.id == writeup_id))
    writeup = result.scalars().first()
    if not writeup:
        raise HTTPException(status_code=404, detail="Writeup not found.")

    writeup.is_approved = True
    await db.commit()

    return {"detail": "Writeup approved.", "id": writeup_id}
