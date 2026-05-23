"""``app.services.flag_submission`` public façade.

Decomposed into submodules (R25 audit finding):

* ``_types``       — error hierarchy + ``SubmissionResult``.
* ``_validation``  — load challenge + ensure-unsolved + prerequisites.
* ``_persistence`` — single-flag (legacy) scoring + persist + emit +
                     announce + pass/fail recorders.
* ``_multi_flag``  — v1 multi-flag path (per-flag attribution).

External callers keep their existing
``from app.services.flag_submission import X`` imports unchanged.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services.flag_dispatch import dispatch_submission

from ._multi_flag import _process_multi_flag_submission
from ._persistence import _record_fail, _record_pass
from ._types import (
    AlreadySolved,
    ChallengeNotFound,
    PrerequisitesNotMet,
    SubmissionError,
    SubmissionResult,
)
from ._validation import (
    _ensure_prerequisites,
    _ensure_unsolved,
    _load_challenge,
)


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
    passed in so this service stays free of FastAPI request
    internals.

    Two paths:

    * **Single-flag / legacy**: the historical one-shot path —
      first correct submission inserts ``Solve`` + ``SolvedFlag``
      + emits audit + announces. ``AlreadySolved`` raised on any
      further submission.
    * **Multi-flag v1** (``len(challenge.flag_definitions) >= 2``):
      per-flag captures award per-flag points; the ``Solve`` row
      is created only when *every* declared flag has been captured
      by this user.

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
        user=user,
        challenge=challenge,
        db=db,
        audit_context=audit_context,
    )


__all__ = [
    "AlreadySolved",
    "ChallengeNotFound",
    "PrerequisitesNotMet",
    "SubmissionError",
    "SubmissionResult",
    "process_submission",
]
