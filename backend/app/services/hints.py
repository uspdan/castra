"""Hint unlock logic.

Extracted from ``routers/challenges.py`` in Phase 6 so the router stays
thin (parse → service call → response). The service takes the DB session
explicitly and raises typed errors; the router translates each to the
right HTTP status.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Challenge, HintUnlock, User


class HintError(Exception):
    """Base for hint-domain errors. Routers map these to 4xx responses."""


class NoHintsAvailable(HintError):
    """The challenge has no hints configured."""


class AllHintsUnlocked(HintError):
    """The user has already unlocked every hint for this challenge."""


async def unlock_next_hint(
    *,
    user: User,
    challenge: Challenge,
    db: AsyncSession,
) -> tuple[int, Any]:
    """Unlock the next still-locked hint for ``user`` on ``challenge``.

    Persists a ``HintUnlock`` row and commits the surrounding session.
    Returns ``(index, hint_value)``. ``hint_value`` is whatever's stored
    in ``Challenge.hints[index]`` — today the seed data uses both
    ``str`` and ``{"text": ..., "cost": ...}`` shapes; Phase 7's
    manifest v1 normalises this. Callers should not assume a string.

    Raises:
        NoHintsAvailable: ``challenge.hints`` is empty / null.
        AllHintsUnlocked: every index is already in ``hint_unlocks`` for
            this user.
    """

    hints = challenge.hints or []
    if not hints:
        raise NoHintsAvailable()

    unlocked_result = await db.execute(
        select(HintUnlock.hint_index).where(
            HintUnlock.user_id == user.id,
            HintUnlock.challenge_id == challenge.id,
        )
    )
    unlocked_indices = set(unlocked_result.scalars().all())

    next_index: int | None = None
    for i in range(len(hints)):
        if i not in unlocked_indices:
            next_index = i
            break

    if next_index is None:
        raise AllHintsUnlocked()

    db.add(
        HintUnlock(
            user_id=user.id,
            challenge_id=challenge.id,
            hint_index=next_index,
            unlocked_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    return next_index, hints[next_index]
