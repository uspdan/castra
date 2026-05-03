"""Flag submission flow.

Extracted from ``routers/challenges.py`` in Phase 6 so the router stays
thin (parse → service call → response). Encapsulates verification,
first-blood detection, scoring, persistence (Solve / SolvedFlag /
Notification / hash-chained AuditLedger), WebSocket broadcast, and
external webhook notification. Phase 12 (slice 8) removed the legacy
``AuditLog`` table writes — every event flows through the ledger.

Typed errors live here, not HTTP details — the router translates each to
the appropriate 4xx response.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Challenge,
    HintUnlock,
    Notification,
    Solve,
    SolvedFlag,
    User,
)
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.flag_dispatch import dispatch_submission
from app.services.scoring import calculate_flag_points, calculate_points, update_streak
from app.services.webhook_dispatch import deliver_event as deliver_webhook_event
from app.services.ws_manager import ws_manager


class SubmissionError(Exception):
    """Base for submission-domain errors. Routers map these to 4xx."""


class ChallengeNotFound(SubmissionError):
    """No active, released challenge with the given slug."""


class AlreadySolved(SubmissionError):
    """The user has already solved this challenge."""


class PrerequisitesNotMet(SubmissionError):
    """The user has not solved one or more prerequisite challenges.

    Carries the list of missing prerequisite slugs so the API layer can
    surface them to the client (the UI renders a "you need: …" hint
    instead of the generic 412 message).
    """

    def __init__(self, missing_slugs: tuple[str, ...] = ()):
        super().__init__()
        self.missing_slugs: tuple[str, ...] = tuple(missing_slugs)


@dataclass(frozen=True)
class SubmissionResult:
    correct: bool
    points_awarded: int | None = None
    is_first_blood: bool | None = None
    flag_id: str | None = None


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


async def _ensure_unsolved(user_id: int, challenge_id: int, db: AsyncSession) -> None:
    existing = (
        await db.execute(
            select(Solve.id).where(
                Solve.challenge_id == challenge_id, Solve.user_id == user_id
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
        # Preserve the order declared on the challenge so the hint is
        # deterministic and matches the manifest's intent.
        ordered = tuple(
            slug_by_id[mid] for mid in missing_ids if mid in slug_by_id
        )
        raise PrerequisitesNotMet(missing_slugs=ordered)


async def process_submission(
    *,
    user: User,
    slug: str,
    submitted_flag: str,
    db: AsyncSession,
    audit_context: dict[str, Any],
) -> SubmissionResult:
    """Run the full flag-submission flow.

    ``audit_context`` is the dict from
    ``services.audit.request_context.context_from_request(request)`` —
    passed in so this service stays free of FastAPI request internals.

    Two paths:

    * **Single-flag / legacy**: the historical one-shot path — first
      correct submission inserts ``Solve`` + ``SolvedFlag`` + emits
      audit + announces. ``AlreadySolved`` raised on any further
      submission.
    * **Multi-flag v1** (``len(challenge.flag_definitions) >= 2``):
      per-flag captures award per-flag points; the ``Solve`` row is
      created only when *every* declared flag has been captured by
      this user. Re-submitting a flag the user already captured
      raises ``AlreadySolved``. Submitting after the challenge is
      fully captured (``Solve`` exists) also raises ``AlreadySolved``.

    Raises ``ChallengeNotFound`` / ``AlreadySolved`` /
    ``PrerequisitesNotMet`` for the corresponding 4xx paths.
    """

    challenge = await _load_challenge(slug, db)
    flag_defs = list(challenge.flag_definitions or [])
    if len(flag_defs) >= 2:
        return await _process_multi_flag_submission(
            user=user,
            challenge=challenge,
            flag_defs=flag_defs,
            submitted_flag=submitted_flag,
            db=db,
            audit_context=audit_context,
        )

    await _ensure_unsolved(user.id, challenge.id, db)
    await _ensure_prerequisites(user.id, challenge, db)

    dispatch = await dispatch_submission(submitted_flag, challenge)
    if dispatch.correct:
        return await _record_pass(
            user=user,
            challenge=challenge,
            db=db,
            audit_context=audit_context,
            matched_flag_id=dispatch.flag_id,
            validator_name=dispatch.validator_name,
        )
    return await _record_fail(
        user=user, challenge=challenge, db=db, audit_context=audit_context
    )


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
                Solve.user_id == user.id, Solve.challenge_id == challenge.id
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
        # iterates the same rows we have in flag_defs — but treat as
        # a wrong submission so a misconfigured deployment doesn't
        # 500 the user.
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
        # User has already captured this specific flag; the rest of
        # the challenge may still be open. 409 keeps the single-flag
        # contract but the message can clarify.
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
                select(func.coalesce(func.sum(SolvedFlag.points_awarded), 0)).where(
                    SolvedFlag.user_id == user.id,
                    SolvedFlag.challenge_id == challenge.id,
                )
            )
        ).scalar() or 0
        total_points = int(total_points)
        challenge_first_blood = (
            await db.execute(
                select(Solve.id).where(Solve.challenge_id == challenge.id).limit(1)
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
        db.add(
            Notification(
                target_user_id=user.id,
                title="Challenge Fully Captured!",
                message=(
                    f"You captured every flag in '{challenge.title}' "
                    f"for {total_points} points!"
                ),
                notification_type="solve",
                is_global=False,
                created_at=now,
            )
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
        # ``points_awarded`` in the ledger payload is the points the
        # user just earned on this submission — not the cumulative
        # challenge total. ``is_first_blood`` is the per-flag value
        # so the audit chain agrees with the SubmissionResult the
        # caller returns.
        payload=payload,
        **audit_context,
    )
    # Phase 12 (slice 5): outbound webhook fan-out happens before the
    # final commit so any ``last_status`` updates on subscription
    # rows land atomically with the audit row. Failures are
    # swallowed inside ``deliver_webhook_event`` and surfaced via
    # ``last_status`` / ``last_error``; submissions never 500
    # because a receiver flapped.
    await deliver_webhook_event(
        db=db,
        event_type=EventType.FLAG_SUBMIT_PASS,
        payload=payload,
    )
    await db.commit()

    if fully_captured:
        await _announce_pass(user, challenge, total_points, challenge_first_blood)

    return SubmissionResult(
        correct=True,
        points_awarded=points,
        is_first_blood=is_first_blood_flag,
        flag_id=matched_flag.flag_id,
    )


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
    points_awarded = await calculate_points(challenge, user_id, hint_used, db)
    return is_first_blood, hint_used, points_awarded


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
    # challenges (no v1 ChallengeFlag rows, dispatch returns None)
    # use the sentinel "legacy" so the table's NOT NULL constraint
    # is satisfied without a special-case nullable column. The
    # ``flag_id`` column is constrained UNIQUE (user_id, challenge_id,
    # flag_id) so the duplicate-submission path is handled by the
    # caller's "already solved" check before we get here.
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
    db.add(
        Notification(
            target_user_id=user.id,
            title="Challenge Solved!",
            message=f"You solved '{challenge.title}' for {points_awarded} points!",
            notification_type="solve",
            is_global=False,
            created_at=now,
        )
    )


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


async def _announce_pass(
    user: User, challenge: Challenge, points_awarded: int, is_first_blood: bool
) -> None:
    # ws_manager.broadcast swallows its own failures so a WS-client
    # disconnection doesn't 500 the submission. Phase 12 (slice 9)
    # removed the legacy env-var Slack/Teams broadcast (notify_solve);
    # operators now subscribe to ``challenge.flag.submit.pass`` via
    # the v1 webhook surface — already fanned out before the caller
    # reaches us.
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
