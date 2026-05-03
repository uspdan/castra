"""``GET /api/v1/challenges/{slug}/progress`` — per-flag progress.

Reads the ``solved_flags`` sidecar plus the manifest's
``challenge_flags`` rows to render per-flag captured/uncaptured state
for the calling user. Legacy challenges (no v1 flag definitions) are
served via a synthetic ``"legacy"`` entry so clients render a single
"fully captured" / "not captured" distinction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Challenge, ChallengeFlag, Solve, SolvedFlag, User
from app.schemas.v1.progress import (
    ChallengeProgressResponse,
    FlagProgressEntry,
)
from app.services.auth import get_current_user

router = APIRouter()


@router.get(
    "/challenges/{slug}/progress",
    response_model=ChallengeProgressResponse,
    responses={404: {"description": "Challenge not found"}},
)
async def challenge_progress_v1(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChallengeProgressResponse:
    challenge = (
        await db.execute(
            select(Challenge).where(
                Challenge.slug == slug, Challenge.is_active.is_(True)
            )
        )
    ).scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="challenge not found")

    flag_rows = (
        await db.execute(
            select(ChallengeFlag)
            .where(ChallengeFlag.challenge_id == challenge.id)
            .order_by(ChallengeFlag.id.asc())
        )
    ).scalars().all()

    captured_rows = {
        row.flag_id: row
        for row in (
            await db.execute(
                select(SolvedFlag).where(
                    SolvedFlag.user_id == current_user.id,
                    SolvedFlag.challenge_id == challenge.id,
                )
            )
        ).scalars().all()
    }

    if flag_rows:
        entries, totals = _v1_entries(flag_rows, captured_rows)
    else:
        entries, totals = await _legacy_entries(challenge, current_user, db)

    captured_count = sum(1 for e in entries if e.captured)
    points_captured = sum(
        e.points_awarded for e in entries
        if e.captured and e.points_awarded is not None
    )
    return ChallengeProgressResponse(
        challenge_slug=challenge.slug,
        flags=entries,
        total_flags=len(entries),
        captured_flags=captured_count,
        total_points_possible=totals,
        points_captured=points_captured,
        fully_captured=(len(entries) > 0 and captured_count == len(entries)),
    )


def _v1_entries(
    flag_rows: list[ChallengeFlag],
    captured_rows: dict[str, SolvedFlag],
) -> tuple[list[FlagProgressEntry], int]:
    entries: list[FlagProgressEntry] = []
    total_points = 0
    for flag in flag_rows:
        total_points += int(flag.points or 0)
        captured = captured_rows.get(flag.flag_id)
        entries.append(
            FlagProgressEntry(
                flag_id=flag.flag_id,
                flag_type=flag.flag_type,
                label=flag.label,
                points=int(flag.points or 0),
                points_awarded=(
                    int(captured.points_awarded) if captured else None
                ),
                captured=captured is not None,
                captured_at=_dt(captured.solved_at) if captured else None,
                is_first_blood_flag=(
                    bool(captured.is_first_blood_flag) if captured else None
                ),
                validator_name=(
                    captured.validator_name if captured else None
                ),
            )
        )
    return entries, total_points


async def _legacy_entries(
    challenge: Challenge, viewer: User, db: AsyncSession
) -> tuple[list[FlagProgressEntry], int]:
    """Synthesise a single ``"legacy"`` entry from the per-challenge Solve."""

    solve = (
        await db.execute(
            select(Solve).where(
                Solve.challenge_id == challenge.id,
                Solve.user_id == viewer.id,
            )
        )
    ).scalars().first()
    captured = solve is not None
    entry = FlagProgressEntry(
        flag_id="legacy",
        flag_type="exact",
        label=None,
        points=int(challenge.points or 0),
        points_awarded=int(solve.points_awarded) if solve else None,
        captured=captured,
        captured_at=_dt(solve.solved_at) if solve else None,
        is_first_blood_flag=bool(solve.is_first_blood) if solve else None,
        validator_name="exact" if captured else None,
    )
    return [entry], int(challenge.points or 0)


def _dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)
