"""``POST /api/v1/challenges/{slug}/submit`` — locked submission contract.

Reuses :func:`process_submission` from the existing flag-submission
service so behaviour is bit-for-bit identical to the legacy
unversioned endpoint. Differences vs. legacy:

* Locked request + response DTOs (``SubmitFlagRequest`` /
  ``SubmitFlagResponse``).
* Response carries ``flag_id`` + ``validator`` on a correct match —
  the legacy shape only returns the boolean, points, and first-blood
  flag.
* 4xx mapping documents the structured cases (404 unknown challenge,
  409 already-solved, 412 prerequisite-not-met) instead of the
  legacy 400-for-everything.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.rate_limit import flag_rate_limit
from app.models import User
from app.schemas.v1.submission import SubmitFlagRequest, SubmitFlagResponse
from app.services.audit.request_context import context_from_request
from app.services.auth import get_current_user
from app.services.flag_submission import (
    AlreadySolved,
    ChallengeNotFound,
    PrerequisitesNotMet,
    process_submission,
)


router = APIRouter()


@router.post(
    "/challenges/{slug}/submit",
    response_model=SubmitFlagResponse,
    responses={
        404: {"description": "Challenge not found or not released"},
        409: {"description": "Challenge already solved by this user"},
        412: {"description": "Prerequisite challenges not yet solved"},
        429: {"description": "Submission rate limit exceeded"},
    },
)
async def submit_flag_v1(
    slug: str,
    data: SubmitFlagRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(flag_rate_limit),
) -> SubmitFlagResponse:
    try:
        result = await process_submission(
            user=current_user,
            slug=slug,
            submitted_flag=data.flag,
            db=db,
            audit_context=context_from_request(request),
        )
    except ChallengeNotFound:
        raise HTTPException(status_code=404, detail="challenge not found")
    except AlreadySolved:
        # 409 (Conflict) is the right code for "the resource already
        # exists in the state you'd be transitioning it to" — the
        # user can't solve a challenge twice. The legacy endpoint
        # returns 400; v1 is locked to 409 going forward.
        raise HTTPException(status_code=409, detail="challenge already solved")
    except PrerequisitesNotMet as exc:
        # 412 (Precondition Failed) signals that a state requirement
        # the client is responsible for is not met. ``detail`` is a
        # structured object so the UI can render a per-prerequisite
        # hint ("you need to solve foo, bar") instead of the generic
        # message. JS clients that fall back to ``String(detail)``
        # still see a useful summary via ``message``.
        missing = list(exc.missing_slugs)
        raise HTTPException(
            status_code=412,
            detail={
                "message": "prerequisite challenges not yet solved",
                "missing_slugs": missing,
            },
        )

    if result.correct:
        return SubmitFlagResponse(
            correct=True,
            points_awarded=result.points_awarded,
            is_first_blood=result.is_first_blood,
            flag_id=result.flag_id,
            # ``SubmissionResult`` doesn't carry the validator name in
            # the v1 shape today (Phase 8 added it on the dispatcher
            # only). Surface ``None`` explicitly so the v1 contract
            # documents the intent; a future slice can wire it
            # through end-to-end.
            validator=None,
        )
    return SubmitFlagResponse(correct=False)
