"""``/api/v1/me`` — current-user surface (read, GDPR export, delete).

Three endpoints:
- ``GET    /api/v1/me``      — locked profile + totals + rank
- ``GET    /api/v1/me/data`` — GDPR export (Article 15)
- ``DELETE /api/v1/me``      — GDPR right-to-be-forgotten (Article 17)
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    AuditLedger,
    ChallengeInstance,
    HintUnlock,
    PasswordResetToken,
    Solve,
    SolvedFlag,
    User,
    Writeup,
)
from app.schemas.v1.auth import AccountDeleteRequest, AccountDeleteResponse
from app.schemas.v1.me import MeResponse
from app.services.api_v1 import viewer_rank
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.audit.request_context import context_from_request
from app.services.auth import (
    get_current_user,
    hash_password,
    verify_password,
)


router = APIRouter()


# ---------------------------------------------------------------------------
# GET /api/v1/me
# ---------------------------------------------------------------------------
@router.get("/me", response_model=MeResponse)
async def me_v1(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    total_points, total_solves, current_streak, rank = await viewer_rank(
        db, viewer_id=current_user.id
    )
    rank_field = rank if total_points > 0 or total_solves > 0 else None
    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name or current_user.username,
        email=current_user.email,
        role=current_user.role.value,
        team=current_user.team.value if current_user.team else None,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        total_points=total_points,
        total_solves=total_solves,
        current_streak=current_streak,
        rank=rank_field,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/me/data — GDPR export
# ---------------------------------------------------------------------------
def _row_dict(row, exclude=()):
    """Convert an ORM row to a JSON-friendly dict."""

    out = {}
    for c in row.__table__.columns:
        if c.name in exclude:
            continue
        v = getattr(row, c.name)
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        elif hasattr(v, "value") and hasattr(type(v), "_member_map_"):
            v = v.value
        out[c.name] = v
    return out


@router.get("/me/data")
async def export_my_data_v1(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export every record we hold about the current user.

    Sections:
      - ``profile``: User row (no hashed_password)
      - ``solves``: every Solve row
      - ``solved_flags``: per-flag attribution
      - ``instances``: ChallengeInstance history
      - ``writeups``: incl. unapproved
      - ``hint_unlocks``: hint usage records
      - ``audit``: audit-ledger rows where actor_id == user.id

    Sufficient for GDPR Article 15. Data not derived from the user
    (challenge catalogue, leaderboard) is excluded.
    """

    profile = _row_dict(current_user, exclude=("hashed_password",))

    solves = (
        await db.execute(select(Solve).where(Solve.user_id == current_user.id))
    ).scalars().all()
    solved_flags = (
        await db.execute(
            select(SolvedFlag).where(SolvedFlag.user_id == current_user.id)
        )
    ).scalars().all()
    instances = (
        await db.execute(
            select(ChallengeInstance).where(
                ChallengeInstance.user_id == current_user.id
            )
        )
    ).scalars().all()
    writeups = (
        await db.execute(
            select(Writeup).where(Writeup.user_id == current_user.id)
        )
    ).scalars().all()
    hint_unlocks = (
        await db.execute(
            select(HintUnlock).where(HintUnlock.user_id == current_user.id)
        )
    ).scalars().all()
    audit_rows = (
        await db.execute(
            select(AuditLedger).where(
                AuditLedger.actor_type == "user",
                AuditLedger.actor_id == str(current_user.id),
            )
        )
    ).scalars().all()

    await audit_append(
        db,
        event_type=EventType.AUTH_DATA_EXPORT,
        actor_type=ActorType.USER,
        actor_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        payload={
            "row_counts": {
                "solves": len(solves),
                "solved_flags": len(solved_flags),
                "instances": len(instances),
                "writeups": len(writeups),
                "hint_unlocks": len(hint_unlocks),
                "audit": len(audit_rows),
            }
        },
        **context_from_request(request),
    )
    await db.commit()

    return {
        "profile": profile,
        "solves": [_row_dict(r) for r in solves],
        "solved_flags": [_row_dict(r) for r in solved_flags],
        "instances": [_row_dict(r) for r in instances],
        "writeups": [_row_dict(r) for r in writeups],
        "hint_unlocks": [_row_dict(r) for r in hint_unlocks],
        "audit": [_row_dict(r) for r in audit_rows],
    }


# ---------------------------------------------------------------------------
# DELETE /api/v1/me — GDPR right-to-be-forgotten
# ---------------------------------------------------------------------------
@router.delete("/me", response_model=AccountDeleteResponse)
async def delete_my_account_v1(
    payload: AccountDeleteRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccountDeleteResponse:
    """Anonymise the account + revoke pending sessions.

    The user row is anonymised in place (NOT hard-deleted) because:
    - The audit ledger is immutable per CLAUDE.md §4.2.
    - ``challenge_instances`` and ``solves`` carry FKs to user_id
      we don't want to cascade-delete (those rows are platform-
      aggregate data, not user-identifying once detached).

    After this call:
    - email   → ``deleted-{user_id}@deleted.local``
    - username → ``deleted_{user_id}``
    - display_name → ``deleted user``
    - hashed_password → unguessable random hash (login disabled)
    - is_active → False
    - team / last_login → NULL

    Pending password-reset tokens for the user are deleted.

    Requires the current password in the body to defend against
    drive-by deletes via stolen access tokens.
    """

    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="password incorrect")

    user_id = current_user.id
    current_user.email = f"deleted-{user_id}@deleted.local"
    current_user.username = f"deleted_{user_id}"
    current_user.display_name = "deleted user"
    current_user.hashed_password = hash_password(secrets.token_hex(32))
    current_user.is_active = False
    current_user.team = None
    current_user.last_login = None

    await db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id
        )
    )

    await audit_append(
        db,
        event_type=EventType.AUTH_ACCOUNT_DELETE,
        actor_type=ActorType.USER,
        actor_id=user_id,
        resource_type="user",
        resource_id=user_id,
        payload={"anonymised": True},
        **context_from_request(request),
    )
    await db.commit()

    return AccountDeleteResponse(message="Account deleted.")
