"""User-engagement endpoints: submit flag, unlock hint, post feedback."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.rate_limit import flag_rate_limit
from app.models import Challenge, ChallengeFeedback, Solve, User
from app.schemas import FeedbackCreate, FlagResult, FlagSubmission
from app.services.audit.request_context import context_from_request
from app.services.auth import get_current_user
from app.services.flag_submission import (
    AlreadySolved,
    ChallengeNotFound,
    PrerequisitesNotMet,
    process_submission,
)
from app.services.hints import (
    AllHintsUnlocked,
    NoHintsAvailable,
    unlock_next_hint,
)

router = APIRouter()


@router.post("/{slug}/submit", response_model=FlagResult)
async def submit_flag(
    slug: str,
    data: FlagSubmission,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(flag_rate_limit),
):
    try:
        result = await process_submission(
            user=current_user,
            slug=slug,
            submitted_flag=data.flag,
            db=db,
            audit_context=context_from_request(request),
        )
    except ChallengeNotFound:
        raise HTTPException(status_code=404, detail="Challenge not found.")
    except AlreadySolved:
        raise HTTPException(status_code=400, detail="Challenge already solved.")
    except PrerequisitesNotMet:
        raise HTTPException(status_code=400, detail="Prerequisites not met.")

    if result.correct:
        return {
            "correct": True,
            "points_awarded": result.points_awarded,
            "is_first_blood": result.is_first_blood,
        }
    return {"correct": False}


@router.post("/{slug}/hint")
async def unlock_hint(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    challenge = (
        await db.execute(
            select(Challenge).where(
                Challenge.slug == slug, Challenge.is_active.is_(True)
            )
        )
    ).scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    try:
        index, text = await unlock_next_hint(
            user=current_user, challenge=challenge, db=db
        )
    except NoHintsAvailable:
        raise HTTPException(status_code=400, detail="No hints available.")
    except AllHintsUnlocked:
        raise HTTPException(status_code=400, detail="All hints already unlocked.")

    return {"index": index, "text": text}


async def _require_solved_challenge(
    slug: str, user_id: int, db: AsyncSession
) -> Challenge:
    challenge = (
        await db.execute(
            select(Challenge).where(
                Challenge.slug == slug, Challenge.is_active.is_(True)
            )
        )
    ).scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")
    has_solved = (
        await db.execute(
            select(
                exists().where(
                    and_(Solve.challenge_id == challenge.id, Solve.user_id == user_id)
                )
            )
        )
    ).scalar()
    if not has_solved:
        raise HTTPException(
            status_code=403,
            detail="You must solve the challenge before giving feedback.",
        )
    return challenge


@router.post("/{slug}/feedback")
async def submit_feedback(
    slug: str,
    data: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    challenge = await _require_solved_challenge(slug, current_user.id, db)
    db.add(
        ChallengeFeedback(
            user_id=current_user.id,
            challenge_id=challenge.id,
            difficulty_rating=data.difficulty_rating,
            quality_rating=data.quality_rating,
            feedback_text=data.feedback_text,
            created_at=datetime.now(timezone.utc),
        )
    )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Feedback already submitted for this challenge.",
        )
    return {"detail": "Feedback submitted."}
