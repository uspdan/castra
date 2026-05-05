"""``/api/v1/admin/*`` — locked admin write surface.

Covers the operator-facing write endpoints needed to seed and run a
deployment:

- ``POST   /api/v1/admin/challenges``           — create
- ``PUT    /api/v1/admin/challenges/{slug}``    — update
- ``POST   /api/v1/admin/challenges/{slug}/release`` — release
- ``DELETE /api/v1/admin/challenges/{slug}``    — soft-delete
- ``PUT    /api/v1/admin/users/{user_id}``      — role/team/active
- ``POST   /api/v1/admin/seed``                 — seed from /challenges

The legacy ``/admin/*`` and ``/challenges/`` admin routes stay live;
this module is the contract the migrated Playwright fixture (and any
external operator tooling) calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    Challenge,
    ChallengeFlag,
    Notification,
    Solve,
    TeamType,
    User,
    UserRole,
)
from app.schemas.v1.admin import (
    AdminChallengeCreateRequest,
    AdminChallengeDetailResponse,
    AdminChallengeFlagRequest,
    AdminChallengeFlagResponse,
    AdminChallengeResponse,
    AdminChallengeUpdateRequest,
    AdminSeedResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
)
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.audit.request_context import context_from_request
from app.services.auth import require_admin
from app.services.webhook_dispatch import deliver_event as deliver_webhook_event
from app.services.ws_manager import ws_manager
from app.validators.exact import hash_exact_value


router = APIRouter(prefix="/admin", tags=["v1-admin"])


def _to_challenge_response(c: Challenge) -> AdminChallengeResponse:
    return AdminChallengeResponse(
        id=c.id,
        slug=c.slug,
        title=c.title,
        category=c.category,
        team=c.team.value if c.team else "red",
        difficulty=c.difficulty,
        points=c.points,
        is_released=bool(c.is_released),
        is_active=bool(c.is_active),
        released_at=c.released_at,
        created_at=c.created_at,
    )


def _to_user_response(u: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=u.id,
        username=u.username,
        email=u.email,
        display_name=u.display_name or u.username,
        role=u.role.value,
        team=u.team.value if u.team else None,
        is_active=bool(u.is_active),
        created_at=u.created_at,
    )


# ---------------------------------------------------------------------------
# Challenges
# ---------------------------------------------------------------------------
@router.post(
    "/challenges",
    response_model=AdminChallengeResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Admin role required"},
        409: {"description": "Slug already exists"},
    },
)
async def create_challenge_v1(
    payload: AdminChallengeCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminChallengeResponse:
    existing = (
        await db.execute(
            select(Challenge).where(Challenge.slug == payload.slug)
        )
    ).scalars().first()
    if existing:
        raise HTTPException(
            status_code=409, detail="Challenge slug already exists"
        )

    chal = Challenge(
        slug=payload.slug,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        team=TeamType(payload.team),
        difficulty=payload.difficulty,
        points=payload.points,
        flag_hash=hash_exact_value(payload.flag),
        hints=payload.hints,
        skills=payload.skills,
        mitre_techniques=payload.mitre_techniques,
        docker_image=payload.docker_image,
        docker_port=payload.docker_port,
        docker_config=payload.docker_config,
        prerequisite_ids=payload.prerequisite_ids,
        is_released=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(chal)
    await db.commit()
    await db.refresh(chal)
    return _to_challenge_response(chal)


@router.put(
    "/challenges/{slug}",
    response_model=AdminChallengeResponse,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "Challenge not found"},
        409: {"description": "Slug already exists"},
        400: {"description": "Cannot change flag after solves exist"},
    },
)
async def update_challenge_v1(
    slug: str,
    payload: AdminChallengeUpdateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminChallengeResponse:
    chal = (
        await db.execute(select(Challenge).where(Challenge.slug == slug))
    ).scalars().first()
    if not chal:
        raise HTTPException(status_code=404, detail="Challenge not found")

    updates = payload.model_dump(exclude_unset=True)

    if "flag" in updates:
        solve_count = (
            await db.execute(
                select(func.count(Solve.id)).where(
                    Solve.challenge_id == chal.id
                )
            )
        ).scalar() or 0
        if solve_count > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot change flag after solves exist",
            )
        chal.flag_hash = hash_exact_value(updates.pop("flag"))

    new_slug = updates.pop("slug", None)
    if new_slug is not None and new_slug != slug:
        existing = (
            await db.execute(
                select(Challenge).where(Challenge.slug == new_slug)
            )
        ).scalars().first()
        if existing:
            raise HTTPException(
                status_code=409, detail="Slug already exists"
            )
        chal.slug = new_slug

    if "team" in updates and updates["team"] is not None:
        updates["team"] = TeamType(updates["team"])

    for field, value in updates.items():
        setattr(chal, field, value)

    await db.commit()
    await db.refresh(chal)
    return _to_challenge_response(chal)


@router.post(
    "/challenges/{slug}/release",
    response_model=AdminChallengeResponse,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "Challenge not found"},
    },
)
async def release_challenge_v1(
    slug: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminChallengeResponse:
    chal = (
        await db.execute(select(Challenge).where(Challenge.slug == slug))
    ).scalars().first()
    if not chal:
        raise HTTPException(status_code=404, detail="Challenge not found")

    chal.is_released = True
    chal.released_at = datetime.now(timezone.utc)

    from app.services.notifications import create_notification

    await create_notification(
        db,
        title="New Challenge Released!",
        message=(
            f"'{chal.title}' "
            f"({chal.category} - difficulty {chal.difficulty}) "
            f"is now available!"
        ),
        notification_type="release",
        is_global=True,
    )

    payload = {
        "challenge_slug": chal.slug,
        "title": chal.title,
        "category": chal.category,
        "points": chal.points,
        "difficulty": chal.difficulty,
    }
    await audit_append(
        db,
        event_type=EventType.CHALLENGE_RELEASED,
        actor_type=ActorType.USER,
        actor_id=admin.id,
        resource_type="challenge",
        resource_id=chal.slug,
        payload=payload,
        **context_from_request(request),
    )
    await deliver_webhook_event(
        db=db,
        event_type=EventType.CHALLENGE_RELEASED,
        payload=payload,
    )
    await db.commit()
    await db.refresh(chal)

    await ws_manager.broadcast(
        {
            "type": "challenge_released",
            "slug": chal.slug,
            "title": chal.title,
            "category": chal.category,
            "difficulty": chal.difficulty,
            "points": chal.points,
        }
    )

    return _to_challenge_response(chal)


@router.delete(
    "/challenges/{slug}",
    response_model=AdminChallengeResponse,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "Challenge not found"},
    },
)
async def delete_challenge_v1(
    slug: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminChallengeResponse:
    chal = (
        await db.execute(select(Challenge).where(Challenge.slug == slug))
    ).scalars().first()
    if not chal:
        raise HTTPException(status_code=404, detail="Challenge not found")

    chal.is_active = False
    await db.commit()
    await db.refresh(chal)
    return _to_challenge_response(chal)


# ---------------------------------------------------------------------------
# Admin challenge detail (Sprint 9 — populates the editor form)
# ---------------------------------------------------------------------------
@router.get(
    "/challenges/{slug}",
    response_model=AdminChallengeDetailResponse,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "Challenge not found"},
    },
)
async def get_challenge_detail_v1(
    slug: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminChallengeDetailResponse:
    """Admin-side full challenge view including docker fields.

    The public ``GET /api/v1/challenges/{slug}`` deliberately hides
    docker_image / docker_port / docker_config so competitors can't
    inspect challenge internals. The admin editor needs them.
    """

    chal = (
        await db.execute(select(Challenge).where(Challenge.slug == slug))
    ).scalars().first()
    if not chal:
        raise HTTPException(status_code=404, detail="Challenge not found")

    solve_count = (
        await db.execute(
            select(func.count(Solve.id)).where(Solve.challenge_id == chal.id)
        )
    ).scalar() or 0

    return AdminChallengeDetailResponse(
        id=chal.id,
        slug=chal.slug,
        title=chal.title,
        description=chal.description,
        category=chal.category,
        team=chal.team.value if chal.team else "red",
        difficulty=chal.difficulty,
        points=chal.points,
        docker_image=chal.docker_image,
        docker_port=chal.docker_port,
        docker_config=dict(chal.docker_config or {}),
        prerequisite_ids=list(chal.prerequisite_ids or []),
        hints=list(chal.hints or []),
        skills=list(chal.skills or []),
        mitre_techniques=list(chal.mitre_techniques or []),
        is_released=bool(chal.is_released),
        is_active=bool(chal.is_active),
        released_at=chal.released_at,
        created_at=chal.created_at,
        solve_count=int(solve_count),
    )


# ---------------------------------------------------------------------------
# Multi-flag challenge flags
# ---------------------------------------------------------------------------
@router.post(
    "/challenges/{slug}/flags",
    response_model=AdminChallengeFlagResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "Challenge not found"},
        409: {"description": "flag_id already exists on this challenge"},
    },
)
async def add_challenge_flag_v1(
    slug: str,
    payload: AdminChallengeFlagRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminChallengeFlagResponse:
    chal = (
        await db.execute(select(Challenge).where(Challenge.slug == slug))
    ).scalars().first()
    if not chal:
        raise HTTPException(status_code=404, detail="Challenge not found")

    existing = (
        await db.execute(
            select(ChallengeFlag).where(
                ChallengeFlag.challenge_id == chal.id,
                ChallengeFlag.flag_id == payload.flag_id,
            )
        )
    ).scalars().first()
    if existing:
        raise HTTPException(
            status_code=409, detail="flag_id already exists on this challenge"
        )

    value_hash = (
        hash_exact_value(payload.value)
        if payload.flag_type == "exact" and payload.value
        else None
    )

    row = ChallengeFlag(
        challenge_id=chal.id,
        flag_id=payload.flag_id,
        flag_type=payload.flag_type,
        points=payload.points,
        label=payload.label,
        value_hash=value_hash,
        config=payload.config or {},
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    # Once a multi-flag set exists, the legacy ``flag_hash`` is
    # ignored (the dispatcher prefers the v1 ``challenge_flags``
    # rows). Clear it so we don't surface a stale hash in audit
    # payloads.
    if chal.flag_hash:
        chal.flag_hash = None
        await db.commit()
        await db.refresh(chal)

    return AdminChallengeFlagResponse(
        id=row.id,
        flag_id=row.flag_id,
        flag_type=row.flag_type,
        points=row.points,
        label=row.label,
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@router.put(
    "/users/{user_id}",
    response_model=AdminUserResponse,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "User not found"},
    },
)
async def update_user_v1(
    user_id: int,
    payload: AdminUserUpdateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserResponse:
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = payload.model_dump(exclude_unset=True)
    if "role" in updates and updates["role"] is not None:
        updates["role"] = UserRole(updates["role"])
    if "team" in updates and updates["team"] is not None:
        updates["team"] = TeamType(updates["team"])

    for field, value in updates.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return _to_user_response(user)


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
@router.post(
    "/seed",
    response_model=AdminSeedResponse,
    responses={
        403: {"description": "Admin role required"},
        400: {"description": "/challenges directory not found"},
    },
)
async def seed_challenges_v1(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminSeedResponse:
    challenges_dir = Path("/challenges")
    if not challenges_dir.exists():
        raise HTTPException(
            status_code=400,
            detail="Challenges directory not found at /challenges",
        )

    created = 0
    skipped = 0
    for entry in sorted(challenges_dir.iterdir()):
        if not entry.is_dir():
            continue
        manifest = entry / "challenge.json"
        if not manifest.exists():
            continue

        with open(manifest) as f:
            data = json.load(f)

        slug = data.get("slug", entry.name)
        existing = (
            await db.execute(select(Challenge).where(Challenge.slug == slug))
        ).scalars().first()
        if existing:
            skipped += 1
            continue

        flag = data.get("flag", "")
        chal = Challenge(
            slug=slug,
            title=data.get("title", slug),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            difficulty=data.get("difficulty", 1),
            points=data.get("points", 100),
            team=TeamType(data.get("team", "red")),
            flag_hash=hash_exact_value(flag) if flag else "",
            hints=data.get("hints", []),
            skills=data.get("skills", []),
            mitre_techniques=data.get("mitre_techniques", []),
            docker_image=data.get("docker_image", "alpine:3.19"),
            docker_port=data.get("docker_port", 8080),
            docker_config=data.get("docker_config", {}),
            prerequisite_ids=data.get("prerequisite_ids", []),
            is_released=True,
            is_active=True,
            released_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(chal)
        created += 1

    await db.commit()
    return AdminSeedResponse(created=created, skipped=skipped)
