import time
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Solve, Streak, User
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.audit.request_context import context_from_request
from app.services.auth import (
    check_account_lockout,
    clear_failed_logins,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    record_failed_login,
    verify_password,
)
from app.middleware.rate_limit import auth_rate_limit
from app.schemas.auth import AccessTokenResponse, LogoutRequest, RefreshTokenRequest
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])


async def get_redis():
    settings = get_settings()
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        yield r
    finally:
        await r.close()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    email = data.email
    username = data.username
    password = data.password
    display_name = data.display_name or username
    team = data.team

    existing = await db.execute(
        select(User).where((User.email == email) | (User.username == username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email or username already taken")

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        display_name=display_name,
        team=team,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    await audit_append(
        db,
        event_type=EventType.AUTH_REGISTER,
        actor_type=ActorType.USER,
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        payload={
            "username": user.username,
            "team": user.team.value if user.team else None,
        },
        **context_from_request(request),
    )
    await db.commit()

    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id)

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "team": user.team.value if user.team else None,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@router.post("/login")
async def login(
    data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis),
):
    email = data.email
    password = data.password
    ctx = context_from_request(request)

    await check_account_lockout(email, redis_client)

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        if user:
            await record_failed_login(email, redis_client)
        await audit_append(
            db,
            event_type=EventType.AUTH_LOGIN_FAILED,
            actor_type=ActorType.USER if user else ActorType.ANONYMOUS,
            actor_id=user.id if user else None,
            resource_type="user",
            resource_id=user.id if user else None,
            payload={
                "email": email,
                "reason": "bad_password" if user else "unknown_user",
            },
            **ctx,
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        await audit_append(
            db,
            event_type=EventType.AUTH_LOGIN_FAILED,
            actor_type=ActorType.USER,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            payload={"email": email, "reason": "account_disabled"},
            **ctx,
        )
        await db.commit()
        raise HTTPException(status_code=403, detail="Account is disabled")

    await clear_failed_logins(email, redis_client)
    user.last_login = datetime.now(timezone.utc)
    await audit_append(
        db,
        event_type=EventType.AUTH_LOGIN_SUCCESS,
        actor_type=ActorType.USER,
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"username": user.username},
        **ctx,
    )
    await db.commit()

    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id)

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "team": user.team.value if user.team else None,
            "role": user.role.value,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    data: RefreshTokenRequest,
    request: Request,
    redis_client=Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    token = data.refresh_token

    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
    if blacklisted:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    new_access = create_access_token(user.id, user.role.value)
    await audit_append(
        db,
        event_type=EventType.AUTH_REFRESH,
        actor_type=ActorType.USER,
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"username": user.username},
        **context_from_request(request),
    )
    await db.commit()
    return {"access_token": new_access, "token_type": "bearer"}


@router.post("/logout", response_model=MessageResponse)
async def logout(
    data: LogoutRequest,
    request: Request,
    redis_client=Depends(get_redis),
    db: AsyncSession = Depends(get_db),
):
    token = data.refresh_token
    actor_id: int | None = None
    if token:
        try:
            payload = decode_token(token)
            exp = payload.get("exp", 0)
            ttl = max(int(exp - time.time()), 0)
            if ttl > 0:
                await redis_client.set(f"siege:blacklist:{token}", "1", ex=ttl)
            sub = payload.get("sub")
            if sub is not None:
                try:
                    actor_id = int(sub)
                except (TypeError, ValueError):
                    actor_id = None
        except Exception:
            pass
    await audit_append(
        db,
        event_type=EventType.AUTH_LOGOUT,
        actor_type=ActorType.USER if actor_id is not None else ActorType.ANONYMOUS,
        actor_id=actor_id,
        resource_type="user" if actor_id is not None else None,
        resource_id=actor_id,
        payload={"token_revoked": bool(token)},
        **context_from_request(request),
    )
    await db.commit()
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    points_result = await db.execute(
        select(func.coalesce(func.sum(Solve.points_awarded), 0)).where(Solve.user_id == current_user.id)
    )
    total_points = points_result.scalar()

    solves_result = await db.execute(
        select(func.count(Solve.id)).where(Solve.user_id == current_user.id)
    )
    total_solves = solves_result.scalar()

    streak_result = await db.execute(select(Streak).where(Streak.user_id == current_user.id))
    streak = streak_result.scalar_one_or_none()

    rank_subquery = (
        select(Solve.user_id, func.coalesce(func.sum(Solve.points_awarded), 0).label("pts"))
        .group_by(Solve.user_id)
        .subquery()
    )
    rank_result = await db.execute(
        select(func.count(rank_subquery.c.user_id) + 1).where(rank_subquery.c.pts > total_points)
    )
    rank = rank_result.scalar()

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "display_name": current_user.display_name,
        "team": current_user.team.value if current_user.team else None,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat(),
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "total_points": total_points,
        "total_solves": total_solves,
        "current_streak": streak.current_streak if streak else 0,
        "rank": rank,
    }
