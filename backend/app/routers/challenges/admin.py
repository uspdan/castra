"""Admin CRUD endpoints for challenges: create, update, release, soft-delete."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Challenge, Notification, Solve, User
from app.schemas import ChallengeCreate, ChallengeUpdate
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.audit.request_context import context_from_request
from app.services.auth import require_admin
from app.services.webhook_dispatch import deliver_event as deliver_webhook_event
from app.validators.exact import hash_exact_value
from app.services.ws_manager import ws_manager

router = APIRouter()


@router.post("/")
async def create_challenge(
    data: ChallengeCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(select(Challenge).where(Challenge.slug == data.slug))
    ).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Challenge slug already exists.")

    challenge = Challenge(
        slug=data.slug,
        title=data.title,
        description=data.description,
        category=data.category,
        difficulty=data.difficulty,
        points=data.points,
        team=data.team,
        flag_hash=hash_exact_value(data.flag),
        hints=data.hints,
        skills=data.skills,
        mitre_techniques=data.mitre_techniques,
        docker_image=data.docker_image,
        docker_port=data.docker_port,
        docker_config=data.docker_config,
        prerequisite_ids=data.prerequisite_ids,
        is_released=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)

    return {
        "id": challenge.id,
        "slug": challenge.slug,
        "title": challenge.title,
        "detail": "Challenge created.",
    }


@router.put("/{slug}")
async def update_challenge(
    slug: str,
    data: ChallengeUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    challenge = (
        await db.execute(select(Challenge).where(Challenge.slug == slug))
    ).scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    updates = data.model_dump(exclude_unset=True)

    if "flag" in updates:
        solve_count = (
            await db.execute(
                select(func.count(Solve.id)).where(
                    Solve.challenge_id == challenge.id
                )
            )
        ).scalar()
        if solve_count > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot change flag after solves exist.",
            )
        challenge.flag_hash = hash_exact_value(updates.pop("flag"))

    new_slug = updates.pop("slug", None)
    if new_slug is not None and new_slug != slug:
        existing = (
            await db.execute(select(Challenge).where(Challenge.slug == new_slug))
        ).scalars().first()
        if existing:
            raise HTTPException(status_code=409, detail="Slug already exists.")
        challenge.slug = new_slug

    for field, value in updates.items():
        setattr(challenge, field, value)

    await db.commit()
    await db.refresh(challenge)

    return {"detail": "Challenge updated.", "slug": challenge.slug}


@router.post("/{slug}/release")
async def release_challenge(
    slug: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    challenge = (
        await db.execute(select(Challenge).where(Challenge.slug == slug))
    ).scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    challenge.is_released = True
    challenge.released_at = datetime.now(timezone.utc)

    db.add(
        Notification(
            title="New Challenge Released!",
            message=(
                f"'{challenge.title}' "
                f"({challenge.category} - {challenge.difficulty}) is now available!"
            ),
            notification_type="release",
            is_global=True,
            created_at=datetime.now(timezone.utc),
        )
    )

    # Phase 12 (slice 9): emit ``challenge.released`` to the
    # audit ledger + fan out to v1 webhook subscriptions. Replaces
    # the legacy env-var-driven notify_release Slack/Teams broadcast.
    payload = {
        "challenge_slug": challenge.slug,
        "title": challenge.title,
        "category": challenge.category,
        "points": challenge.points,
        "difficulty": challenge.difficulty,
    }
    await audit_append(
        db,
        event_type=EventType.CHALLENGE_RELEASED,
        actor_type=ActorType.USER,
        actor_id=admin.id,
        resource_type="challenge",
        resource_id=challenge.slug,
        payload=payload,
        **context_from_request(request),
    )
    await deliver_webhook_event(
        db=db,
        event_type=EventType.CHALLENGE_RELEASED,
        payload=payload,
    )
    await db.commit()

    await ws_manager.broadcast(
        {
            "type": "challenge_released",
            "slug": challenge.slug,
            "title": challenge.title,
            "category": challenge.category,
            "difficulty": challenge.difficulty,
            "points": challenge.points,
        }
    )

    return {"detail": "Challenge released.", "slug": challenge.slug}


@router.delete("/{slug}")
async def delete_challenge(
    slug: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    challenge = (
        await db.execute(select(Challenge).where(Challenge.slug == slug))
    ).scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    challenge.is_active = False
    await db.commit()
    return {"detail": "Challenge soft-deleted.", "slug": slug}
