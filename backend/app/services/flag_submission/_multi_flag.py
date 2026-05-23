"""Multi-flag submission path (v1 challenges with ≥2 declared flags).

Per-flag captures award per-flag points; the ``Solve`` row is
created only when every declared flag has been captured by this
user. Resubmitting an already-captured flag, or any further
submission once the challenge is fully captured, raises
:class:`AlreadySolved`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Challenge, Solve, SolvedFlag, User
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.flag_dispatch import dispatch_submission
from app.services.scoring import calculate_flag_points, update_streak
from app.services.webhook_dispatch import deliver_event as deliver_webhook_event

from ._persistence import (
    _announce_pass,
    _hint_used,
    _is_first_blood_flag,
    _record_fail,
)
from ._types import AlreadySolved, SubmissionResult
from ._validation import _ensure_prerequisites


async def _process_multi_flag_submission(
    *,
    user: User,
    challenge: Challenge,
    flag_defs: list,
    submitted_flag: str,
    db: AsyncSession,
    audit_context: dict[str, Any],
) -> SubmissionResult:
    # Challenge already fully captured — any further submission is
    # a no-op (409). Same semantics as the single-flag branch.
    existing_solve = (
        await db.execute(
            select(Solve.id).where(
                Solve.user_id == user.id,
                Solve.challenge_id == challenge.id,
            )
        )
    ).scalar_one_or_none()
    if existing_solve is not None:
        raise AlreadySolved()

    await _ensure_prerequisites(user.id, challenge, db)

    dispatch = await dispatch_submission(submitted_flag, challenge)
    if not dispatch.correct:
        return await _record_fail(
            user=user,
            challenge=challenge,
            db=db,
            audit_context=audit_context,
        )

    matched = next(
        (f for f in flag_defs if f.flag_id == dispatch.flag_id), None
    )
    if matched is None:
        # Dispatcher reported a flag_id that isn't in the challenge's
        # ChallengeFlag rows. Shouldn't happen — dispatch_submission
        # iterates the same rows — but treat as a wrong submission
        # so a misconfigured deployment doesn't 500 the user.
        return await _record_fail(
            user=user,
            challenge=challenge,
            db=db,
            audit_context=audit_context,
        )

    already = (
        await db.execute(
            select(SolvedFlag.id).where(
                SolvedFlag.user_id == user.id,
                SolvedFlag.challenge_id == challenge.id,
                SolvedFlag.flag_id == matched.flag_id,
            )
        )
    ).scalar_one_or_none()
    if already is not None:
        raise AlreadySolved()

    return await _record_multi_flag_pass(
        user=user,
        challenge=challenge,
        flag_defs=flag_defs,
        matched_flag=matched,
        validator_name=dispatch.validator_name,
        db=db,
        audit_context=audit_context,
    )


async def _record_multi_flag_pass(
    *,
    user: User,
    challenge: Challenge,
    flag_defs: list,
    matched_flag,
    validator_name: str | None,
    db: AsyncSession,
    audit_context: dict[str, Any],
) -> SubmissionResult:
    hint_used = await _hint_used(user.id, challenge.id, db)
    points = await calculate_flag_points(
        challenge, matched_flag, user.id, hint_used, db
    )
    is_first_blood_flag = await _is_first_blood_flag(
        challenge.id, matched_flag.flag_id, db
    )

    now = datetime.now(timezone.utc)
    db.add(
        SolvedFlag(
            user_id=user.id,
            challenge_id=challenge.id,
            flag_id=matched_flag.flag_id,
            points_awarded=points,
            is_first_blood_flag=is_first_blood_flag,
            validator_name=validator_name,
            solved_at=now,
        )
    )
    # Flush so the freshly-inserted row participates in the
    # all-flags-captured query below.
    await db.flush()

    captured_ids = set(
        (
            await db.execute(
                select(SolvedFlag.flag_id).where(
                    SolvedFlag.user_id == user.id,
                    SolvedFlag.challenge_id == challenge.id,
                )
            )
        ).scalars().all()
    )
    declared_ids = {f.flag_id for f in flag_defs}
    fully_captured = captured_ids >= declared_ids

    challenge_first_blood = False
    total_points = points
    if fully_captured:
        total_points = (
            await db.execute(
                select(
                    func.coalesce(func.sum(SolvedFlag.points_awarded), 0)
                ).where(
                    SolvedFlag.user_id == user.id,
                    SolvedFlag.challenge_id == challenge.id,
                )
            )
        ).scalar() or 0
        total_points = int(total_points)
        challenge_first_blood = (
            await db.execute(
                select(Solve.id)
                .where(Solve.challenge_id == challenge.id)
                .limit(1)
            )
        ).scalar_one_or_none() is None
        db.add(
            Solve(
                user_id=user.id,
                challenge_id=challenge.id,
                points_awarded=total_points,
                is_first_blood=challenge_first_blood,
                solved_at=now,
            )
        )
        await update_streak(user.id, db)
        from app.services.notifications import create_notification

        await create_notification(
            db,
            target_user_id=user.id,
            title="Challenge Fully Captured!",
            message=(
                f"You captured every flag in '{challenge.title}' "
                f"for {total_points} points!"
            ),
            notification_type="solve",
            is_global=False,
        )

    payload = {
        "challenge_slug": challenge.slug,
        "points_awarded": points,
        "is_first_blood": is_first_blood_flag,
        "flag_id": matched_flag.flag_id,
        "validator": validator_name,
        "fully_captured": fully_captured,
    }
    await audit_append(
        db,
        event_type=EventType.FLAG_SUBMIT_PASS,
        actor_type=ActorType.USER,
        actor_id=user.id,
        resource_type="challenge",
        resource_id=challenge.slug,
        # ``points_awarded`` in the ledger payload is the points
        # the user just earned on this submission — not the
        # cumulative challenge total. ``is_first_blood`` is the
        # per-flag value so the audit chain agrees with the
        # SubmissionResult the caller returns.
        payload=payload,
        **audit_context,
    )
    # Phase 12 (slice 5): outbound webhook fan-out happens before
    # the final commit so any ``last_status`` updates on
    # subscription rows land atomically with the audit row.
    await deliver_webhook_event(
        db=db,
        event_type=EventType.FLAG_SUBMIT_PASS,
        payload=payload,
    )
    await db.commit()

    if fully_captured:
        await _announce_pass(
            user, challenge, total_points, challenge_first_blood
        )

    return SubmissionResult(
        correct=True,
        points_awarded=points,
        is_first_blood=is_first_blood_flag,
        flag_id=matched_flag.flag_id,
    )


__all__ = ["_process_multi_flag_submission", "_record_multi_flag_pass"]
