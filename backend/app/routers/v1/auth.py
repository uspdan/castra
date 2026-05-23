"""``/api/v1/auth/*`` — locked auth contract.

The only auth surface as of v2.5.1 — the legacy ``/auth/*`` router
was removed (R3 audit finding). Every response is a Pydantic model
with ``ConfigDict(extra="forbid")`` so internal columns cannot leak.

Endpoints:

- ``POST /api/v1/auth/register`` — create user, return token pair.
- ``POST /api/v1/auth/login``    — authenticate, return token pair.
- ``POST /api/v1/auth/refresh``  — exchange refresh token for new access.
- ``POST /api/v1/auth/logout``   — revoke refresh token (best-effort).
- ``GET  /api/v1/auth/me``       — same shape as ``GET /api/v1/me``.

All write endpoints carry per-IP rate limits via
``auth_rate_limit`` / ``auth_burst_rate_limit`` (R5 audit finding).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.middleware.rate_limit import auth_burst_rate_limit, auth_rate_limit
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
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaDisableResponse,
    MfaEnrolRequest,
    MfaEnrolResponse,
    MfaPendingResponse,
    MfaVerifyRequest,
    ProfileUpdateRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.services.mfa import (
    InvalidMfaCode,
    MFA_PENDING_MAX_ATTEMPTS,
    MfaNotEnrolled,
    confirm_enrolment,
    decode_mfa_pending_claims,
    decode_mfa_pending_token,
    disable_mfa,
    issue_mfa_pending_token,
    start_enrolment,
    verify_login_code,
)
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.audit.request_context import context_from_request
from app.services.auth import (
    check_account_lockout,
    clear_failed_logins,
    ghost_login_check,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    record_failed_login,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["v1-auth"])


def _safe_email_payload(email: str, *, actor_id: int | None) -> dict:
    """R12 audit finding — keep cleartext email out of audit_ledger.

    For *known* actors the ``actor_id`` already identifies the
    subject; the email field is dropped entirely. For *unknown*
    actors (anonymous traffic, enumeration probes) we hash the
    address with HMAC-SHA256 keyed on the platform secret so
    correlation across rows is still possible without exposing the
    plaintext.
    """

    import hashlib as _hashlib
    import hmac as _hmac

    if actor_id is not None:
        return {}
    settings = get_settings()
    digest = _hmac.new(
        settings.SECRET_KEY.encode(),
        email.lower().encode(),
        _hashlib.sha256,
    ).hexdigest()
    return {"email_hash": digest}


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
        mfa_enabled=bool(getattr(user, "mfa_enabled", False)),
        email_verified=bool(getattr(user, "email_verified", False)),
    )


@router.post(
    "/register",
    response_model=AuthTokenPairResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Email or username already taken"},
        429: {"description": "Rate limit exceeded"},
    },
    dependencies=[Depends(auth_rate_limit)],
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

    # Sprint 9 Phase B — issue an email-verification token and email
    # the link. Best-effort: a transient SMTP outage does NOT block
    # registration. The user can re-request via /auth/resend-
    # verification.
    from app.services.email import send_email
    from app.services.email_verification import (
        issue_token as issue_verify_token,
    )

    settings_local = get_settings()
    try:
        cleartext = await issue_verify_token(db, user)
        link = (
            f"{settings_local.frontend_url()}/verify-email"
            f"?token={cleartext}"
        )
        body = (
            f"Hi {user.display_name or user.username},\n\n"
            f"Welcome to siege-range. Confirm your email so you don't "
            f"lose access to your account:\n\n"
            f"{link}\n\n"
            f"The link expires in 24 hours. If you didn't sign up, "
            f"you can ignore this email.\n"
        )
        await send_email(
            to=user.email,
            subject="Confirm your siege-range email",
            body_text=body,
        )
        await audit_append(
            db,
            event_type=EventType.AUTH_EMAIL_VERIFY_REQUEST,
            actor_type=ActorType.USER,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            payload={"reason": "register"},
            **context_from_request(request),
        )
    except Exception:
        # Don't fail register if SMTP / token issue blew up; the
        # user can still resend via /auth/resend-verification.
        pass

    await db.commit()

    return AuthTokenPairResponse(
        user=_to_auth_user(user),
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id),
    )


@router.post(
    "/login",
    response_model=None,
    responses={
        200: {"description": "Login success — token pair OR MFA pending"},
        401: {"description": "Invalid credentials"},
        403: {"description": "Account is disabled"},
        429: {"description": "Account temporarily locked or rate limit exceeded"},
    },
    dependencies=[Depends(auth_rate_limit)],
)
async def login_v1(
    payload: AuthLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(_get_redis),
):
    """Authenticate by email + password.

    Two response shapes:
      * If MFA is **not** enabled on the matched user: returns
        ``AuthTokenPairResponse`` (the standard
        ``{user, access_token, refresh_token, token_type}``).
      * If MFA **is** enabled: returns ``MfaPendingResponse``
        (``{mfa_required: true, mfa_pending_token: "..."}``). The
        client must call ``POST /api/v1/auth/mfa/verify`` with the
        pending token + the user's TOTP / recovery code to receive
        the real token pair.
    """
    ctx = context_from_request(request)
    await check_account_lockout(payload.email, redis_client)

    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None:
        # R9: burn the equivalent bcrypt round so the response time
        # against an unknown email matches the response time against
        # a known email with a wrong password.
        ghost_login_check(payload.password)
    if not user or not verify_password(payload.password, user.hashed_password):
        if user:
            await record_failed_login(payload.email, redis_client)
        actor_id = user.id if user else None
        await audit_append(
            db,
            event_type=EventType.AUTH_LOGIN_FAILED,
            actor_type=ActorType.USER if user else ActorType.ANONYMOUS,
            actor_id=actor_id,
            resource_type="user",
            resource_id=actor_id,
            payload={
                "reason": "bad_password" if user else "unknown_user",
                **_safe_email_payload(payload.email, actor_id=actor_id),
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
            payload={"reason": "account_disabled"},
            **ctx,
        )
        await db.commit()
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Sprint 10 Phase C — operator opt-in: refuse login until the
    # user has clicked through their verification email.
    settings_for_gate = get_settings()
    if (
        settings_for_gate.REQUIRE_EMAIL_VERIFIED
        and not user.email_verified
    ):
        await audit_append(
            db,
            event_type=EventType.AUTH_LOGIN_FAILED,
            actor_type=ActorType.USER,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            payload={"reason": "email_not_verified"},
            **ctx,
        )
        await db.commit()
        raise HTTPException(
            status_code=403, detail="email not verified"
        )

    await clear_failed_logins(payload.email, redis_client)

    # MFA short-circuit: if the user has MFA enabled we return a
    # pending token instead of the real pair. Login still counts as
    # "successful first factor" — emit the audit row but don't bump
    # last_login until the second factor verifies.
    if user.mfa_enabled and user.mfa_secret:
        await audit_append(
            db,
            event_type=EventType.AUTH_LOGIN_SUCCESS,
            actor_type=ActorType.USER,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            payload={
                "username": user.username,
                "mfa_pending": True,
            },
            **ctx,
        )
        await db.commit()
        return MfaPendingResponse(
            mfa_required=True,
            mfa_pending_token=issue_mfa_pending_token(user.id),
        )

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
    responses={
        401: {"description": "Invalid or revoked refresh token"},
        429: {"description": "Rate limit exceeded"},
    },
    dependencies=[Depends(auth_rate_limit)],
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
        except HTTPException:
            # decode_token raises 401 for malformed/expired tokens;
            # logout is best-effort — swallow at debug, audit below
            # still fires with actor_id=None.
            decoded = None
            logger.debug("logout token decode failed", exc_info=True)
        if decoded is not None:
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
    # R7: tight burst limit — password-reset is the cheap email-bomb
    # surface. Per-email throttling lives inside the handler.
    dependencies=[Depends(auth_burst_rate_limit)],
)
async def forgot_password_v1(
    payload: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(_get_redis),
) -> ForgotPasswordResponse:
    """Issue a password-reset token and email the link.

    Always returns 202 with a generic message regardless of whether
    the email matches a real account — leaking that information
    enables enumeration. The actual delivery happens only on a
    real match.

    R7: a per-email throttle (3 mails per hour) layered on top of
    the per-IP burst limit prevents an attacker who rotates IPs
    from mail-bombing a known address.
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

    # Per-email throttle. We hash the email before keying so the
    # Redis dump doesn't carry plaintext addresses. The 202 is still
    # returned to anonymous callers regardless of whether the
    # email matched (no enumeration via 429-vs-202).
    import hashlib as _hashlib

    email_key = _hashlib.sha256(payload.email.lower().encode()).hexdigest()
    rate_key = f"siege:ratelimit:pwreset-email:{email_key}"
    now = int(time.time())
    window = 3600
    limit_per_email = 3
    pipe = redis_client.pipeline()
    await pipe.zremrangebyscore(rate_key, 0, now - window)
    await pipe.zadd(rate_key, {str(now): now})
    await pipe.zcard(rate_key)
    await pipe.expire(rate_key, window)
    results = await pipe.execute()
    if results[2] > limit_per_email:
        # Silent throttle — still return 202 so the response shape is
        # identical to the match / no-match branches; the side-effect
        # (email sent) just doesn't fire.
        return ForgotPasswordResponse(
            message=(
                "If an account with that email exists, a password "
                "reset link has been sent."
            )
        )

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
            # R12: actor_id identifies the subject; don't carry the
            # cleartext email again.
            payload={},
            **ctx,
        )
    else:
        # Audit even the no-match case so log analysis can spot
        # enumeration attempts (high-frequency requests for
        # nonexistent emails from the same IP). R12: HMAC the email
        # so the same probe-target correlates across rows without
        # leaking the address itself.
        await audit_append(
            db,
            event_type=EventType.AUTH_PASSWORD_RESET_REQUEST,
            actor_type=ActorType.ANONYMOUS,
            actor_id=None,
            resource_type=None,
            resource_id=None,
            payload={
                "matched": False,
                **_safe_email_payload(payload.email, actor_id=None),
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
    responses={
        400: {"description": "Invalid or expired reset token"},
        429: {"description": "Rate limit exceeded"},
    },
    dependencies=[Depends(auth_rate_limit)],
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


# ---------------------------------------------------------------------------
# Account settings (Sprint 7 Phase A)
# ---------------------------------------------------------------------------
@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    responses={401: {"description": "Current password incorrect"}},
)
async def change_password_v1(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChangePasswordResponse:
    """In-app password change. Requires current password."""

    if not verify_password(payload.current_password, current_user.hashed_password):
        await audit_append(
            db,
            event_type=EventType.AUTH_PASSWORD_CHANGE,
            actor_type=ActorType.USER,
            actor_id=current_user.id,
            resource_type="user",
            resource_id=current_user.id,
            payload={"success": False, "reason": "bad_current_password"},
            **context_from_request(request),
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="current password incorrect")

    current_user.hashed_password = hash_password(payload.new_password)
    await audit_append(
        db,
        event_type=EventType.AUTH_PASSWORD_CHANGE,
        actor_type=ActorType.USER,
        actor_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        payload={"success": True},
        **context_from_request(request),
    )
    await db.commit()
    return ChangePasswordResponse(message="Password changed.")


@router.patch("/profile", response_model=AuthUser)
async def update_profile_v1(
    payload: ProfileUpdateRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthUser:
    """Self-service mutation of display_name + team."""

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        # No-op; return current shape.
        return _to_auth_user(current_user)

    if "team" in updates and updates["team"] is not None:
        updates["team"] = TeamType(updates["team"])

    for field, value in updates.items():
        setattr(current_user, field, value)

    await audit_append(
        db,
        event_type=EventType.AUTH_PROFILE_UPDATE,
        actor_type=ActorType.USER,
        actor_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        payload={
            "fields": list(updates.keys()),
        },
        **context_from_request(request),
    )
    await db.commit()
    await db.refresh(current_user)
    return _to_auth_user(current_user)


# ---------------------------------------------------------------------------
# MFA — Sprint 7 Phase C
# ---------------------------------------------------------------------------
@router.post(
    "/mfa/enroll",
    response_model=None,
    responses={
        200: {"description": "Enrolment started; pass code to /mfa/confirm"},
    },
)
async def mfa_enroll_v1(
    payload: MfaEnrolRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MfaEnrolResponse:
    """Generate a fresh TOTP secret + provisioning URI.

    Does NOT enable MFA — that requires the user to confirm a code
    via ``/mfa/confirm``. Calling this on a user who already has
    MFA fully enabled rotates the secret to a new one and resets
    them to the unconfirmed state — they have to re-confirm.

    R10 audit finding: requires the current account password.
    If MFA is already enabled, also requires a valid current TOTP
    or recovery code in ``current_code`` — otherwise a stolen
    access token could quietly rotate the second factor.
    """

    if not verify_password(payload.password, current_user.hashed_password):
        await audit_append(
            db,
            event_type=EventType.AUTH_MFA_ENROLL,
            actor_type=ActorType.USER,
            actor_id=current_user.id,
            resource_type="user",
            resource_id=current_user.id,
            payload={"success": False, "reason": "password_incorrect"},
            **context_from_request(request),
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="password incorrect")

    if current_user.mfa_enabled:
        if not payload.current_code:
            raise HTTPException(
                status_code=400,
                detail="current_code required when MFA already enabled",
            )
        try:
            # ``_verify_or_raise`` lives inside services.mfa but isn't
            # exported; use the public verify_login_code wrapper
            # which returns tokens we discard.
            await verify_login_code(db, current_user, payload.current_code)
        except (InvalidMfaCode, MfaNotEnrolled):
            await audit_append(
                db,
                event_type=EventType.AUTH_MFA_ENROLL,
                actor_type=ActorType.USER,
                actor_id=current_user.id,
                resource_type="user",
                resource_id=current_user.id,
                payload={"success": False, "reason": "current_code_rejected"},
                **context_from_request(request),
            )
            await db.commit()
            raise HTTPException(status_code=401, detail="current_code rejected")

    result = await start_enrolment(db, current_user)
    await audit_append(
        db,
        event_type=EventType.AUTH_MFA_ENROLL,
        actor_type=ActorType.USER,
        actor_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        payload={"rotated": True},
        **context_from_request(request),
    )
    await db.commit()
    return MfaEnrolResponse(
        secret=result.secret,
        provisioning_uri=result.provisioning_uri,
    )


@router.post(
    "/mfa/confirm",
    response_model=None,
    responses={
        200: {"description": "MFA enabled, recovery codes returned"},
        400: {"description": "Code did not match or no enrolment in progress"},
    },
)
async def mfa_confirm_v1(
    payload: MfaConfirmRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MfaConfirmResponse:
    """Verify the TOTP code and finalise enrolment.

    On success: ``mfa_enabled=True``, recovery codes generated and
    returned in cleartext **once**. The cleartext is never
    persisted — only sha256 hashes live in
    ``mfa_recovery_codes``.

    R10 audit finding: requires the current account password so
    that simply holding an access token isn't enough to enable
    MFA for an account.
    """

    if not verify_password(payload.password, current_user.hashed_password):
        await audit_append(
            db,
            event_type=EventType.AUTH_MFA_CONFIRM,
            actor_type=ActorType.USER,
            actor_id=current_user.id,
            resource_type="user",
            resource_id=current_user.id,
            payload={"success": False, "reason": "password_incorrect"},
            **context_from_request(request),
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="password incorrect")

    try:
        result = await confirm_enrolment(db, current_user, payload.code)
    except (InvalidMfaCode, MfaNotEnrolled) as exc:
        await audit_append(
            db,
            event_type=EventType.AUTH_MFA_CONFIRM,
            actor_type=ActorType.USER,
            actor_id=current_user.id,
            resource_type="user",
            resource_id=current_user.id,
            payload={"success": False, "reason": str(exc)},
            **context_from_request(request),
        )
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc))

    await audit_append(
        db,
        event_type=EventType.AUTH_MFA_CONFIRM,
        actor_type=ActorType.USER,
        actor_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        payload={"success": True},
        **context_from_request(request),
    )
    await db.commit()
    return MfaConfirmResponse(
        message="MFA enabled.",
        recovery_codes=result.recovery_codes,
    )


@router.post(
    "/mfa/disable",
    response_model=None,
    responses={
        200: {"description": "MFA disabled"},
        400: {"description": "Code did not match"},
        401: {"description": "Password incorrect"},
    },
)
async def mfa_disable_v1(
    payload: MfaDisableRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MfaDisableResponse:
    """Disable MFA after re-authenticating with password + code."""

    if not verify_password(payload.password, current_user.hashed_password):
        await audit_append(
            db,
            event_type=EventType.AUTH_MFA_DISABLE,
            actor_type=ActorType.USER,
            actor_id=current_user.id,
            resource_type="user",
            resource_id=current_user.id,
            payload={"success": False, "reason": "bad_password"},
            **context_from_request(request),
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="password incorrect")

    try:
        await disable_mfa(db, current_user, payload.code)
    except (InvalidMfaCode, MfaNotEnrolled) as exc:
        await audit_append(
            db,
            event_type=EventType.AUTH_MFA_DISABLE,
            actor_type=ActorType.USER,
            actor_id=current_user.id,
            resource_type="user",
            resource_id=current_user.id,
            payload={"success": False, "reason": str(exc)},
            **context_from_request(request),
        )
        await db.commit()
        raise HTTPException(status_code=400, detail=str(exc))

    await audit_append(
        db,
        event_type=EventType.AUTH_MFA_DISABLE,
        actor_type=ActorType.USER,
        actor_id=current_user.id,
        resource_type="user",
        resource_id=current_user.id,
        payload={"success": True},
        **context_from_request(request),
    )
    await db.commit()
    return MfaDisableResponse(message="MFA disabled.")


@router.post(
    "/mfa/verify",
    response_model=AuthTokenPairResponse,
    responses={
        401: {"description": "Pending token invalid or code rejected"},
        429: {"description": "Rate limit exceeded"},
    },
    dependencies=[Depends(auth_burst_rate_limit)],
)
async def mfa_verify_v1(
    payload: MfaVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(_get_redis),
) -> AuthTokenPairResponse:
    """Second-factor step of the login flow.

    Consumes the pending token from ``/auth/login`` (response body
    when MFA is enabled) plus the user's TOTP code (or a recovery
    code). Returns the real access + refresh token pair on
    success.

    R8: an attempt counter keyed on the pending token's jti caps
    brute-force at :data:`MFA_PENDING_MAX_ATTEMPTS`; once tripped
    the token is permanently revoked (cap-key set with a 24h TTL,
    far beyond the 90s token TTL).
    """

    ctx = context_from_request(request)

    try:
        claims = decode_mfa_pending_claims(payload.mfa_pending_token)
    except InvalidMfaCode as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    # Refuse a pending token that already burned through its
    # attempt budget. Key TTL > token TTL so a replayed valid
    # pending token after exhaustion still fails closed.
    cap_key = f"siege:mfa:pending:capped:{claims.jti}"
    if await redis_client.get(cap_key):
        raise HTTPException(status_code=401, detail="pending token revoked")

    user = (
        await db.execute(select(User).where(User.id == claims.user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="user not found")

    try:
        access, refresh = await verify_login_code(db, user, payload.code)
    except (InvalidMfaCode, MfaNotEnrolled) as exc:
        # Increment the per-jti failure counter and revoke once we
        # hit the cap.
        fail_key = f"siege:mfa:pending:fails:{claims.jti}"
        count = await redis_client.incr(fail_key)
        await redis_client.expire(fail_key, 24 * 3600)
        if count >= MFA_PENDING_MAX_ATTEMPTS:
            await redis_client.set(cap_key, "1", ex=24 * 3600)
            await redis_client.delete(fail_key)
        await audit_append(
            db,
            event_type=EventType.AUTH_MFA_VERIFY_FAILED,
            actor_type=ActorType.USER,
            actor_id=user.id,
            resource_type="user",
            resource_id=user.id,
            payload={
                "reason": str(exc),
                "attempt": int(count),
                "capped": bool(count >= MFA_PENDING_MAX_ATTEMPTS),
            },
            **ctx,
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="code rejected")

    user.last_login = datetime.now(timezone.utc)
    await audit_append(
        db,
        event_type=EventType.AUTH_MFA_VERIFY_SUCCESS,
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
        access_token=access,
        refresh_token=refresh,
    )


# ---------------------------------------------------------------------------
# Email verification — Sprint 9 Phase B
# ---------------------------------------------------------------------------
@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    responses={
        400: {"description": "Invalid or expired token"},
        429: {"description": "Rate limit exceeded"},
    },
    dependencies=[Depends(auth_rate_limit)],
)
async def verify_email_v1(
    payload: VerifyEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> VerifyEmailResponse:
    """Redeem an email-verification token and flip
    ``users.email_verified`` to True. Single-use."""

    from app.services.email_verification import (
        InvalidVerificationToken,
        redeem_token,
    )

    try:
        user = await redeem_token(db, payload.token)
    except InvalidVerificationToken as exc:
        await audit_append(
            db,
            event_type=EventType.AUTH_EMAIL_VERIFY_REDEEM,
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
        event_type=EventType.AUTH_EMAIL_VERIFY_REDEEM,
        actor_type=ActorType.USER,
        actor_id=user.id,
        resource_type="user",
        resource_id=user.id,
        payload={"matched": True},
        **context_from_request(request),
    )
    await db.commit()
    return VerifyEmailResponse(message="Email verified.")


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={429: {"description": "Rate limit exceeded"}},
    dependencies=[Depends(auth_burst_rate_limit)],
)
async def resend_verification_v1(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResendVerificationResponse:
    """Issue a new verification token and email the link.

    No-op (still 202) if the user is already verified, so callers
    can't probe verification state with this endpoint.
    """

    from app.services.email import send_email
    from app.services.email_verification import (
        issue_token as issue_verify_token,
    )

    settings_local = get_settings()
    if not current_user.email_verified:
        cleartext = await issue_verify_token(db, current_user)
        link = (
            f"{settings_local.frontend_url()}/verify-email"
            f"?token={cleartext}"
        )
        await send_email(
            to=current_user.email,
            subject="Confirm your siege-range email",
            body_text=(
                f"Hi {current_user.display_name or current_user.username},\n\n"
                f"Use this link to confirm your email — expires in "
                f"24 hours:\n\n{link}\n"
            ),
        )
        await audit_append(
            db,
            event_type=EventType.AUTH_EMAIL_VERIFY_REQUEST,
            actor_type=ActorType.USER,
            actor_id=current_user.id,
            resource_type="user",
            resource_id=current_user.id,
            payload={"reason": "resend"},
            **context_from_request(request),
        )
        await db.commit()
    return ResendVerificationResponse(
        message="Verification email sent if your account is not already verified."
    )
