"""``/api/v1/auth/*`` — locked auth contract.

The legacy ``/auth/*`` endpoints stay live for compatibility; this
surface is the one the migrated frontend (and any external clients)
consumes. Every response is a Pydantic model with
``ConfigDict(extra="forbid")`` so internal columns cannot leak.

Endpoints:

- ``POST /api/v1/auth/register`` — create user, return token pair.
- ``POST /api/v1/auth/login``    — authenticate, return token pair.
- ``POST /api/v1/auth/refresh``  — exchange refresh token for new access.
- ``POST /api/v1/auth/logout``   — revoke refresh token (best-effort).
- ``GET  /api/v1/auth/me``       — same shape as ``GET /api/v1/me``.

Audit-ledger emit, account lockout, and refresh-token blacklist
behaviour mirrors the legacy router (see ``app/routers/auth.py``).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import TeamType, User
from app.schemas.v1.auth import (
    AuthLoginRequest,
    AuthLogoutRequest,
    AuthLogoutResponse,
    AuthRefreshRequest,
    AuthRefreshResponse,
    AuthRegisterRequest,
    AuthTokenPairResponse,
    AuthUser,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
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


router = APIRouter(prefix="/auth", tags=["v1-auth"])


async def _get_redis():
    settings = get_settings()
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        yield r
    finally:
        await r.close()


def _to_auth_user(user: User) -> AuthUser:
    return AuthUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name or user.username,
        email=user.email,
        role=user.role.value,
        team=user.team.value if user.team else None,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.post(
    "/register",
    response_model=AuthTokenPairResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Email or username already taken"}},
)
async def register_v1(
    payload: AuthRegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenPairResponse:
    existing = await db.execute(
        select(User).where(
            (User.email == payload.email) | (User.username == payload.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="Email or username already taken"
        )

    team_value = TeamType(payload.team) if payload.team else None
    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        team=team_value,
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

    return AuthTokenPairResponse(
        user=_to_auth_user(user),
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post(
    "/login",
    response_model=AuthTokenPairResponse,
    responses={
        401: {"description": "Invalid credentials"},
        403: {"description": "Account is disabled"},
        429: {"description": "Account temporarily locked"},
    },
)
async def login_v1(
    payload: AuthLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(_get_redis),
) -> AuthTokenPairResponse:
    ctx = context_from_request(request)
    await check_account_lockout(payload.email, redis_client)

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        if user:
            await record_failed_login(payload.email, redis_client)
        await audit_append(
            db,
            event_type=EventType.AUTH_LOGIN_FAILED,
            actor_type=ActorType.USER if user else ActorType.ANONYMOUS,
            actor_id=user.id if user else None,
            resource_type="user",
            resource_id=user.id if user else None,
            payload={
                "email": payload.email,
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
            payload={"email": payload.email, "reason": "account_disabled"},
            **ctx,
        )
        await db.commit()
        raise HTTPException(status_code=403, detail="Account is disabled")

    await clear_failed_logins(payload.email, redis_client)
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

    return AuthTokenPairResponse(
        user=_to_auth_user(user),
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post(
    "/refresh",
    response_model=AuthRefreshResponse,
    responses={401: {"description": "Invalid or revoked refresh token"}},
)
async def refresh_v1(
    payload: AuthRefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(_get_redis),
) -> AuthRefreshResponse:
    token = payload.refresh_token

    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
    if blacklisted:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    try:
        decoded = decode_token(token)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    try:
        user_id = int(decoded["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

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
    return AuthRefreshResponse(access_token=new_access)


@router.post("/logout", response_model=AuthLogoutResponse)
async def logout_v1(
    payload: AuthLogoutRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(_get_redis),
) -> AuthLogoutResponse:
    token = payload.refresh_token
    actor_id: int | None = None
    if token:
        try:
            decoded = decode_token(token)
            exp = decoded.get("exp", 0)
            ttl = max(int(exp - time.time()), 0)
            if ttl > 0:
                await redis_client.set(
                    f"siege:blacklist:{token}", "1", ex=ttl
                )
            sub = decoded.get("sub")
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
    return AuthLogoutResponse(message="Logged out")


@router.get("/me", response_model=AuthUser)
async def me_v1(
    current_user: User = Depends(get_current_user),
) -> AuthUser:
    return _to_auth_user(current_user)


# ---------------------------------------------------------------------------
# Password reset (Sprint 6)
# ---------------------------------------------------------------------------
@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={429: {"description": "Too many reset requests"}},
)
async def forgot_password_v1(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """Issue a password-reset token and email the link.

    Always returns 202 with a generic message regardless of whether
    the email matches a real account — leaking that information
    enables enumeration. The actual delivery happens only on a
    real match.
    """

    from app.services.audit import (
        ActorType,
        EventType,
        append as audit_append,
    )
    from app.services.audit.request_context import context_from_request
    from app.services.email import send_email
    from app.services.password_reset import issue_token

    ctx = context_from_request(request)
    settings = get_settings()

    user = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()

    if user is not None and user.is_active:
        cleartext = await issue_token(db, user)
        link = (
            f"{settings.frontend_url()}/reset-password"
            f"?token={cleartext}"
        )
        body = (
            f"Hi {user.display_name or user.username},\n\n"
            f"Someone (hopefully you) requested a password reset on "
            f"siege-range. Click the link below to set a new password "
            f"— it expires in "
            f"{settings.PASSWORD_RESET_TTL_MINUTES} minutes.\n\n"
            f"{link}\n\n"
            f"If you didn't request this, you can safely ignore this "
            f"email.\n"
        )
        await send_email(
            to=user.email,
            subject="Reset your siege-range password",
            body_text=body,
        )
        await audit_append(
            db,
            event_type=EventType.AUTH_PASSWORD_RESET_REQUEST,
            actor_type=ActorType.USER,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            payload={"email": payload.email},
            **ctx,
        )
    else:
        # Audit even the no-match case so log analysis can spot
        # enumeration attempts (high-frequency requests for
        # nonexistent emails from the same IP).
        await audit_append(
            db,
            event_type=EventType.AUTH_PASSWORD_RESET_REQUEST,
            actor_type=ActorType.ANONYMOUS,
            actor_id=None,
            resource_type=None,
            resource_id=None,
            payload={
                "email": payload.email,
                "matched": False,
            },
            **ctx,
        )

    await db.commit()
    return ForgotPasswordResponse(
        message=(
            "If an account with that email exists, a password "
            "reset link has been sent."
        )
    )


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    responses={400: {"description": "Invalid or expired reset token"}},
)
async def reset_password_v1(
    payload: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    """Redeem a reset token and set a new password."""

    from app.services.audit import (
        ActorType,
        EventType,
        append as audit_append,
    )
    from app.services.audit.request_context import context_from_request
    from app.services.password_reset import (
        InvalidResetToken,
        redeem_token,
    )

    try:
        user = await redeem_token(db, payload.token, payload.new_password)
    except InvalidResetToken as exc:
        # Audit the failure with the reason; client gets a generic
        # 400 so the failure mode isn't enumerable.
        await audit_append(
            db,
            event_type=EventType.AUTH_PASSWORD_RESET_REDEEM,
            actor_type=ActorType.ANONYMOUS,
            actor_id=None,
            resource_type=None,
            resource_id=None,
            payload={"matched": False, "reason": str(exc)},
            **context_from_request(request),
        )
        await db.commit()
        raise HTTPException(
            status_code=400, detail="invalid or expired token"
        )

    await audit_append(
        db,
        event_type=EventType.AUTH_PASSWORD_RESET_REDEEM,
        actor_type=ActorType.USER,
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"matched": True},
        **context_from_request(request),
    )
    await db.commit()
    return ResetPasswordResponse(message="Password reset successful.")
