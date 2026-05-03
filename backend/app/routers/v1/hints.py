"""``POST /api/v1/challenges/{slug}/hint`` — locked hint-unlock contract.

Reuses :func:`unlock_next_hint` from the existing hints service. The
v1 response normalises the legacy hint storage variants (bare string
vs. ``{"text": ..., "cost": ...}`` dict) into a single locked shape.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Challenge, User
from app.schemas.v1.hints import HintUnlockResponse
from app.services.auth import get_current_user
from app.services.hints import (
    AllHintsUnlocked,
    NoHintsAvailable,
    unlock_next_hint,
)


router = APIRouter()


@router.post(
    "/challenges/{slug}/hint",
    response_model=HintUnlockResponse,
    responses={
        404: {"description": "Challenge not found"},
        409: {"description": "No more hints to unlock"},
    },
)
async def unlock_hint_v1(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HintUnlockResponse:
    challenge = (
        await db.execute(
            select(Challenge).where(
                Challenge.slug == slug, Challenge.is_active.is_(True)
            )
        )
    ).scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="challenge not found")

    try:
        index, raw = await unlock_next_hint(
            user=current_user, challenge=challenge, db=db
        )
    except NoHintsAvailable:
        raise HTTPException(status_code=409, detail="no hints available")
    except AllHintsUnlocked:
        raise HTTPException(status_code=409, detail="all hints already unlocked")

    text, cost = _normalise_hint(raw)
    return HintUnlockResponse(index=index, text=text, cost=cost)


def _normalise_hint(raw) -> tuple[str, int]:
    """Normalise the two on-disk hint storage shapes into ``(text, cost)``.

    Phase 7's manifest v1 stores hints as ``{"text", "cost"}`` dicts.
    The legacy seed format stores bare strings. v1 callers see the
    same shape regardless of the source.
    """

    if isinstance(raw, dict):
        text = str(raw.get("text") or "")
        cost = int(raw.get("cost") or 0)
        return text, cost
    return str(raw), 0
