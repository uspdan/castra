"""Scoring + persistence + audit emit + announce for the
single-flag (legacy) submission path.

Multi-flag persistence lives in ``_multi_flag.py`` because the
flow is different enough that sharing helpers would just produce
a tangle of optional-args.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Challenge,
    HintUnlock,
    Solve,
    SolvedFlag,
    User,
)
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.scoring import calculate_points, update_streak
from app.services.webhook_dispatch import deliver_event as deliver_webhook_event
from app.services.ws_manager import ws_manager

from ._types import SubmissionResult


async def _hint_used(
    user_id: int, challenge_id: int, db: AsyncSession
) -> bool:
    return (
        (
            await db.execute(
                select(func.count(HintUnlock.id)).where(
                    HintUnlock.user_id == user_id,
                    HintUnlock.challenge_id == challenge_id,
                )
            )
        ).scalar()
        or 0
    ) > 0


async def _score_pass_inputs(
    user_id: int, challenge: Challenge, db: AsyncSession
) -> tuple[bool, bool, int]:
    """Compute (is_first_blood, hint_used, points_awarded)."""

    is_first_blood = (
        (
            await db.execute(
                select(func.count(Solve.id)).where(
                    Solve.challenge_id == challenge.id
                )
            )
        ).scalar()
        or 0
    ) == 0
    hint_used = (
        (
            await db.execute(
                select(func.count(HintUnlock.id)).where(
                    HintUnlock.user_id == user_id,
                    HintUnlock.challenge_id == challenge.id,
                )
            )
        ).scalar()
        or 0
    ) > 0
    points_awarded = await calculate_points(
        challenge, user_id, hint_used, db
    )
    return is_first_blood, hint_used, points_awarded


async def _is_first_blood_flag(
    challenge_id: int, flag_id: str, db: AsyncSession
) -> bool:
    """True iff no other user has yet captured this (challenge, flag)."""

    existing = (
        await db.execute(
            select(func.count(SolvedFlag.id)).where(
                SolvedFlag.challenge_id == challenge_id,
                SolvedFlag.flag_id == flag_id,
            )
        )
    ).scalar() or 0
    return existing == 0


async def _persist_pass(
    *,
    user: User,
    challenge: Challenge,
    points_awarded: int,
    is_first_blood: bool,
    db: AsyncSession,
    matched_flag_id: str | None = None,
    validator_name: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    db.add(
        Solve(
            user_id=user.id,
            challenge_id=challenge.id,
            points_awarded=points_awarded,
            is_first_blood=is_first_blood,
            solved_at=now,
        )
    )
    # Phase 12 (slice 3): record per-flag attribution. Legacy
    # challenges (no v1 ChallengeFlag rows, dispatch returns
    # None) use the sentinel "legacy" so the table's NOT NULL
    # constraint is satisfied without a special-case nullable
    # column.
    flag_id_value = matched_flag_id or "legacy"
    is_first_blood_flag = await _is_first_blood_flag(
        challenge.id, flag_id_value, db
    )
    db.add(
        SolvedFlag(
            user_id=user.id,
            challenge_id=challenge.id,
            flag_id=flag_id_value,
            points_awarded=points_awarded,
            is_first_blood_flag=is_first_blood_flag,
            validator_name=validator_name,
            solved_at=now,
        )
    )
    await update_streak(user.id, db)
    from app.services.notifications import create_notification

    await create_notification(
        db,
        target_user_id=user.id,
        title="Challenge Solved!",
        message=f"You solved '{challenge.title}' for {points_awarded} points!",
        notification_type="solve",
        is_global=False,
    )


async def _announce_pass(
    user: User,
    challenge: Challenge,
    points_awarded: int,
    is_first_blood: bool,
) -> None:
    # ws_manager.broadcast swallows its own failures so a
    # WS-client disconnection doesn't 500 the submission.
    # Phase 12 (slice 9) removed the legacy env-var Slack/Teams
    # broadcast — operators now subscribe to
    # ``challenge.flag.submit.pass`` via the v1 webhook surface
    # already fanned out before the caller reaches us.
    await ws_manager.broadcast(
        {
            "type": "flag_captured",
            "user": user.username,
            "challenge": challenge.slug,
            "points": points_awarded,
            "is_first_blood": is_first_blood,
        }
    )


async def _record_pass(
    *,
    user: User,
    challenge: Challenge,
    db: AsyncSession,
    audit_context: dict[str, Any],
    matched_flag_id: str | None = None,
    validator_name: str | None = None,
) -> SubmissionResult:
    is_first_blood, hint_used, points_awarded = await _score_pass_inputs(
        user.id, challenge, db
    )
    await _persist_pass(
        user=user,
        challenge=challenge,
        points_awarded=points_awarded,
        is_first_blood=is_first_blood,
        db=db,
        matched_flag_id=matched_flag_id,
        validator_name=validator_name,
    )
    payload = {
        "challenge_slug": challenge.slug,
        "points_awarded": points_awarded,
        "is_first_blood": is_first_blood,
        "hint_used": hint_used,
        "flag_id": matched_flag_id,
        "validator": validator_name,
    }
    await audit_append(
        db,
        event_type=EventType.FLAG_SUBMIT_PASS,
        actor_type=ActorType.USER,
        actor_id=user.id,
        resource_type="challenge",
        resource_id=challenge.slug,
        payload=payload,
        **audit_context,
    )
    # Phase 12 (slice 5): outbound webhook fan-out (best-effort,
    # last_status persisted on subscription row).
    await deliver_webhook_event(
        db=db,
        event_type=EventType.FLAG_SUBMIT_PASS,
        payload=payload,
    )
    await db.commit()
    await _announce_pass(user, challenge, points_awarded, is_first_blood)
    return SubmissionResult(
        correct=True,
        points_awarded=points_awarded,
        is_first_blood=is_first_blood,
        flag_id=matched_flag_id,
    )


async def _record_fail(
    *,
    user: User,
    challenge: Challenge,
    db: AsyncSession,
    audit_context: dict[str, Any],
) -> SubmissionResult:
    await audit_append(
        db,
        event_type=EventType.FLAG_SUBMIT_FAIL,
        actor_type=ActorType.USER,
        actor_id=user.id,
        resource_type="challenge",
        resource_id=challenge.slug,
        payload={"challenge_slug": challenge.slug},
        **audit_context,
    )
    await db.commit()
    return SubmissionResult(correct=False)


__all__ = [
    "_announce_pass",
    "_hint_used",
    "_is_first_blood_flag",
    "_persist_pass",
    "_record_fail",
    "_record_pass",
    "_score_pass_inputs",
]
