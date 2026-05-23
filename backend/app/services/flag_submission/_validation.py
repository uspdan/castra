"""Pre-flight checks for a submission attempt:

* challenge exists + released + active
* user hasn't already solved it
* user has solved every prerequisite
"""

from __future__ import annotations

from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Challenge, Solve

from ._types import AlreadySolved, ChallengeNotFound, PrerequisitesNotMet


async def _load_challenge(slug: str, db: AsyncSession) -> Challenge:
    challenge = (
        await db.execute(
            select(Challenge).where(
                Challenge.slug == slug,
                Challenge.is_released.is_(True),
                Challenge.is_active.is_(True),
            )
        )
    ).scalars().first()
    if not challenge:
        raise ChallengeNotFound(slug)
    return challenge


async def _ensure_unsolved(
    user_id: int, challenge_id: int, db: AsyncSession
) -> None:
    existing = (
        await db.execute(
            select(Solve.id).where(
                Solve.challenge_id == challenge_id,
                Solve.user_id == user_id,
            )
        )
    ).scalars().first()
    if existing is not None:
        raise AlreadySolved()


async def _ensure_prerequisites(
    user_id: int, challenge: Challenge, db: AsyncSession
) -> None:
    missing_ids: list[int] = []
    for prereq_id in challenge.prerequisite_ids or []:
        ok = (
            await db.execute(
                select(
                    exists().where(
                        and_(
                            Solve.challenge_id == prereq_id,
                            Solve.user_id == user_id,
                        )
                    )
                )
            )
        ).scalar()
        if not ok:
            missing_ids.append(int(prereq_id))
    if missing_ids:
        slug_rows = (
            await db.execute(
                select(Challenge.id, Challenge.slug).where(
                    Challenge.id.in_(missing_ids)
                )
            )
        ).all()
        slug_by_id = {int(r.id): r.slug for r in slug_rows}
        # Preserve the order declared on the challenge so the hint
        # is deterministic and matches the manifest's intent.
        ordered = tuple(
            slug_by_id[mid] for mid in missing_ids if mid in slug_by_id
        )
        raise PrerequisitesNotMet(missing_slugs=ordered)


__all__ = [
    "_ensure_prerequisites",
    "_ensure_unsolved",
    "_load_challenge",
]
