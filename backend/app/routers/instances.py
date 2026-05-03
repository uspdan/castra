from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User, Challenge, ChallengeInstance, InstanceStatus
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.audit.request_context import context_from_request
from app.services.auth import get_current_user
from app.services.orchestration import (
    MissingImageDigest,
    PostPullDigestMismatch,
    UnknownProfile,
    launch_instance,
    stop_instance,
)
from app.services.orchestration.networking import EgressProxyUnavailable

router = APIRouter(prefix="/instances", tags=["instances"])


async def get_redis():
    settings = get_settings()
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        yield r
    finally:
        await r.aclose()


def _launch_to_http(exc: Exception) -> HTTPException:
    """Translate launcher domain errors to status codes."""
    if isinstance(exc, MissingImageDigest):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, PostPullDigestMismatch):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, UnknownProfile):
        return HTTPException(status_code=409, detail=f"unknown profile: {exc}")
    if isinstance(exc, EgressProxyUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="launch failed")


@router.post("/{slug}/launch")
async def launch(
    slug: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis),
):
    result = await db.execute(
        select(Challenge).where(
            Challenge.slug == slug,
            Challenge.is_active == True,
            Challenge.is_released == True,
        )
    )
    challenge = result.scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    try:
        instance_data = await launch_instance(
            current_user.id, challenge, db, redis_client
        )
    except (MissingImageDigest, UnknownProfile, EgressProxyUnavailable, ValueError) as exc:
        # No rollback here: the per-request session is closed by the
        # ``get_db`` dependency teardown. Issuing rollback in this path
        # while a savepoint is active leaves the asyncpg greenlet adapter
        # in an inconsistent state when the same session is reused by a
        # caller (notably the integration-test harness).
        raise _launch_to_http(exc) from exc

    await audit_append(
        db,
        event_type=EventType.INSTANCE_LAUNCH,
        actor_type=ActorType.USER,
        actor_id=current_user.id,
        resource_type="instance",
        resource_id=instance_data["instance_id"],
        payload={
            "instance_id": instance_data["instance_id"],
            "challenge_slug": slug,
            "port": instance_data["port"],
            "expires_at": str(instance_data["expires_at"]),
            "profile": instance_data["profile"],
            "digest": instance_data["digest"],
        },
        **context_from_request(request),
    )
    await db.commit()

    return {
        "id": instance_data["instance_id"],
        "challenge_slug": slug,
        "status": "running",
        "port": instance_data["port"],
        "ip_address": instance_data["ip"],
        "expires_at": str(instance_data["expires_at"]),
        "profile": instance_data["profile"],
    }


@router.delete("/{instance_id}")
async def stop(
    instance_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis),
):
    result = await db.execute(
        select(ChallengeInstance).where(ChallengeInstance.id == instance_id)
    )
    instance = result.scalars().first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found.")

    if instance.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your instance.")

    try:
        await stop_instance(instance_id, db, redis_client)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await audit_append(
        db,
        event_type=EventType.INSTANCE_STOP,
        actor_type=ActorType.USER,
        actor_id=current_user.id,
        resource_type="instance",
        resource_id=instance_id,
        payload={"instance_id": instance_id, "reason": "user_request"},
        **context_from_request(request),
    )
    await db.commit()

    return {"detail": "Instance stopped.", "id": instance_id}


@router.get("/")
async def list_instances(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChallengeInstance)
        .where(
            ChallengeInstance.user_id == current_user.id,
            ChallengeInstance.status == InstanceStatus.running,
        )
        .order_by(ChallengeInstance.started_at.desc())
    )
    instances = result.scalars().all()

    items = []
    for inst in instances:
        challenge_result = await db.execute(
            select(Challenge.slug, Challenge.title).where(
                Challenge.id == inst.challenge_id
            )
        )
        ch = challenge_result.first()

        time_remaining = None
        if inst.expires_at:
            delta = inst.expires_at - datetime.now(timezone.utc)
            time_remaining = max(int(delta.total_seconds()), 0)

        items.append(
            {
                "id": inst.id,
                "challenge_slug": ch.slug if ch else None,
                "challenge_title": ch.title if ch else None,
                "status": inst.status.value if inst.status else None,
                "port": inst.assigned_port,
                "ip_address": inst.assigned_ip,
                "time_remaining_seconds": time_remaining,
                "expires_at": str(inst.expires_at) if inst.expires_at else None,
                "started_at": str(inst.started_at) if inst.started_at else None,
                "profile": inst.applied_profile,
            }
        )

    return {"instances": items}


@router.post("/{instance_id}/reset")
async def reset_instance(
    instance_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis),
):
    result = await db.execute(
        select(ChallengeInstance).where(ChallengeInstance.id == instance_id)
    )
    instance = result.scalars().first()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found.")

    if instance.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your instance.")

    challenge_result = await db.execute(
        select(Challenge).where(Challenge.id == instance.challenge_id)
    )
    challenge = challenge_result.scalars().first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found.")

    try:
        await stop_instance(instance_id, db, redis_client)
        instance_data = await launch_instance(
            current_user.id, challenge, db, redis_client
        )
    except (MissingImageDigest, UnknownProfile, EgressProxyUnavailable, ValueError) as exc:
        # No rollback here: the per-request session is closed by the
        # ``get_db`` dependency teardown. Issuing rollback in this path
        # while a savepoint is active leaves the asyncpg greenlet adapter
        # in an inconsistent state when the same session is reused by a
        # caller (notably the integration-test harness).
        raise _launch_to_http(exc) from exc

    await audit_append(
        db,
        event_type=EventType.INSTANCE_RESET,
        actor_type=ActorType.USER,
        actor_id=current_user.id,
        resource_type="instance",
        resource_id=instance_data["instance_id"],
        payload={
            "instance_id": instance_data["instance_id"],
            "previous_instance_id": instance_id,
            "challenge_slug": challenge.slug,
            "profile": instance_data["profile"],
            "digest": instance_data["digest"],
        },
        **context_from_request(request),
    )
    await db.commit()

    return {
        "id": instance_data["instance_id"],
        "challenge_slug": challenge.slug,
        "status": "running",
        "port": instance_data["port"],
        "ip_address": instance_data["ip"],
        "expires_at": str(instance_data["expires_at"]),
        "profile": instance_data["profile"],
        "detail": "Instance reset.",
    }
