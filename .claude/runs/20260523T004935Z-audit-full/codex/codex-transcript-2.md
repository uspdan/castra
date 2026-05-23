Reading additional input from stdin...
OpenAI Codex v0.124.0 (research preview)
--------
workdir: /data/projects/seige-range
model: gpt-5.5
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 019e5263-5157-7332-bcc1-59c174e60c95
--------
user
Security validation of a pre-computed list of findings on this FastAPI/SQLAlchemy CTF platform. Be terse. For each finding read the cited file and answer CONFIRMED / FALSE-POSITIVE / DOWNGRADE / NEEDS-MORE-INFO with one short note. End with: VERDICT: APPROVED  or  VERDICT: KICK-BACK.

F1. backend/app/middleware/security_headers.py lines 108, 113: literal strings "Strict-Transport-REDACTED" and "Content-REDACTED-Policy" instead of canonical Security/Content-Security. Class REDACTEDHeadersMiddleware line 88. CRITICAL.
F2. backend/app/main.py:154 FastAPI() omits docs_url=None/redoc_url=None/openapi_url=None. /docs exposed in prod. HIGH.
F3. backend/app/routers/auth.py login (lines 106-186) has no MFA check; v1 router (backend/app/routers/v1/auth.py:309-327) does. v0 mounted at backend/app/main.py:211. MFA-enabled user bypasses second factor via v0. CRITICAL.
F4. backend/app/middleware/rate_limit.py:48-51 defines auth_rate_limit; rg "Depends(auth_rate_limit)" in app/routers returns nothing. HIGH.
F5. backend/app/middleware/rate_limit.py:43,49,55 uses request.client.host (proxy IP behind nginx). HIGH.
F6. backend/app/services/webhook_dispatch.py POSTs subscription.target_url verbatim; backend/app/schemas/v1/webhooks.py validates HttpUrl only — no private-IP filter. CRITICAL (admin-mediated).
F7. backend/app/routers/v1/auth.py forgot-password (lines 452-542) — responses dict declares 429 but no rate-limit Depends. HIGH.
F8. backend/app/services/mfa.py _verify_or_raise — no per-token attempt counter; pending JWT TTL 300s (line 40). HIGH.
F9. backend/app/routers/v1/auth.py:248 + backend/app/routers/auth.py:122 — bcrypt verify only when user exists; 30x timing oracle. HIGH.
F10. backend/app/routers/v1/auth.py:258-262 stores raw payload.email in AUTH_LOGIN_FAILED ledger row (privacy/GDPR). HIGH.
F11. backend/app/models.py 562 lines; backend/app/services/flag_submission.py 614 lines. CLAUDE.md §1.1 says <300. MEDIUM.
F12. frontend/package.json uses ^ ranges everywhere. CLAUDE.md §3.4 forbids floating ranges. HIGH.
F13. .github/workflows/ci.yml runs `pytest tests/unit/ -v --no-cov`; pytest.ini has --cov-fail-under=80 but is overridden; integration tests not in CI. HIGH.
F14. WebSocket access tokens appear in uvicorn access logs (token in query string). Verified live. HIGH.

Also: skim app/routers/ and app/services/ briefly for any MISSED security finding (max 5). One-line entries.

Format strictly:
[SEV] file:line — finding
  Verdict: CONFIRMED|FALSE-POSITIVE|DOWNGRADE|NEEDS-MORE-INFO  — short note
warning: Codex could not find bubblewrap on PATH. Install bubblewrap with your OS package manager. See the sandbox prerequisites: https://developers.openai.com/codex/concepts/sandboxing#prerequisites. Codex will use the vendored bubblewrap in the meantime.
codex
I’ll validate the cited files directly and keep this to the requested verdict format. The workspace is read-only, so I’ll only inspect files and run searches.
exec
/bin/bash -lc "sed -n '1,220p' backend/app/services/webhook_dispatch.py && sed -n '1,220p' backend/app/schemas/v1/webhooks.py" in /data/projects/seige-range
 succeeded in 0ms:
"""Outbound webhook dispatch.

Phase 12 (slice 5). Looks up active :class:`WebhookSubscription` rows
whose ``events`` list contains the firing event type, then POSTs a
canonical JSON envelope to each ``target_url`` with an HMAC-SHA256
signature header.

Design constraints (CLAUDE.md §3, §15):

* **Best-effort delivery.** A single attempt with a 5-second
  timeout. Network failures, non-2xx responses, and unsigned 4xx
  responses all flow into ``last_status`` / ``last_error`` on the
  subscription row but never raise into the caller. The submission
  flow that triggers dispatch must not 500 because Slack is
  flapping.
* **HMAC-signed body.** ``X-Siege-Signature: sha256=<hex>`` derived
  from the subscription's ``secret``. Receivers verify by
  recomputing — the same scheme GitHub / Stripe / Linear use.
* **Replay protection.** ``X-Siege-Delivery-Id`` header is a
  per-call UUID; receivers can de-dupe.
* **Receiver isolation.** Each subscription is dispatched on its
  own ``httpx.AsyncClient`` so a slow receiver doesn't head-of-line
  block the others. Failures are logged + persisted; the function
  returns when every subscription has been attempted.

A future slice will bring retries with exponential backoff + a
deliveries-history table for replay. For slice 5 the inline
``last_status`` / ``last_error`` fields are the only persisted
observability.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets as _secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookDelivery, WebhookSubscription


logger = structlog.get_logger()

_DEFAULT_TIMEOUT_S = 5.0
_SIGNATURE_HEADER = "X-Siege-Signature"
_DELIVERY_HEADER = "X-Siege-Delivery-Id"
_EVENT_HEADER = "X-Siege-Event"
_SECRET_BYTES = 32  # 64 hex chars; well above 128-bit margin


def generate_subscription_secret() -> str:
    """Return a fresh URL-safe random secret for a new subscription."""

    return _secrets.token_hex(_SECRET_BYTES)


def sign_body(secret: str, body: bytes) -> str:
    """Compute the ``sha256=<hex>`` signature for ``body``.

    Exposed for tests + hypothetical receiver-side verification
    helpers. The ``sha256=`` prefix matches the GitHub / Stripe
    style; receivers can split on ``=`` to extract the hex digest.
    """

    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def deliver_event(
    *,
    db: AsyncSession,
    event_type: str,
    payload: Mapping[str, Any],
    http_client_factory=None,
) -> None:
    """Fan out a single audit event to every matching subscription.

    Loads active :class:`WebhookSubscription` rows whose ``events``
    list contains ``event_type``, signs the canonical JSON body with
    each subscription's secret, and POSTs concurrently. The function
    returns when every dispatch task has completed (or its 5-second
    timeout has elapsed). Per-row ``last_*`` fields are updated and
    committed in the calling transaction.

    ``http_client_factory`` is a test seam; production callers
    omit it and a fresh ``httpx.AsyncClient`` is used per attempt.
    """

    subscriptions = await _matching_subscriptions(db, event_type)
    if not subscriptions:
        return

    delivery_id = _secrets.token_hex(8)
    canonical_body = _canonical_body(event_type, delivery_id, payload)

    factory = http_client_factory or _default_http_client
    # HTTP fan-out runs concurrently; the results (per-subscription
    # status / error) are persisted to the DB *serially* afterwards.
    # Mixing concurrent ``db.add`` / ``db.flush`` calls into the same
    # session triggers SQLAlchemy's "flush within flush" warning and
    # is genuinely racy on the unit-of-work tracker — the post-hoc
    # write loop avoids both.
    outcomes: list[_AttemptOutcome] = await asyncio.gather(
        *(
            _attempt_one(
                subscription=sub,
                event_type=event_type,
                delivery_id=delivery_id,
                body=canonical_body,
                factory=factory,
            )
            for sub in subscriptions
        ),
        return_exceptions=False,
    )
    now = datetime.now(timezone.utc)
    for outcome in outcomes:
        sub = outcome.subscription
        sub.last_delivery_at = now
        sub.last_status = outcome.status
        sub.last_error = (
            (outcome.error or "")[:500] if outcome.error else None
        )
        db.add(sub)
        # Phase 12 (slice 6): record an attempt row in
        # ``webhook_deliveries`` so the v1 list endpoint and replay
        # endpoint have something to read.
        db.add(
            WebhookDelivery(
                subscription_id=sub.id,
                event_type=event_type,
                delivery_id=delivery_id,
                payload=dict(payload),
                attempt=1,
                status=outcome.status,
                http_status=outcome.http_status,
                response_ms=outcome.response_ms,
                error=(outcome.error or "")[:500] if outcome.error else None,
                created_at=now,
            )
        )
    await db.flush()


async def _matching_subscriptions(
    db: AsyncSession, event_type: str
) -> list[WebhookSubscription]:
    rows = (
        await db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.is_active.is_(True)
            )
        )
    ).scalars().all()
    out: list[WebhookSubscription] = []
    for row in rows:
        events = list(row.events or [])
        if event_type in events or "*" in events:
            out.append(row)
    return out


def _canonical_body(
    event_type: str, delivery_id: str, payload: Mapping[str, Any]
) -> bytes:
    envelope = {
        "event_type": event_type,
        "delivery_id": delivery_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": dict(payload),
    }
    # ``sort_keys=True`` so the receiver-side recomputation is
    # deterministic regardless of dict iteration order.
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _default_http_client():
    return httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_S)


@dataclass(frozen=True)
class _AttemptOutcome:
    """Per-subscription outcome of a single dispatch attempt."""

    subscription: WebhookSubscription
    status: str
    http_status: int | None
    response_ms: int
    error: str | None


async def _attempt_one(
    *,
    subscription: WebhookSubscription,
    event_type: str,
    delivery_id: str,
    body: bytes,
    factory,
) -> _AttemptOutcome:
    """Pure HTTP attempt for a single subscription.

    Returns an :class:`_AttemptOutcome` and never raises; the caller
    serialises the resulting `last_*` writes + delivery row inserts
    onto the shared session.
    """

    headers = {
        "Content-Type": "application/json",
"""v1 webhook subscription DTOs.

The locked contract is:

* ``WebhookCreateRequest`` — admin sends ``name``, ``target_url``,
  ``events``. The server generates the secret.
* ``WebhookCreatedResponse`` — surfaced **once** at create time
  with ``secret`` populated. Subsequent reads omit the secret.
* ``WebhookResponse`` — returned by list / detail. No secret leak.

Phase 12 slice 5 deliberately ships no update endpoint; admins who
need to rotate a secret or change events should DELETE + re-POST.
A patch endpoint is a future slice.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# Allowed event names. Restricted to the audit-ledger event vocabulary
# the platform actually emits today; anything else is rejected at
# create time so the admin sees the failure immediately rather than
# waiting forever for a webhook that will never fire.
_KNOWN_EVENTS = {
    "challenge.flag.submit.pass",
    "challenge.flag.submit.fail",
    "challenge.released",
    "auth.register",
    "auth.login.success",
    "auth.login.failed",
    "auth.logout",
    "auth.refresh",
    "auth.password.reset.request",
    "auth.password.reset.redeem",
    "auth.password.change",
    "auth.profile.update",
    "auth.account.delete",
    "auth.data.export",
    "auth.mfa.enroll",
    "auth.mfa.confirm",
    "auth.mfa.disable",
    "auth.mfa.verify.success",
    "auth.mfa.verify.failed",
    "instance.launch",
    "instance.stop",
    "instance.reset",
    "instance.expired",
    "*",  # wildcard: deliver every event the platform emits
}


class WebhookCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    target_url: HttpUrl
    events: List[str] = Field(min_length=1, max_length=32)

    @field_validator("events")
    @classmethod
    def _events_known(cls, v: List[str]) -> List[str]:
        unknown = sorted(set(v) - _KNOWN_EVENTS)
        if unknown:
            raise ValueError(
                f"unknown event types: {unknown}. "
                f"Known: {sorted(_KNOWN_EVENTS)}"
            )
        if "*" in v and len(v) != 1:
            raise ValueError(
                "wildcard '*' must be the only entry when used"
            )
        # de-dupe while preserving order
        seen: set[str] = set()
        out: List[str] = []
        for entry in v:
            if entry not in seen:
                seen.add(entry)
                out.append(entry)
        return out


class WebhookResponse(BaseModel):
    """Read-side view of a subscription (no secret)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    target_url: str
    events: List[str]
    is_active: bool
    created_at: datetime
    last_delivery_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None


class WebhookCreatedResponse(WebhookResponse):
    """One-time create response. Carries the secret exactly once."""

    secret: str = Field(min_length=32)


class WebhookListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[WebhookResponse]
    total: int = Field(ge=0)

exec
/bin/bash -lc "sed -n '220,360p' backend/app/routers/v1/auth.py && sed -n '440,550p' backend/app/routers/v1/auth.py && sed -n '1,120p' backend/app/services/mfa.py" in /data/projects/seige-range
exec
/bin/bash -lc "sed -n '1,260p' backend/app/middleware/security_headers.py && sed -n '130,230p' backend/app/main.py && sed -n '80,210p' backend/app/routers/auth.py" in /data/projects/seige-range
 succeeded in 0ms:
        403: {"description": "Account is disabled"},
        429: {"description": "Account temporarily locked"},
    },
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
            payload={"email": payload.email, "reason": "email_not_verified"},
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
    responses={401: {"description": "Invalid or revoked refresh token"}},
)
async def refresh_v1(
    payload: AuthRefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(_get_redis),
) -> AuthRefreshResponse:
    token = payload.refresh_token


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
"""TOTP-based MFA service.

Sprint 7 Phase C. Wraps ``pyotp`` with the platform-specific bits:
secret generation, recovery-code lifecycle, login-step pending-token
issuance, code verification across both TOTP and recovery-code paths.

Recovery codes are 10 single-use 8-character strings, shown to the
user once at confirm time. Only sha256 hashes live in the
``mfa_recovery_codes`` table.

The MFA pending token is a short-lived JWT issued during the login
flow when a user has MFA enabled. It carries
``{"type": "mfa_pending", "sub": <user_id>}`` and TTLs in 5 minutes;
the user exchanges it via ``POST /auth/mfa/verify`` for the real
access + refresh tokens.
"""

from __future__ import annotations

import hashlib
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pyotp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import MfaRecoveryCode, User
from app.services.auth import create_access_token, create_refresh_token


_RECOVERY_CODE_COUNT = 10
_RECOVERY_CODE_LENGTH = 8
_RECOVERY_CODE_ALPHABET = string.ascii_uppercase + string.digits

_MFA_PENDING_TTL_SECONDS = 5 * 60


class InvalidMfaCode(ValueError):
    """Raised when a TOTP code or recovery code fails validation."""


class MfaNotEnrolled(ValueError):
    """Raised when an MFA action is attempted but the user hasn't
    finished enrolment (mfa_secret unset OR mfa_enabled=False)."""


@dataclass(frozen=True)
class EnrolStartResult:
    secret: str
    provisioning_uri: str


@dataclass(frozen=True)
class EnrolConfirmResult:
    recovery_codes: List[str]


def _hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.upper().encode("utf-8")).hexdigest()


def _generate_recovery_codes() -> List[str]:
    return [
        "".join(
            secrets.choice(_RECOVERY_CODE_ALPHABET)
            for _ in range(_RECOVERY_CODE_LENGTH)
        )
        for _ in range(_RECOVERY_CODE_COUNT)
    ]


def _issuer_name() -> str:
    settings = get_settings()
    return "siege-range" if settings.is_production else "siege-range (dev)"


async def start_enrolment(db: AsyncSession, user: User) -> EnrolStartResult:
    """Generate a fresh TOTP secret + provisioning URI for ``user``.

    Stores the secret on the row but does NOT enable MFA yet —
    enable happens in :func:`confirm_enrolment` after the user
    submits a valid TOTP code from their authenticator. Calling
    :func:`start_enrolment` again on a partially-enrolled user
    rotates the secret (the previous one becomes garbage).
    """

    secret = pyotp.random_base32()
    user.mfa_secret = secret
    user.mfa_enabled = False
    await db.flush()

    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name=_issuer_name(),
    )
    return EnrolStartResult(
        secret=secret, provisioning_uri=provisioning_uri
    )


async def confirm_enrolment(
    db: AsyncSession, user: User, code: str
) -> EnrolConfirmResult:
    """Verify the TOTP ``code`` and finalise enrolment.

    On success: sets ``mfa_enabled=True``, generates 10 recovery
    codes, stores their hashes, returns the cleartext list once
    (the caller surfaces them to the UI; they're never persisted).
    """

    if not user.mfa_secret:
        raise MfaNotEnrolled("call /mfa/enroll first")

    if not pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1):
        raise InvalidMfaCode("code did not match")

 succeeded in 0ms:
"""Response-time security headers middleware (Phase 3).

Headers applied to every response:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: strict-origin-when-cross-origin
    - Permissions-Policy: minimal allowlist (camera/microphone/geolocation off)
    - Strict-Transport-REDACTED: prod-only (1y, includeSubDomains)
    - Content-REDACTED-Policy: locked down — no wildcards, no unsafe-eval

CSP is deliberately *not* applied to the OpenAPI/Swagger surfaces
(``/docs``, ``/redoc``, ``/openapi.json``): both Swagger UI and ReDoc
load assets from a CDN and require inline scripts. Locking those down
is a Phase 12 problem (we'll self-host the Swagger bundle and tighten
this exception then).
"""

from __future__ import annotations

from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


_DOC_PATHS: frozenset[str] = frozenset({"/docs", "/redoc", "/openapi.json"})


_PERMISSIONS_POLICY: str = ", ".join(
    f"{feature}=()"
    for feature in (
        "camera",
        "microphone",
        "geolocation",
        "payment",
        "usb",
        "interest-cohort",
    )
)


_CSP_REPORT_PATH = "/csp-report"


def _build_csp(
    connect_src_extra: Iterable[str] = (),
    *,
    include_report_uri: bool = True,
) -> str:
    """Strict CSP suitable for a Vite-built React SPA.

    - script-src 'self': Vite production builds emit hashed assets, no
      inline scripts. We do **not** allow ``unsafe-eval`` or ``unsafe-inline``.
    - style-src 'self' 'unsafe-inline': Tailwind/React inline style
      attributes are unavoidable in the current build; tracked for
      Phase 12 review.
    - connect-src 'self': API + websocket on the same origin (nginx
      fronts both). Extra entries (e.g. wss://...) can be added by the
      caller if a future deploy splits the origin.

    Sprint 12 Phase B — when ``include_report_uri`` is set, browsers
    POST CSP violations to ``/csp-report`` so we can audit-log them.
    """

    connect_src = " ".join(["'self'", *connect_src_extra]).strip()
    directives = [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        f"connect-src {connect_src}",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ]
    if include_report_uri:
        # ``report-uri`` is the legacy directive (still honoured by
        # every browser); ``report-to`` requires a separate
        # Reporting-Endpoints header which isn't worth the extra
        # plumbing today.
        directives.append(f"report-uri {_CSP_REPORT_PATH}")
    return "; ".join(directives)


class REDACTEDHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, is_production: bool) -> None:
        super().__init__(app)
        self._is_production = is_production
        self._csp = _build_csp()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)

        if self._is_production:
            response.headers.setdefault(
                "Strict-Transport-REDACTED",
                "max-age=31536000; includeSubDomains",
            )

        if request.url.path not in _DOC_PATHS:
            response.headers.setdefault("Content-REDACTED-Policy", self._csp)

        return response

    # Shutdown
    logger.info("Shutting down Siege Range API...")
    pubsub_task.cancel()
    try:
        await pubsub_task
    except asyncio.CancelledError:
        pass

    from app.services.scheduler import scheduler
    scheduler.shutdown(wait=False)

    try:
        docker_client.close()
    except Exception:
        pass

    try:
        await redis_conn.close()
    except Exception:
        pass
    logger.info("Shutdown complete.")


app = FastAPI(title="Siege Range API", version="2.5.0", lifespan=lifespan)

# Sprint 11 Phase C — opt-in OpenTelemetry tracing. No-op when
# OTEL_EXPORTER_OTLP_ENDPOINT is unset. Failure to configure
# (missing dep, bad endpoint) logs WARN and degrades to disabled
# — the platform must always boot.
from app.database import engine as _db_engine
from app.observability.tracing import configure_tracing

configure_tracing(app, _db_engine)

from app.middleware.logging_mw import LoggingMiddleware
from app.middleware.metrics import PrometheusMetricsMiddleware
from app.middleware.security_headers import REDACTEDHeadersMiddleware

# Middleware order: outer-most runs last on the response. We want the
# request-id logger to see the response **after** security headers have
# been attached, so register the headers middleware first (it ends up
# inner-most relative to LoggingMiddleware).
app.add_middleware(REDACTEDHeadersMiddleware, is_production=_settings.is_production)
app.add_middleware(LoggingMiddleware)
# Prometheus metrics — outermost, so it sees the actual response
# status code Starlette returns to the client (after any later
# middleware mutates it).
app.add_middleware(PrometheusMetricsMiddleware)

_allowed_origins = _settings.allowed_origins_list()
if not _allowed_origins:
    logger.warning(
        "CORS disabled: ALLOWED_ORIGINS is empty and APP_ENV=%s",
        _settings.APP_ENV,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

from app.routers.auth import router as auth_router
from app.routers.challenges import router as challenges_router
from app.routers.health import router as health_router
from app.routers.instances import router as instances_router
from app.routers.leaderboard import router as leaderboard_router
from app.routers.stats import router as stats_router
from app.routers.writeups import router as writeups_router
from app.routers.competitions import router as competitions_router
from app.routers.notifications import router as notifications_router
from app.routers.admin import router as admin_router
from app.routers.ws import router as ws_router
from app.routers.v1 import router as api_v1_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(challenges_router)
app.include_router(instances_router)
app.include_router(leaderboard_router)
app.include_router(stats_router)
app.include_router(writeups_router)
app.include_router(competitions_router)
app.include_router(notifications_router)
app.include_router(admin_router)
app.include_router(ws_router)
# Phase 12 (slice 1): public API v1 namespace. Locked DTOs under
# /api/v1/. Legacy unversioned routes stay live alongside until the
# front door is migrated over in a later slice.
app.include_router(api_v1_router)
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

exec
/bin/bash -lc "sed -n '1,90p' backend/app/middleware/rate_limit.py && rg -n \"Depends\\(auth_rate_limit\\)|auth_rate_limit|request\\.client\\.host|X-Forwarded|Forwarded\" backend/app" in /data/projects/seige-range
 succeeded in 0ms:
import time

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.config import get_settings


async def _get_redis():
    settings = get_settings()
    return aioredis.from_url(settings.REDIS_URL)


async def _check_rate_limit(key: str, limit: int, window_seconds: int, request: Request) -> None:
    redis_client = await _get_redis()
    try:
        now = time.time()
        pipeline = redis_client.pipeline()
        await pipeline.zremrangebyscore(key, 0, now - window_seconds)
        await pipeline.zadd(key, {str(now): now})
        await pipeline.zcard(key)
        await pipeline.expire(key, window_seconds)
        results = await pipeline.execute()
        request_count = results[2]

        remaining = max(0, limit - request_count)

        if request_count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + window_seconds)),
                },
            )
    finally:
        await redis_client.close()


async def flag_rate_limit(request: Request) -> None:
    user_id = getattr(request.state, "user_id", request.client.host)
    key = f"siege:ratelimit:flag:{user_id}"
    await _check_rate_limit(key, 10, 60, request)


async def auth_rate_limit(request: Request) -> None:
    ip = request.client.host
    key = f"siege:ratelimit:auth:{ip}"
    await _check_rate_limit(key, 5, 60, request)


async def general_rate_limit(request: Request) -> None:
    user_id = getattr(request.state, "user_id", request.client.host)
    key = f"siege:ratelimit:general:{user_id}"
    await _check_rate_limit(key, 100, 60, request)
backend/app/middleware/rate_limit.py:43:    user_id = getattr(request.state, "user_id", request.client.host)
backend/app/middleware/rate_limit.py:48:async def auth_rate_limit(request: Request) -> None:
backend/app/middleware/rate_limit.py:49:    ip = request.client.host
backend/app/middleware/rate_limit.py:55:    user_id = getattr(request.state, "user_id", request.client.host)
backend/app/routers/auth.py:25:from app.middleware.rate_limit import auth_rate_limit
backend/app/services/audit/request_context.py:17:    ip = request.client.host if request.client else None
backend/app/routers/v1/workstation.py:38:    # Derived from the request's Host + X-Forwarded-Proto headers so
backend/app/routers/v1/workstation.py:61:    """Prefer X-Forwarded-Proto so URLs render https behind TLS proxies."""
backend/app/routers/v1/workstation.py:70:    other front-door that sets the standard X-Forwarded-* headers).

codex
The first pass confirms several items exactly as written. I’m checking the remaining cited line contexts and then doing the requested skim for up to five missed issues.
exec
/bin/bash -lc "sed -n '120,260p' backend/app/services/mfa.py && sed -n '360,460p' backend/app/routers/v1/auth.py && sed -n '1,170p' backend/app/routers/auth.py" in /data/projects/seige-range
 succeeded in 0ms:
        raise InvalidMfaCode("code did not match")

    user.mfa_enabled = True

    cleartext_codes = _generate_recovery_codes()
    for cc in cleartext_codes:
        db.add(
            MfaRecoveryCode(
                user_id=user.id,
                code_hash=_hash_recovery_code(cc),
            )
        )
    await db.flush()
    return EnrolConfirmResult(recovery_codes=cleartext_codes)


async def disable_mfa(db: AsyncSession, user: User, code: str) -> None:
    """Verify ``code`` (TOTP or recovery) and disable MFA + drop
    all stored recovery codes."""

    from sqlalchemy import delete

    if not user.mfa_enabled or not user.mfa_secret:
        raise MfaNotEnrolled("MFA is not enabled")

    await _verify_or_raise(db, user, code)

    user.mfa_enabled = False
    user.mfa_secret = None
    await db.execute(
        delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
    )
    await db.flush()


async def verify_login_code(
    db: AsyncSession, user: User, code: str
) -> tuple[str, str]:
    """Verify ``code`` against TOTP first, then recovery codes.

    On success: returns the (access_token, refresh_token) pair.
    On failure: raises :class:`InvalidMfaCode`.
    """

    if not user.mfa_enabled or not user.mfa_secret:
        raise MfaNotEnrolled("MFA is not enabled")

    await _verify_or_raise(db, user, code)
    await db.flush()

    return (
        create_access_token(user.id, user.role.value),
        create_refresh_token(user.id),
    )


async def _verify_or_raise(
    db: AsyncSession, user: User, code: str
) -> None:
    """TOTP first; falls back to recovery codes. Marks the matched
    recovery code used. Raises :class:`InvalidMfaCode` on miss."""

    code_str = (code or "").strip()
    if not code_str:
        raise InvalidMfaCode("code missing")

    # TOTP path — 6 digits.
    if code_str.isdigit() and len(code_str) == 6:
        if pyotp.TOTP(user.mfa_secret).verify(code_str, valid_window=1):
            return

    # Recovery-code path — alphanumeric, length matches.
    candidate = _hash_recovery_code(code_str)
    row: Optional[MfaRecoveryCode] = (
        await db.execute(
            select(MfaRecoveryCode).where(
                MfaRecoveryCode.user_id == user.id,
                MfaRecoveryCode.code_hash == candidate,
                MfaRecoveryCode.used_at.is_(None),
            )
        )
    ).scalars().first()
    if row is not None:
        row.used_at = datetime.now(timezone.utc)
        return

    raise InvalidMfaCode("code did not match")


# ---------------------------------------------------------------------------
# Pending-token plumbing for the two-step login flow
# ---------------------------------------------------------------------------
def issue_mfa_pending_token(user_id: int) -> str:
    """Short-lived JWT carrying ``{type:"mfa_pending"}`` + sub.

    Uses the same ``python-jose`` library as the rest of the auth
    stack so signature verification is uniform.
    """

    from jose import jwt as jose_jwt

    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "type": "mfa_pending",
        "exp": int(
            (
                datetime.now(timezone.utc)
                + timedelta(seconds=_MFA_PENDING_TTL_SECONDS)
            ).timestamp()
        ),
    }
    return jose_jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_mfa_pending_token(token: str) -> int:
    """Validate the pending token and return the user_id."""

    from jose import jwt as jose_jwt, JWTError

    settings = get_settings()
    try:
        decoded = jose_jwt.decode(
            token, settings.SECRET_KEY, algorithms=["HS256"]
        )
    except JWTError as exc:
        raise InvalidMfaCode("invalid pending token") from exc
    if decoded.get("type") != "mfa_pending":
        raise InvalidMfaCode("wrong token type")
    sub = decoded.get("sub")
    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise InvalidMfaCode("malformed pending token") from exc


__all__ = [
    "EnrolConfirmResult",
    "EnrolStartResult",
    "InvalidMfaCode",
    "MfaNotEnrolled",
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

exec
/bin/bash -lc "wc -l backend/app/models.py backend/app/services/flag_submission.py && sed -n '1,120p' CLAUDE.md && sed -n '1,220p' frontend/package.json && sed -n '1,180p' .github/workflows/ci.yml && sed -n '1,160p' pytest.ini" in /data/projects/seige-range
 exited 2 in 0ms:
  562 backend/app/models.py
  614 backend/app/services/flag_submission.py
 1176 total
# CLAUDE.md — Project Engineering Standards

> This file governs how Claude Code builds, modifies, and reviews code in this project.
> All directives are mandatory. Violations must be flagged, not silently ignored.
>
> **Canonical source:** `standards` repo. Do not edit per-project copies directly.
> Pull updates via `./scripts/sync-standards.sh` or CI bootstrap.

---

## 1. ARCHITECTURE PRINCIPLES

### 1.1 Modularity

- **Single Responsibility**: Every module, class, and function does exactly one thing. If you need the word "and" to describe what it does, split it.
- **Explicit Boundaries**: Each module exposes a public API via an `index.ts` (or `__init__.py`, `mod.rs`, etc.). Internal implementation files are never imported directly by other modules.
- **Dependency Direction**: Dependencies flow inward. Core/domain logic has zero dependencies on infrastructure, frameworks, or I/O. Use dependency injection or ports-and-adapters to invert where needed.
- **No God Files**: No single file exceeds 300 lines. No single function exceeds 50 lines. If a module needs more, decompose it.
- **Feature Isolation**: New features are added as new modules, not by extending existing ones. Existing modules are only modified to expose new extension points.

### 1.2 Project Structure

Every project must follow a consistent layout. Adapt naming to the language ecosystem but preserve the separation:

```
src/
├── core/              # Domain logic, pure functions, business rules — zero I/O
├── services/          # Orchestration layer — coordinates core logic with infra
├── infra/             # External integrations: DB, HTTP, queues, file I/O
│   ├── db/
│   ├── http/
│   └── queue/
├── api/               # Entrypoints: REST routes, CLI handlers, event consumers
├── shared/            # Cross-cutting: types, constants, errors, result types
│   ├── types/
│   ├── errors/
│   └── constants/
├── config/            # Configuration loading, validation, env parsing
└── utils/             # Pure utility functions only — no business logic
tests/
├── unit/              # Mirror src/ structure, one test file per module
├── integration/       # Tests requiring real infra (DB, network)
└── fixtures/          # Shared test data, factories, builders
scripts/               # Build, deploy, migration, seed scripts
docs/                  # Architecture decision records, runbooks, API docs
docker/                # Dockerfiles, compose files, container configs
```

### 1.3 Naming & Conventions

- Files: `kebab-case` (TS/JS), `snake_case` (Python/Rust).
- Exported types/classes: `PascalCase`. Functions/variables: `camelCase` (TS/JS) or `snake_case` (Python/Rust).
- Boolean variables/functions: prefix with `is`, `has`, `should`, `can`.
- Constants: `UPPER_SNAKE_CASE`, defined in `shared/constants/`.
- No abbreviations in public APIs. `getUserAuthentication()` not `getUsrAuth()`.

### 1.4 Dependency Injection & Wiring

- **Constructor injection** is the default pattern. All dependencies are passed explicitly — no service locators, no ambient singletons, no module-level mutable state.
- **Composition root**: A single wiring entrypoint (`src/composition-root.ts`, `src/container.py`, etc.) assembles the dependency graph. No other file instantiates infrastructure or service-layer objects.
- **Interfaces over implementations**: Core and service layers depend on interfaces/protocols/traits. Concrete implementations live in `infra/` and are wired at the composition root.
- **Test seams**: Every external dependency is injectable, making it replaceable in tests without mocks of internals. Fake implementations live in `tests/fixtures/fakes/`.

---

## 2. ERROR HANDLING & RESULT TYPES

### 2.1 Fail-Fast, Fail-Loud

- **No silent swallowing.** Every `catch` block must either re-throw, return a typed error, or log at `ERROR` level with full context. Empty catch blocks are forbidden.
- **Use Result types** over thrown exceptions for expected failure paths. `Result<T, E>` (Rust), `Either` pattern (TS), or equivalent. Exceptions are for truly exceptional/unrecoverable situations.
- **Validate at the boundary.** All external input (HTTP, CLI, env vars, file reads, queue messages) is validated and parsed into typed domain objects at the point of entry. Nothing unvalidated reaches core logic.

### 2.2 Error Classification

Define and use a typed error hierarchy:

```
AppError
├── ValidationError      # Bad input — 400-class
├── AuthenticationError  # Identity unknown — 401
├── AuthorisationError   # Identity known, access denied — 403
├── NotFoundError        # Resource does not exist — 404
├── ConflictError        # State conflict — 409
├── RateLimitError       # Throttled — 429
├── DependencyError      # Upstream/infra failure — 502/503
└── InternalError        # Unexpected bug — 500
```

Every error must carry: `code` (machine-readable), `message` (human-readable), `context` (structured metadata), `timestamp`, `requestId` (if in a request context).

---

## 3. SECURITY CONTROLS

### 3.1 Input Validation

- Validate **all** external input with a schema validation library (Zod, Pydantic, JSON Schema, etc.). No hand-rolled regex-only validation.
- Apply allowlists, not denylists. Define what is permitted, reject everything else.
- Enforce length limits, type constraints, and format constraints on every field.
- Sanitise all string inputs before use in HTML, SQL, shell commands, or log output.

### 3.2 Authentication & Authorisation

- Never store secrets, API keys, tokens, or passwords in source code, config files, or environment variable defaults. Use a secrets manager or `.env` files excluded via `.gitignore`.
- Always check authorisation at the service layer, not only at the API/route layer. Defence in depth.
- Implement principle of least privilege: every component, user, and service account gets the minimum permissions required.
- Session tokens / JWTs: validate expiry, issuer, audience, and signature on every request. No "trust the client" patterns.

### 3.3 Data Protection

- PII and sensitive fields are encrypted at rest and masked in logs. Implement a `SensitiveString` wrapper type that redacts on serialisation/logging.
- No secrets in URLs or query parameters. Ever.
- Database queries use parameterised queries or ORM methods. Raw string interpolation into SQL is forbidden.
- All HTTP responses include security headers: `Content-REDACTED-Policy`, `X-Content-Type-Options`, `Strict-Transport-REDACTED`, `X-Frame-Options`.

### 3.4 Dependency REDACTED

- Pin all dependency versions exactly. No floating ranges (`^`, `~`, `*`).
- Run `npm audit` / `pip audit` / `cargo audit` (as appropriate) before every commit. Fail the build on HIGH or CRITICAL findings.
{
  "name": "siege-range-dashboard",
  "private": true,
  "version": "2.4.1",
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "preview": "vite preview",
    "e2e": "playwright test",
    "e2e:list": "playwright test --list",
    "e2e:ui": "playwright test --ui"
  },
  "dependencies": {
    "axios": "^1.6.7",
    "clsx": "^2.1.0",
    "lucide-react": "^0.344.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.1",
    "recharts": "^2.12.2",
    "zustand": "^4.5.1"
  },
  "devDependencies": {
    "@playwright/test": "^1.59.1",
    "@tailwindcss/vite": "^4.0.0",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "tailwindcss": "^4.0.0",
    "vite": "^5.1.4"
  }
}
name: ci

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

# Cancel in-flight runs when a branch is pushed twice in quick
# succession — the older run's signal is no longer load-bearing.
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend-tests:
    name: backend — pytest + coverage gate
    runs-on: ubuntu-22.04
    timeout-minutes: 20

    steps:
      - name: checkout
        uses: actions/checkout@v4

      - name: set up python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: backend/requirements*.txt

      - name: install backend deps
        working-directory: backend
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r requirements-test.txt

      - name: run pytest — unit tests only (integration suite needs
          testcontainers config that isn't wired into CI yet)
        working-directory: backend
        env:
          APP_ENV: test
          SECRET_KEY: ci-test-secret-do-not-use-in-prod-0123456789abcdef0123456789abcdef
          ADMIN_PASSWORD: CIAdminPasswordA1!
          ALLOWED_ORIGINS: http://localhost:3000
        run: |
          python -m pytest tests/unit/ -v --no-cov

  frontend-build:
    name: frontend — vite build + lint
    runs-on: ubuntu-22.04
    timeout-minutes: 10

    steps:
      - name: checkout
        uses: actions/checkout@v4

      - name: set up node 20
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: install
        working-directory: frontend
        run: npm ci

      - name: lint
        working-directory: frontend
        run: npm run lint --if-present

      - name: build
        working-directory: frontend
        run: npm run build

  secret-scan:
    name: secret-scan — trufflehog
    runs-on: ubuntu-22.04
    timeout-minutes: 5

    steps:
      - name: checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: trufflehog (verified-only)
        uses: trufflesecurity/trufflehog@v3.81.10
        with:
          path: ./
          # Only verified secrets fail the build. Heuristic-only hits
          # become PR comments via the action's default behaviour.
          extra_args: --only-verified

  flag-leak-check:
    name: flag-leak — refuse cleartext CTF flags in tracked source
    runs-on: ubuntu-22.04
    timeout-minutes: 2

    steps:
      - name: checkout
        uses: actions/checkout@v4

      - name: scan tracked files for ``CTF{...}`` literals
        run: |
          set -eu
          # Permit the redacted marker and the explicit template
          # placeholder. Anything else means cleartext flag back in
          # the tree — fail the build.
          # examples/ ships intentionally-leaky training artefacts
          # (pre-rendered memory dumps, sample evtx, etc.) for the
          # challenge-author tutorial. Out of scope for this gate —
          # tracked in docs/author-onboarding.md as a follow-up.
          if git grep -nE 'CTF\{[^}]+\}' \
              -- ':!*.flag.txt' ':!examples/' ':!docs/' \
                 ':!.github/workflows/ci.yml' \
              | grep -v 'CTF{REDACTED}' \
              | grep -v 'CTF{{REDACTED}}' \
              | grep -v 'CTF{EXAMPLE_flag_string}' \
              | grep -v 'CTF{<' ; then
            echo
            echo "::error::Cleartext CTF flag literal detected in tracked source."
            echo "::error::Flags must live under secrets/ and be staged via scripts/stage-answers.sh"
            exit 1
          fi
          echo "no cleartext CTF{...} literals in tracked source — ok"
sed: can't read pytest.ini: No such file or directory

exec
/bin/bash -lc "rg -n \"websocket|WebSocket|token|access_token|query|Query|logger|uvicorn|Authorization|Depends\\(|include_router|@router\\.(get|post|put|patch|delete)\" backend/app/routers backend/app/services" in /data/projects/seige-range
 succeeded in 0ms:
backend/app/services/validator_registry.py:32:_logger = logging.getLogger(__name__)
backend/app/services/validator_registry.py:122:        _logger.info(
backend/app/services/api_v1.py:134:                _user_points_subq().scalar_subquery() > total_points
backend/app/routers/notifications.py:1:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/notifications.py:12:@router.get("/")
backend/app/routers/notifications.py:14:    page: int = Query(1, ge=1),
backend/app/routers/notifications.py:15:    per_page: int = Query(20, ge=1, le=100),
backend/app/routers/notifications.py:16:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:17:    db: AsyncSession = Depends(get_db),
backend/app/routers/notifications.py:54:@router.put("/{notification_id}/read")
backend/app/routers/notifications.py:57:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:58:    db: AsyncSession = Depends(get_db),
backend/app/routers/notifications.py:76:@router.put("/read-all")
backend/app/routers/notifications.py:78:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:79:    db: AsyncSession = Depends(get_db),
backend/app/routers/notifications.py:98:@router.get("/unread-count")
backend/app/routers/notifications.py:100:    current_user: User = Depends(get_current_user),
backend/app/routers/notifications.py:101:    db: AsyncSession = Depends(get_db),
backend/app/services/notifications.py:1:"""Notification service — DB row + WebSocket fan-out in one call.
backend/app/services/notifications.py:3:The frontend's ``useWebSocket`` hook already routes
backend/app/services/notifications.py:29:logger = structlog.get_logger()
backend/app/services/notifications.py:86:        logger.warning(
backend/app/services/challenge_browse.py:65:            .scalar_subquery()
backend/app/services/challenge_browse.py:82:        await db.execute(select(func.count()).select_from(stmt.subquery()))
backend/app/routers/auth.py:17:    create_access_token,
backend/app/routers/auth.py:18:    create_refresh_token,
backend/app/routers/auth.py:19:    decode_token,
backend/app/routers/auth.py:42:@router.post("/register", status_code=status.HTTP_201_CREATED)
backend/app/routers/auth.py:46:    db: AsyncSession = Depends(get_db),
backend/app/routers/auth.py:87:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:88:    refresh_token = create_refresh_token(user.id)
backend/app/routers/auth.py:101:        "access_token": access_token,
backend/app/routers/auth.py:102:        "refresh_token": refresh_token,
backend/app/routers/auth.py:106:@router.post("/login")
backend/app/routers/auth.py:110:    db: AsyncSession = Depends(get_db),
backend/app/routers/auth.py:111:    redis_client=Depends(get_redis),
backend/app/routers/auth.py:169:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:170:    refresh_token = create_refresh_token(user.id)
backend/app/routers/auth.py:184:        "access_token": access_token,
backend/app/routers/auth.py:185:        "refresh_token": refresh_token,
backend/app/routers/auth.py:189:@router.post("/refresh", response_model=AccessTokenResponse)
backend/app/routers/auth.py:193:    redis_client=Depends(get_redis),
backend/app/routers/auth.py:194:    db: AsyncSession = Depends(get_db),
backend/app/routers/auth.py:196:    token = data.refresh_token
backend/app/routers/auth.py:198:    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
backend/app/routers/auth.py:202:    payload = decode_token(token)
backend/app/routers/auth.py:204:        raise HTTPException(status_code=401, detail="Invalid token type")
backend/app/routers/auth.py:212:    new_access = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:224:    return {"access_token": new_access, "token_type": "bearer"}
backend/app/routers/auth.py:227:@router.post("/logout", response_model=MessageResponse)
backend/app/routers/auth.py:231:    redis_client=Depends(get_redis),
backend/app/routers/auth.py:232:    db: AsyncSession = Depends(get_db),
backend/app/routers/auth.py:234:    token = data.refresh_token
backend/app/routers/auth.py:236:    if token:
backend/app/routers/auth.py:238:            payload = decode_token(token)
backend/app/routers/auth.py:242:                await redis_client.set(f"siege:blacklist:{token}", "1", ex=ttl)
backend/app/routers/auth.py:258:        payload={"token_revoked": bool(token)},
backend/app/routers/auth.py:265:@router.get("/me")
backend/app/routers/auth.py:267:    current_user: User = Depends(get_current_user),
backend/app/routers/auth.py:268:    db: AsyncSession = Depends(get_db),
backend/app/routers/auth.py:283:    rank_subquery = (
backend/app/routers/auth.py:286:        .subquery()
backend/app/routers/auth.py:289:        select(func.count(rank_subquery.c.user_id) + 1).where(rank_subquery.c.pts > total_points)
backend/app/services/auth.py:4:from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
backend/app/services/auth.py:29:def create_access_token(user_id: int, role: str) -> str:
backend/app/services/auth.py:40:def create_refresh_token(user_id: int) -> str:
backend/app/services/auth.py:50:def decode_token(token: str) -> dict:
backend/app/services/auth.py:52:        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
backend/app/services/auth.py:57:            detail="Invalid or expired token",
backend/app/services/auth.py:62:    credentials: HTTPAuthorizationCredentials = Depends(security),
backend/app/services/auth.py:63:    db: AsyncSession = Depends(get_db),
backend/app/services/auth.py:70:    payload = decode_token(credentials.credentials)
backend/app/services/auth.py:74:            detail="Invalid token type",
backend/app/services/auth.py:87:async def require_admin(current_user: User = Depends(get_current_user)) -> User:
backend/app/routers/writeups.py:4:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/writeups.py:27:@router.post("/{slug}")
backend/app/routers/writeups.py:31:    current_user: User = Depends(get_current_user),
backend/app/routers/writeups.py:32:    db: AsyncSession = Depends(get_db),
backend/app/routers/writeups.py:83:@router.get("/{slug}")
backend/app/routers/writeups.py:86:    page: int = Query(1, ge=1),
backend/app/routers/writeups.py:87:    per_page: int = Query(20, ge=1, le=100),
backend/app/routers/writeups.py:88:    current_user: User = Depends(get_current_user),
backend/app/routers/writeups.py:89:    db: AsyncSession = Depends(get_db),
backend/app/routers/writeups.py:149:@router.post("/{writeup_id}/rate", response_model=WriteupRatingResponse)
backend/app/routers/writeups.py:153:    current_user: User = Depends(get_current_user),
backend/app/routers/writeups.py:154:    db: AsyncSession = Depends(get_db),
backend/app/routers/writeups.py:176:@router.put("/{writeup_id}/approve")
backend/app/routers/writeups.py:179:    admin: User = Depends(require_admin),
backend/app/routers/writeups.py:180:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:7:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/admin.py:22:@router.get("/users")
backend/app/routers/admin.py:24:    page: int = Query(1, ge=1),
backend/app/routers/admin.py:25:    per_page: int = Query(50, ge=1, le=200),
backend/app/routers/admin.py:26:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:27:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:80:@router.put("/users/{user_id}")
backend/app/routers/admin.py:84:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:85:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:108:@router.get("/audit")
backend/app/routers/admin.py:110:    user_id: int | None = Query(None),
backend/app/routers/admin.py:111:    action: str | None = Query(None),
backend/app/routers/admin.py:112:    date_from: str | None = Query(None),
backend/app/routers/admin.py:113:    date_to: str | None = Query(None),
backend/app/routers/admin.py:114:    page: int = Query(1, ge=1),
backend/app/routers/admin.py:115:    per_page: int = Query(50, ge=1, le=200),
backend/app/routers/admin.py:116:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:117:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:145:        select(func.count()).select_from(stmt.subquery())
backend/app/routers/admin.py:174:@router.post("/seed")
backend/app/routers/admin.py:176:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:177:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:237:@router.get("/system")
backend/app/routers/admin.py:239:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:240:    db: AsyncSession = Depends(get_db),
backend/app/routers/admin.py:278:@router.get("/reports/operator/{user_id}")
backend/app/routers/admin.py:281:    admin: User = Depends(require_admin),
backend/app/routers/admin.py:282:    db: AsyncSession = Depends(get_db),
backend/app/routers/leaderboard.py:4:from fastapi import APIRouter, Depends, Query
backend/app/routers/leaderboard.py:19:@router.get("/")
backend/app/routers/leaderboard.py:21:    team: str | None = Query(None),
backend/app/routers/leaderboard.py:22:    current_user: User = Depends(get_current_user),
backend/app/routers/leaderboard.py:23:    db: AsyncSession = Depends(get_db),
backend/app/routers/leaderboard.py:89:@router.get("/teams")
backend/app/routers/leaderboard.py:91:    current_user: User = Depends(get_current_user),
backend/app/routers/leaderboard.py:92:    db: AsyncSession = Depends(get_db),
backend/app/routers/leaderboard.py:132:@router.get("/weekly")
backend/app/routers/leaderboard.py:134:    team: str | None = Query(None),
backend/app/routers/leaderboard.py:135:    current_user: User = Depends(get_current_user),
backend/app/routers/leaderboard.py:136:    db: AsyncSession = Depends(get_db),
backend/app/services/orchestration/egress.py:44:logger = structlog.get_logger()
backend/app/services/orchestration/egress.py:226:        logger.info(
backend/app/services/orchestration/egress.py:233:        logger.warning(
backend/app/services/orchestration/egress.py:276:        logger.warning(
backend/app/routers/competitions.py:3:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/competitions.py:15:@router.post("/")
backend/app/routers/competitions.py:18:    admin: User = Depends(require_admin),
backend/app/routers/competitions.py:19:    db: AsyncSession = Depends(get_db),
backend/app/routers/competitions.py:44:@router.get("/")
backend/app/routers/competitions.py:46:    active: bool | None = Query(None),
backend/app/routers/competitions.py:47:    current_user: User = Depends(get_current_user),
backend/app/routers/competitions.py:48:    db: AsyncSession = Depends(get_db),
backend/app/routers/competitions.py:90:@router.get("/{competition_id}")
backend/app/routers/competitions.py:93:    current_user: User = Depends(get_current_user),
backend/app/routers/competitions.py:94:    db: AsyncSession = Depends(get_db),
backend/app/routers/competitions.py:130:@router.get("/{competition_id}/scoreboard")
backend/app/routers/competitions.py:133:    current_user: User = Depends(get_current_user),
backend/app/routers/competitions.py:134:    db: AsyncSession = Depends(get_db),
backend/app/routers/competitions.py:147:@router.post("/{competition_id}/activate")
backend/app/routers/competitions.py:150:    admin: User = Depends(require_admin),
backend/app/routers/competitions.py:151:    db: AsyncSession = Depends(get_db),
backend/app/services/orchestration/cleanup.py:21:logger = structlog.get_logger()
backend/app/services/orchestration/cleanup.py:79:        logger.warning("container.stop_failed", id=container_id, error=str(exc))
backend/app/services/orchestration/cleanup.py:83:        logger.warning("container.remove_failed", id=container_id, error=str(exc))
backend/app/services/orchestration/cleanup.py:121:            logger.info("instance.cleanup", instance_id=instance.id)
backend/app/services/orchestration/cleanup.py:124:            logger.error(
backend/app/services/orchestration/cleanup.py:157:        logger.warning("orphan_sweep.docker_list_failed", error=str(exc))
backend/app/services/orchestration/cleanup.py:185:            logger.info("instance.orphan_swept", instance_id=inst.id)
backend/app/services/orchestration/cleanup.py:188:            logger.warning(
backend/app/services/orchestration/networking.py:24:logger = structlog.get_logger()
backend/app/services/orchestration/networking.py:31:    return f"siege-ch-{user_id}-{slug}-{secrets.token_hex(4)}"
backend/app/services/orchestration/networking.py:100:    logger.info(
backend/app/services/orchestration/networking.py:116:        logger.warning("network.remove_failed", network=network_name, error=str(exc))
backend/app/services/orchestration/sidecar.py:37:logger = structlog.get_logger()
backend/app/services/orchestration/sidecar.py:90:    return f"{_SIDECAR_NAME_PREFIX}-{safe[:48]}-{secrets.token_hex(3)}"
backend/app/services/orchestration/sidecar.py:117:    logger.info(
backend/app/services/orchestration/sidecar.py:170:        logger.warning(
backend/app/services/orchestration/docker_client.py:19:logger = structlog.get_logger()
backend/app/services/orchestration/docker_client.py:38:            logger.info(
backend/app/services/orchestration/docker_client.py:58:                logger.warning("docker.client.close_failed", error=str(exc))
backend/app/routers/challenges/browse.py:7:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/challenges/browse.py:25:@router.get("/")
backend/app/routers/challenges/browse.py:27:    team: str | None = Query(None),
backend/app/routers/challenges/browse.py:28:    category: str | None = Query(None),
backend/app/routers/challenges/browse.py:29:    difficulty: str | None = Query(None),
backend/app/routers/challenges/browse.py:30:    search: str | None = Query(None),
backend/app/routers/challenges/browse.py:31:    mitre: str | None = Query(None),
backend/app/routers/challenges/browse.py:32:    sort: str = Query("newest"),
backend/app/routers/challenges/browse.py:33:    page: int = Query(1, ge=1),
backend/app/routers/challenges/browse.py:34:    per_page: int = Query(20, ge=1, le=100),
backend/app/routers/challenges/browse.py:35:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/browse.py:36:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/browse.py:54:@router.get("/{slug}")
backend/app/routers/challenges/browse.py:57:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/browse.py:58:    db: AsyncSession = Depends(get_db),
backend/app/services/orchestration/launcher.py:42:logger = structlog.get_logger()
backend/app/services/orchestration/launcher.py:228:        container_name = f"siege-{user_id}-{challenge.slug}-{secrets.token_hex(3)}"
backend/app/services/orchestration/launcher.py:362:                    logger.warning("workstation.attach.audit_failed", error=str(exc))
backend/app/services/orchestration/launcher.py:364:            logger.warning("workstation.attach.skip", error=str(exc))
backend/app/routers/challenges/admin.py:22:@router.post("/")
backend/app/routers/challenges/admin.py:25:    admin: User = Depends(require_admin),
backend/app/routers/challenges/admin.py:26:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/admin.py:66:@router.put("/{slug}")
backend/app/routers/challenges/admin.py:70:    admin: User = Depends(require_admin),
backend/app/routers/challenges/admin.py:71:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/admin.py:114:@router.post("/{slug}/release")
backend/app/routers/challenges/admin.py:118:    admin: User = Depends(require_admin),
backend/app/routers/challenges/admin.py:119:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/admin.py:184:@router.delete("/{slug}")
backend/app/routers/challenges/admin.py:187:    admin: User = Depends(require_admin),
backend/app/routers/challenges/admin.py:188:    db: AsyncSession = Depends(get_db),
backend/app/services/password_reset.py:1:"""Password-reset token issue + redeem.
backend/app/services/password_reset.py:5:The cleartext is returned by :func:`issue_token` once and never
backend/app/services/password_reset.py:7:``password_reset_tokens.token_hash``.
backend/app/services/password_reset.py:10:later attempt with the same token fails validation.
backend/app/services/password_reset.py:36:def _hash_cleartext(token: str) -> str:
backend/app/services/password_reset.py:37:    return hashlib.sha256(token.encode("utf-8")).hexdigest()
backend/app/services/password_reset.py:40:async def issue_token(db: AsyncSession, user: User) -> str:
backend/app/services/password_reset.py:41:    """Generate a fresh single-use token for ``user``.
backend/app/services/password_reset.py:43:    Returns the cleartext token (URL-safe base64) for embedding in
backend/app/services/password_reset.py:45:    ``token_hash`` and TTL controlled by
backend/app/services/password_reset.py:51:    cleartext = secrets.token_urlsafe(32)
backend/app/services/password_reset.py:54:        token_hash=_hash_cleartext(cleartext),
backend/app/services/password_reset.py:65:async def redeem_token(
backend/app/services/password_reset.py:73:    expired, already-used). On success: marks token used, sets
backend/app/services/password_reset.py:78:        raise InvalidResetToken("token missing")
backend/app/services/password_reset.py:82:    token_hash = _hash_cleartext(cleartext)
backend/app/services/password_reset.py:86:                PasswordResetToken.token_hash == token_hash
backend/app/services/password_reset.py:91:        raise InvalidResetToken("token not found")
backend/app/services/password_reset.py:93:        raise InvalidResetToken("token already used")
backend/app/services/password_reset.py:95:        raise InvalidResetToken("token expired")
backend/app/services/password_reset.py:109:__all__ = ["InvalidResetToken", "issue_token", "redeem_token"]
backend/app/routers/challenges/engagement.py:30:@router.post("/{slug}/submit", response_model=FlagResult)
backend/app/routers/challenges/engagement.py:35:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/engagement.py:36:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/engagement.py:37:    _rl=Depends(flag_rate_limit),
backend/app/routers/challenges/engagement.py:63:@router.post("/{slug}/hint")
backend/app/routers/challenges/engagement.py:66:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/engagement.py:67:    db: AsyncSession = Depends(get_db),
backend/app/routers/challenges/engagement.py:120:@router.post("/{slug}/feedback")
backend/app/routers/challenges/engagement.py:124:    current_user: User = Depends(get_current_user),
backend/app/routers/challenges/engagement.py:125:    db: AsyncSession = Depends(get_db),
backend/app/services/scheduler.py:13:logger = structlog.get_logger()
backend/app/services/scheduler.py:42:                logger.info("Cleaned up expired instances", count=count)
backend/app/services/scheduler.py:47:                logger.info("Swept orphan instances", count=orphaned)
backend/app/services/scheduler.py:61:            logger.info("Reaped idle workstations", user_ids=reaped)
backend/app/services/scheduler.py:63:        logger.warning("workstation.reap.job_failed", error=str(exc))
backend/app/services/scheduler.py:77:                logger.info("Submission-burst alerts raised", count=raised)
backend/app/services/scheduler.py:79:        logger.warning("cheat_detector.job_failed", error=str(exc))
backend/app/services/scheduler.py:125:        logger.error("Failed to cache leaderboard", error=str(e))
backend/app/services/scheduler.py:141:            logger.info("Cleaned up old notifications")
backend/app/services/scheduler.py:143:        logger.error("Notification cleanup failed", error=str(e))
backend/app/services/scheduler.py:155:                logger.info(
backend/app/services/scheduler.py:159:        logger.error("Webhook retry failed", error=str(e))
backend/app/services/scheduler.py:185:        logger.error("Audit verify scheduler crashed", error=str(exc))
backend/app/services/scheduler.py:198:        logger.info(
backend/app/services/scheduler.py:205:    logger.error(
backend/app/services/scheduler.py:227:        logger.error("audit_ledger.notify_failed", error=str(exc))
backend/app/services/scheduler.py:246:        logger.info("backup.skipped", reason="BACKUP_DIR empty")
backend/app/services/scheduler.py:258:    logger.error(
backend/app/services/scheduler.py:279:        logger.error("backup.notify_failed", error=str(exc))
backend/app/services/scheduler.py:292:                logger.info(
backend/app/services/scheduler.py:296:        logger.error("Webhook prune failed", error=str(e))
backend/app/services/scheduler.py:331:    logger.info("Scheduler started")
backend/app/routers/challenges/__init__.py:19:router.include_router(browse.router)
backend/app/routers/challenges/__init__.py:20:router.include_router(engagement.router)
backend/app/routers/challenges/__init__.py:21:router.include_router(admin.router)
backend/app/services/backup.py:40:logger = structlog.get_logger()
backend/app/services/backup.py:92:                logger.warning(
backend/app/services/backup.py:177:    logger.info(
backend/app/services/cheat_detector.py:25:* The query is capped at ``BURST_QUERY_LIMIT = 5000`` rows; if
backend/app/services/cheat_detector.py:42:logger = structlog.get_logger()
backend/app/services/cheat_detector.py:74:        logger.warning(
backend/app/services/cheat_detector.py:119:        logger.info(
backend/app/services/flag_submission.py:6:Notification / hash-chained AuditLedger), WebSocket broadcast, and
backend/app/services/flag_submission.py:300:    # all-flags-captured query below.
backend/app/services/webhook_dispatch.py:52:logger = structlog.get_logger()
backend/app/services/webhook_dispatch.py:64:    return _secrets.token_hex(_SECRET_BYTES)
backend/app/services/webhook_dispatch.py:103:    delivery_id = _secrets.token_hex(8)
backend/app/services/webhook_dispatch.py:264:        logger.error(
backend/app/services/webhook_dispatch.py:414:    # subquery uses MAX(attempt) — the rows we want to consider are
backend/app/services/webhook_dispatch.py:425:        .subquery()
backend/app/services/webhook_dispatch.py:474:            logger.error(
backend/app/services/validator_sandbox.py:146:    # platform's structured logger.
backend/app/services/scoreboard_cache.py:5:active user spawns a points + solves + streak query). This wrapper
backend/app/services/scoreboard_cache.py:28:logger = structlog.get_logger()
backend/app/services/scoreboard_cache.py:94:            logger.warning(
backend/app/services/scoreboard_cache.py:100:        logger.warning(
backend/app/services/email.py:39:logger = structlog.get_logger()
backend/app/services/email.py:130:        logger.error(
backend/app/routers/v1/scoreboard.py:8:from fastapi import APIRouter, Depends, Query
backend/app/routers/v1/scoreboard.py:20:@router.get("/scoreboard", response_model=ScoreboardResponse)
backend/app/routers/v1/scoreboard.py:22:    team: Optional[str] = Query(None, pattern="^(red|blue|purple)$"),
backend/app/routers/v1/scoreboard.py:23:    limit: int = Query(100, ge=1, le=500),
backend/app/routers/v1/scoreboard.py:24:    _viewer: User = Depends(get_current_user),
backend/app/routers/v1/scoreboard.py:25:    db: AsyncSession = Depends(get_db),
backend/app/services/email_verification.py:1:"""Email-verification token issue + redeem.
backend/app/services/email_verification.py:32:def _hash_cleartext(token: str) -> str:
backend/app/services/email_verification.py:33:    return hashlib.sha256(token.encode("utf-8")).hexdigest()
backend/app/services/email_verification.py:36:async def issue_token(db: AsyncSession, user: User) -> str:
backend/app/services/email_verification.py:37:    """Generate a fresh single-use verification token.
backend/app/services/email_verification.py:44:    cleartext = secrets.token_urlsafe(32)
backend/app/services/email_verification.py:48:            token_hash=_hash_cleartext(cleartext),
backend/app/services/email_verification.py:59:async def redeem_token(db: AsyncSession, cleartext: str) -> User:
backend/app/services/email_verification.py:67:        raise InvalidVerificationToken("token missing")
backend/app/services/email_verification.py:69:    token_hash = _hash_cleartext(cleartext)
backend/app/services/email_verification.py:73:                EmailVerificationToken.token_hash == token_hash
backend/app/services/email_verification.py:78:        raise InvalidVerificationToken("token not found")
backend/app/services/email_verification.py:80:        raise InvalidVerificationToken("token already used")
backend/app/services/email_verification.py:82:        raise InvalidVerificationToken("token expired")
backend/app/services/email_verification.py:98:    "issue_token",
backend/app/services/email_verification.py:99:    "redeem_token",
backend/app/services/mfa.py:4:secret generation, recovery-code lifecycle, login-step pending-token
backend/app/services/mfa.py:11:The MFA pending token is a short-lived JWT issued during the login
backend/app/services/mfa.py:15:access + refresh tokens.
backend/app/services/mfa.py:33:from app.services.auth import create_access_token, create_refresh_token
backend/app/services/mfa.py:160:    On success: returns the (access_token, refresh_token) pair.
backend/app/services/mfa.py:171:        create_access_token(user.id, user.role.value),
backend/app/services/mfa.py:172:        create_refresh_token(user.id),
backend/app/services/mfa.py:210:# Pending-token plumbing for the two-step login flow
backend/app/services/mfa.py:212:def issue_mfa_pending_token(user_id: int) -> str:
backend/app/services/mfa.py:235:def decode_mfa_pending_token(token: str) -> int:
backend/app/services/mfa.py:236:    """Validate the pending token and return the user_id."""
backend/app/services/mfa.py:243:            token, settings.SECRET_KEY, algorithms=["HS256"]
backend/app/services/mfa.py:246:        raise InvalidMfaCode("invalid pending token") from exc
backend/app/services/mfa.py:248:        raise InvalidMfaCode("wrong token type")
backend/app/services/mfa.py:253:        raise InvalidMfaCode("malformed pending token") from exc
backend/app/services/mfa.py:262:    "decode_mfa_pending_token",
backend/app/services/mfa.py:264:    "issue_mfa_pending_token",
backend/app/routers/v1/webhooks.py:12:from fastapi import APIRouter, Depends, HTTPException, Query, status
backend/app/routers/v1/webhooks.py:38:@router.post(
backend/app/routers/v1/webhooks.py:46:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:47:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:64:@router.get(
backend/app/routers/v1/webhooks.py:70:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:71:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:86:@router.get(
backend/app/routers/v1/webhooks.py:96:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:97:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:103:@router.delete(
backend/app/routers/v1/webhooks.py:114:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:115:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:161:@router.get(
backend/app/routers/v1/webhooks.py:171:    page: int = Query(1, ge=1, le=10_000),
backend/app/routers/v1/webhooks.py:172:    per_page: int = Query(50, ge=1, le=200),
backend/app/routers/v1/webhooks.py:173:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:174:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/webhooks.py:204:@router.post(
backend/app/routers/v1/webhooks.py:216:    admin: User = Depends(require_admin),
backend/app/routers/v1/webhooks.py:217:    db: AsyncSession = Depends(get_db),
backend/app/services/ws_manager.py:6:from fastapi import WebSocket
backend/app/services/ws_manager.py:8:logger = structlog.get_logger()
backend/app/services/ws_manager.py:11:class WebSocketManager:
backend/app/services/ws_manager.py:13:        self.connections: Dict[int, List[WebSocket]] = {}
backend/app/services/ws_manager.py:19:    async def connect(self, websocket: WebSocket, user_id: int):
backend/app/services/ws_manager.py:20:        await websocket.accept()
backend/app/services/ws_manager.py:23:        self.connections[user_id].append(websocket)
backend/app/services/ws_manager.py:24:        logger.info("WebSocket connected", user_id=user_id)
backend/app/services/ws_manager.py:26:    async def disconnect(self, websocket: WebSocket, user_id: int):
backend/app/services/ws_manager.py:29:                self.connections[user_id].remove(websocket)
backend/app/services/ws_manager.py:34:        logger.info("WebSocket disconnected", user_id=user_id)
backend/app/services/ws_manager.py:43:                logger.error("Redis publish failed", error=str(e))
backend/app/services/ws_manager.py:80:                        logger.error("Redis listener error", error=str(e))
backend/app/services/ws_manager.py:84:            logger.error("Redis listener crashed", error=str(e))
backend/app/services/ws_manager.py:87:ws_manager = WebSocketManager()
backend/app/services/workstation.py:33:logger = structlog.get_logger()
backend/app/services/workstation.py:120:        logger.info("workstation.launch.already_running", user_id=user_id)
backend/app/services/workstation.py:133:        logger.info("workstation.launch.swept_stale", user_id=user_id, container=name)
backend/app/services/workstation.py:176:    logger.info(
backend/app/services/workstation.py:212:        logger.info(
backend/app/services/workstation.py:218:        logger.warning(
backend/app/services/workstation.py:243:        logger.warning("workstation.reap.list_failed", error=str(exc))
backend/app/services/workstation.py:262:            logger.info(
backend/app/services/workstation.py:268:            logger.warning("workstation.reap.failed", user_id=uid, error=str(exc))
backend/app/services/workstation.py:287:    logger.info("workstation.stop.ok", user_id=user_id)
backend/app/routers/v1/__init__.py:40:router.include_router(auth.router)
backend/app/routers/v1/__init__.py:41:router.include_router(admin.router)
backend/app/routers/v1/__init__.py:42:router.include_router(challenges.router)
backend/app/routers/v1/__init__.py:43:router.include_router(scoreboard.router)
backend/app/routers/v1/__init__.py:44:router.include_router(leaderboard.router)
backend/app/routers/v1/__init__.py:45:router.include_router(attack_coverage.router)
backend/app/routers/v1/__init__.py:46:router.include_router(me.router)
backend/app/routers/v1/__init__.py:47:router.include_router(submit.router)
backend/app/routers/v1/__init__.py:48:router.include_router(hints.router)
backend/app/routers/v1/__init__.py:49:router.include_router(progress.router)
backend/app/routers/v1/__init__.py:50:router.include_router(webhooks.router)
backend/app/routers/v1/__init__.py:51:router.include_router(workstation.router)
backend/app/routers/ws.py:4:from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
backend/app/routers/ws.py:6:from app.services.auth import decode_token
backend/app/routers/ws.py:9:router = APIRouter(tags=["websocket"])
backend/app/routers/ws.py:12:@router.websocket("/ws")
backend/app/routers/ws.py:13:async def websocket_endpoint(
backend/app/routers/ws.py:14:    websocket: WebSocket,
backend/app/routers/ws.py:15:    token: str = Query(None),
backend/app/routers/ws.py:17:    if not token:
backend/app/routers/ws.py:18:        await websocket.close(code=4001, reason="Missing authentication token")
backend/app/routers/ws.py:22:        payload = decode_token(token)
backend/app/routers/ws.py:25:            await websocket.close(code=4001, reason="Invalid token")
backend/app/routers/ws.py:28:        await websocket.close(code=4001, reason="Invalid or expired token")
backend/app/routers/ws.py:31:    await ws_manager.connect(websocket, user_id)
backend/app/routers/ws.py:33:    heartbeat_task = asyncio.create_task(_heartbeat(websocket))
backend/app/routers/ws.py:37:            data = await websocket.receive_text()
backend/app/routers/ws.py:43:                await websocket.send_json({"type": "pong"})
backend/app/routers/ws.py:44:    except WebSocketDisconnect:
backend/app/routers/ws.py:50:        await ws_manager.disconnect(websocket, user_id)
backend/app/routers/ws.py:53:async def _heartbeat(websocket: WebSocket):
backend/app/routers/ws.py:58:                await websocket.send_json({"type": "ping"})
backend/app/routers/v1/progress.py:30:@router.get(
backend/app/routers/v1/progress.py:37:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/progress.py:38:    db: AsyncSession = Depends(get_db),
backend/app/routers/health.py:32:logger = structlog.get_logger()
backend/app/routers/health.py:43:@router.get("/health")
backend/app/routers/health.py:133:@router.get("/readyz")
backend/app/routers/health.py:145:@router.get("/metrics", include_in_schema=False)
backend/app/routers/health.py:166:_CSP_LOG = structlog.get_logger("siege_range.csp")
backend/app/routers/health.py:169:@router.post("/csp-report", include_in_schema=False)
backend/app/routers/stats.py:3:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/stats.py:14:@router.get("/overview")
backend/app/routers/stats.py:16:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:17:    db: AsyncSession = Depends(get_db),
backend/app/routers/stats.py:90:@router.get("/mitre")
backend/app/routers/stats.py:92:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:93:    db: AsyncSession = Depends(get_db),
backend/app/routers/stats.py:140:@router.get("/activity")
backend/app/routers/stats.py:142:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:143:    db: AsyncSession = Depends(get_db),
backend/app/routers/stats.py:178:@router.get("/user/{user_id}")
backend/app/routers/stats.py:181:    current_user: User = Depends(get_current_user),
backend/app/routers/stats.py:182:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/submit.py:39:@router.post(
backend/app/routers/v1/submit.py:53:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/submit.py:54:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/submit.py:55:    _rl=Depends(flag_rate_limit),
backend/app/routers/v1/auth.py:10:- ``POST /api/v1/auth/register`` — create user, return token pair.
backend/app/routers/v1/auth.py:11:- ``POST /api/v1/auth/login``    — authenticate, return token pair.
backend/app/routers/v1/auth.py:12:- ``POST /api/v1/auth/refresh``  — exchange refresh token for new access.
backend/app/routers/v1/auth.py:13:- ``POST /api/v1/auth/logout``   — revoke refresh token (best-effort).
backend/app/routers/v1/auth.py:16:Audit-ledger emit, account lockout, and refresh-token blacklist
backend/app/routers/v1/auth.py:64:    decode_mfa_pending_token,
backend/app/routers/v1/auth.py:66:    issue_mfa_pending_token,
backend/app/routers/v1/auth.py:75:    create_access_token,
backend/app/routers/v1/auth.py:76:    create_refresh_token,
backend/app/routers/v1/auth.py:77:    decode_token,
backend/app/routers/v1/auth.py:113:@router.post(
backend/app/routers/v1/auth.py:122:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:161:    # Sprint 9 Phase B — issue an email-verification token and email
backend/app/routers/v1/auth.py:167:        issue_token as issue_verify_token,
backend/app/routers/v1/auth.py:172:        cleartext = await issue_verify_token(db, user)
backend/app/routers/v1/auth.py:175:            f"?token={cleartext}"
backend/app/routers/v1/auth.py:201:        # Don't fail register if SMTP / token issue blew up; the
backend/app/routers/v1/auth.py:209:        access_token=create_access_token(user.id, user.role.value),
backend/app/routers/v1/auth.py:210:        refresh_token=create_refresh_token(user.id),
backend/app/routers/v1/auth.py:214:@router.post(
backend/app/routers/v1/auth.py:218:        200: {"description": "Login success — token pair OR MFA pending"},
backend/app/routers/v1/auth.py:227:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:228:    redis_client=Depends(_get_redis),
backend/app/routers/v1/auth.py:235:        ``{user, access_token, refresh_token, token_type}``).
backend/app/routers/v1/auth.py:237:        (``{mfa_required: true, mfa_pending_token: "..."}``). The
backend/app/routers/v1/auth.py:239:        pending token + the user's TOTP / recovery code to receive
backend/app/routers/v1/auth.py:240:        the real token pair.
backend/app/routers/v1/auth.py:306:    # pending token instead of the real pair. Login still counts as
backend/app/routers/v1/auth.py:326:            mfa_pending_token=issue_mfa_pending_token(user.id),
backend/app/routers/v1/auth.py:344:        access_token=create_access_token(user.id, user.role.value),
backend/app/routers/v1/auth.py:345:        refresh_token=create_refresh_token(user.id),
backend/app/routers/v1/auth.py:349:@router.post(
backend/app/routers/v1/auth.py:352:    responses={401: {"description": "Invalid or revoked refresh token"}},
backend/app/routers/v1/auth.py:357:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:358:    redis_client=Depends(_get_redis),
backend/app/routers/v1/auth.py:360:    token = payload.refresh_token
backend/app/routers/v1/auth.py:362:    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
backend/app/routers/v1/auth.py:367:        decoded = decode_token(token)
backend/app/routers/v1/auth.py:371:        raise HTTPException(status_code=401, detail="Invalid token")
backend/app/routers/v1/auth.py:374:        raise HTTPException(status_code=401, detail="Invalid token type")
backend/app/routers/v1/auth.py:379:        raise HTTPException(status_code=401, detail="Invalid token")
backend/app/routers/v1/auth.py:386:    new_access = create_access_token(user.id, user.role.value)
backend/app/routers/v1/auth.py:398:    return AuthRefreshResponse(access_token=new_access)
backend/app/routers/v1/auth.py:401:@router.post("/logout", response_model=AuthLogoutResponse)
backend/app/routers/v1/auth.py:405:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:406:    redis_client=Depends(_get_redis),
backend/app/routers/v1/auth.py:408:    token = payload.refresh_token
backend/app/routers/v1/auth.py:410:    if token:
backend/app/routers/v1/auth.py:412:            decoded = decode_token(token)
backend/app/routers/v1/auth.py:417:                    f"siege:blacklist:{token}", "1", ex=ttl
backend/app/routers/v1/auth.py:435:        payload={"token_revoked": bool(token)},
backend/app/routers/v1/auth.py:442:@router.get("/me", response_model=AuthUser)
backend/app/routers/v1/auth.py:444:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:452:@router.post(
backend/app/routers/v1/auth.py:461:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:463:    """Issue a password-reset token and email the link.
backend/app/routers/v1/auth.py:478:    from app.services.password_reset import issue_token
backend/app/routers/v1/auth.py:488:        cleartext = await issue_token(db, user)
backend/app/routers/v1/auth.py:491:            f"?token={cleartext}"
backend/app/routers/v1/auth.py:545:@router.post(
backend/app/routers/v1/auth.py:548:    responses={400: {"description": "Invalid or expired reset token"}},
backend/app/routers/v1/auth.py:553:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:555:    """Redeem a reset token and set a new password."""
backend/app/routers/v1/auth.py:565:        redeem_token,
backend/app/routers/v1/auth.py:569:        user = await redeem_token(db, payload.token, payload.new_password)
backend/app/routers/v1/auth.py:585:            status_code=400, detail="invalid or expired token"
backend/app/routers/v1/auth.py:605:@router.post(
backend/app/routers/v1/auth.py:613:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:614:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:647:@router.patch("/profile", response_model=AuthUser)
backend/app/routers/v1/auth.py:651:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:652:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:687:@router.post(
backend/app/routers/v1/auth.py:696:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:697:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:725:@router.post(
backend/app/routers/v1/auth.py:736:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:737:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:780:@router.post(
backend/app/routers/v1/auth.py:792:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:793:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:841:@router.post(
backend/app/routers/v1/auth.py:845:        401: {"description": "Pending token invalid or code rejected"},
backend/app/routers/v1/auth.py:851:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:855:    Consumes the pending token from ``/auth/login`` (response body
backend/app/routers/v1/auth.py:857:    code). Returns the real access + refresh token pair on
backend/app/routers/v1/auth.py:864:        user_id = decode_mfa_pending_token(payload.mfa_pending_token)
backend/app/routers/v1/auth.py:904:        access_token=access,
backend/app/routers/v1/auth.py:905:        refresh_token=refresh,
backend/app/routers/v1/auth.py:912:@router.post(
backend/app/routers/v1/auth.py:915:    responses={400: {"description": "Invalid or expired token"}},
backend/app/routers/v1/auth.py:920:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:922:    """Redeem an email-verification token and flip
backend/app/routers/v1/auth.py:927:        redeem_token,
backend/app/routers/v1/auth.py:931:        user = await redeem_token(db, payload.token)
backend/app/routers/v1/auth.py:945:            status_code=400, detail="invalid or expired token"
backend/app/routers/v1/auth.py:962:@router.post(
backend/app/routers/v1/auth.py:969:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/auth.py:970:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/auth.py:972:    """Issue a new verification token and email the link.
backend/app/routers/v1/auth.py:980:        issue_token as issue_verify_token,
backend/app/routers/v1/auth.py:985:        cleartext = await issue_verify_token(db, current_user)
backend/app/routers/v1/auth.py:988:            f"?token={cleartext}"
backend/app/routers/instances.py:50:@router.post("/{slug}/launch")
backend/app/routers/instances.py:54:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:55:    db: AsyncSession = Depends(get_db),
backend/app/routers/instances.py:56:    redis_client=Depends(get_redis),
backend/app/routers/instances.py:111:@router.delete("/{instance_id}")
backend/app/routers/instances.py:115:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:116:    db: AsyncSession = Depends(get_db),
backend/app/routers/instances.py:117:    redis_client=Depends(get_redis),
backend/app/routers/instances.py:149:@router.get("/")
backend/app/routers/instances.py:151:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:152:    db: AsyncSession = Depends(get_db),
backend/app/routers/instances.py:196:@router.post("/{instance_id}/reset")
backend/app/routers/instances.py:200:    current_user: User = Depends(get_current_user),
backend/app/routers/instances.py:201:    db: AsyncSession = Depends(get_db),
backend/app/routers/instances.py:202:    redis_client=Depends(get_redis),
backend/app/routers/v1/leaderboard.py:21:from fastapi import APIRouter, Depends, Query
backend/app/routers/v1/leaderboard.py:39:@router.get("/leaderboard/teams", response_model=TeamLeaderboardResponse)
backend/app/routers/v1/leaderboard.py:41:    _viewer: User = Depends(get_current_user),
backend/app/routers/v1/leaderboard.py:42:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/leaderboard.py:85:@router.get("/leaderboard/weekly", response_model=WeeklyLeaderboardResponse)
backend/app/routers/v1/leaderboard.py:87:    team: Optional[str] = Query(None, pattern="^(red|blue)$"),
backend/app/routers/v1/leaderboard.py:88:    limit: int = Query(100, ge=1, le=500),
backend/app/routers/v1/leaderboard.py:89:    _viewer: User = Depends(get_current_user),
backend/app/routers/v1/leaderboard.py:90:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/hints.py:28:@router.post(
backend/app/routers/v1/hints.py:38:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/hints.py:39:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/challenges.py:15:from fastapi import APIRouter, Depends, HTTPException, Query
backend/app/routers/v1/challenges.py:39:@router.get("/challenges", response_model=PublicChallengeListResponse)
backend/app/routers/v1/challenges.py:41:    team: Optional[str] = Query(None),
backend/app/routers/v1/challenges.py:42:    category: Optional[str] = Query(None),
backend/app/routers/v1/challenges.py:43:    difficulty: Optional[str] = Query(None),
backend/app/routers/v1/challenges.py:44:    search: Optional[str] = Query(None, max_length=200),
backend/app/routers/v1/challenges.py:45:    mitre: Optional[str] = Query(None, max_length=16),
backend/app/routers/v1/challenges.py:46:    sort: str = Query("newest", pattern="^(newest|points|difficulty|solves)$"),
backend/app/routers/v1/challenges.py:47:    page: int = Query(1, ge=1, le=10_000),
backend/app/routers/v1/challenges.py:48:    per_page: int = Query(20, ge=1, le=100),
backend/app/routers/v1/challenges.py:49:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/challenges.py:50:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/challenges.py:71:@router.get("/challenges/{slug}", response_model=PublicChallengeDetail)
backend/app/routers/v1/challenges.py:74:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/challenges.py:75:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/attack_coverage.py:17:@router.get("/attack-coverage", response_model=AttackCoverageResponse)
backend/app/routers/v1/attack_coverage.py:19:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/attack_coverage.py:20:    db: AsyncSession = Depends(get_db),
backend/app/services/audit/events.py:9:strings, so the chain remains queryable by a known vocabulary.
backend/app/routers/v1/workstation.py:108:@router.get("/status", response_model=WorkstationStatus)
backend/app/routers/v1/workstation.py:111:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/workstation.py:119:@router.post("/launch", response_model=WorkstationLaunchResponse)
backend/app/routers/v1/workstation.py:122:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/workstation.py:123:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/workstation.py:170:@router.post("/stop", response_model=WorkstationStatus)
backend/app/routers/v1/workstation.py:173:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/workstation.py:174:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:92:@router.post(
backend/app/routers/v1/admin.py:103:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:104:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:142:@router.put(
backend/app/routers/v1/admin.py:155:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:156:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:205:@router.post(
backend/app/routers/v1/admin.py:216:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:217:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:281:@router.delete(
backend/app/routers/v1/admin.py:291:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:292:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:309:@router.get(
backend/app/routers/v1/admin.py:319:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:320:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:368:@router.post(
backend/app/routers/v1/admin.py:381:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:382:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:443:@router.put(
backend/app/routers/v1/admin.py:454:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:455:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/admin.py:480:@router.post(
backend/app/routers/v1/admin.py:489:    admin: User = Depends(require_admin),
backend/app/routers/v1/admin.py:490:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/me.py:46:@router.get("/me", response_model=MeResponse)
backend/app/routers/v1/me.py:48:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/me.py:49:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/me.py:90:@router.get("/me/data")
backend/app/routers/v1/me.py:93:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/me.py:94:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/me.py:182:@router.delete("/me", response_model=AccountDeleteResponse)
backend/app/routers/v1/me.py:186:    current_user: User = Depends(get_current_user),
backend/app/routers/v1/me.py:187:    db: AsyncSession = Depends(get_db),
backend/app/routers/v1/me.py:205:    Pending password-reset tokens for the user are deleted.
backend/app/routers/v1/me.py:208:    drive-by deletes via stolen access tokens.
backend/app/routers/v1/me.py:218:    current_user.hashed_password = hash_password(secrets.token_hex(32))

exec
/bin/bash -lc "rg -n \"TODO|FIXME|verify_password|create_access_token|HttpUrl|url|target_url|subprocess|docker|shell=True|eval\\(|pickle|yaml\\.load|secret|password|token|Depends\\(get_current_admin|is_admin|role|CORS|allow_origins|TrustedHost|csrf|cookie|set_cookie|request\\.client\\.host\" backend/app/routers backend/app/services" in /data/projects/seige-range
 succeeded in 0ms:
backend/app/services/validator_registry.py:17:Sandboxing — ``asyncio.timeout`` enforcement, subprocess pool — lives
backend/app/routers/auth.py:17:    create_access_token,
backend/app/routers/auth.py:18:    create_refresh_token,
backend/app/routers/auth.py:19:    decode_token,
backend/app/routers/auth.py:21:    hash_password,
backend/app/routers/auth.py:23:    verify_password,
backend/app/routers/auth.py:35:    r = aioredis.from_url(settings.REDIS_URL)
backend/app/routers/auth.py:50:    password = data.password
backend/app/routers/auth.py:63:        hashed_password=hash_password(password),
backend/app/routers/auth.py:87:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:88:    refresh_token = create_refresh_token(user.id)
backend/app/routers/auth.py:97:            "role": user.role.value,
backend/app/routers/auth.py:101:        "access_token": access_token,
backend/app/routers/auth.py:102:        "refresh_token": refresh_token,
backend/app/routers/auth.py:114:    password = data.password
backend/app/routers/auth.py:122:    if not user or not verify_password(password, user.hashed_password):
backend/app/routers/auth.py:134:                "reason": "bad_password" if user else "unknown_user",
backend/app/routers/auth.py:169:    access_token = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:170:    refresh_token = create_refresh_token(user.id)
backend/app/routers/auth.py:179:            "role": user.role.value,
backend/app/routers/auth.py:184:        "access_token": access_token,
backend/app/routers/auth.py:185:        "refresh_token": refresh_token,
backend/app/routers/auth.py:196:    token = data.refresh_token
backend/app/routers/auth.py:198:    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
backend/app/routers/auth.py:202:    payload = decode_token(token)
backend/app/routers/auth.py:204:        raise HTTPException(status_code=401, detail="Invalid token type")
backend/app/routers/auth.py:212:    new_access = create_access_token(user.id, user.role.value)
backend/app/routers/auth.py:224:    return {"access_token": new_access, "token_type": "bearer"}
backend/app/routers/auth.py:234:    token = data.refresh_token
backend/app/routers/auth.py:236:    if token:
backend/app/routers/auth.py:238:            payload = decode_token(token)
backend/app/routers/auth.py:242:                await redis_client.set(f"siege:blacklist:{token}", "1", ex=ttl)
backend/app/routers/auth.py:258:        payload={"token_revoked": bool(token)},
backend/app/routers/auth.py:299:        "role": current_user.role.value,
backend/app/services/auth.py:21:def hash_password(password: str) -> str:
backend/app/services/auth.py:22:    return pwd_context.hash(password)
backend/app/services/auth.py:25:def verify_password(plain_password: str, hashed_password: str) -> bool:
backend/app/services/auth.py:26:    return pwd_context.verify(plain_password, hashed_password)
backend/app/services/auth.py:29:def create_access_token(user_id: int, role: str) -> str:
backend/app/services/auth.py:33:        "role": role,
backend/app/services/auth.py:40:def create_refresh_token(user_id: int) -> str:
backend/app/services/auth.py:50:def decode_token(token: str) -> dict:
backend/app/services/auth.py:52:        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
backend/app/services/auth.py:57:            detail="Invalid or expired token",
backend/app/services/auth.py:70:    payload = decode_token(credentials.credentials)
backend/app/services/auth.py:74:            detail="Invalid token type",
backend/app/services/auth.py:88:    if current_user.role.value != "admin":
backend/app/routers/admin.py:67:                "role": user.role,
backend/app/routers/admin.py:102:        "role": user.role,
backend/app/routers/admin.py:256:        import docker
backend/app/routers/admin.py:258:        client = docker.from_env()
backend/app/routers/leaderboard.py:26:    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
backend/app/services/orchestration/profiles.py:32:    All fields are intentionally final; the launcher composes docker-py
backend/app/services/orchestration/profiles.py:39:    mem_limit: str  # docker-py format, e.g. "512m"
backend/app/services/orchestration/egress.py:4:deployment-wide allowlist at ``docker/egress-proxy/egress-allowlist.conf``
backend/app/services/orchestration/egress.py:7:into ``Challenge.docker_config["egress_allowlist"]`` and persisted on
backend/app/services/orchestration/egress.py:141:    challenge ``docker_config["egress_allowlist"]`` ride along.
backend/app/services/orchestration/egress.py:163:            (challenge.docker_config or {}).get("egress_allowlist") or []
backend/app/services/orchestration/egress.py:204:    docker_client_obj,
backend/app/services/orchestration/egress.py:212:    on any failure (container missing, signal rejected, docker socket
backend/app/services/orchestration/egress.py:218:    The docker-socket-proxy ACL needs ``CONTAINERS=1`` + ``POST=1``
backend/app/services/orchestration/egress.py:224:        container = docker_client_obj.containers.get(proxy_container_name)
backend/app/services/orchestration/egress.py:243:    docker_client_obj=None,
backend/app/services/orchestration/egress.py:283:    # Only signal if we got a real docker client. Tests pass a stub;
backend/app/services/orchestration/egress.py:285:    if docker_client_obj is not None:
backend/app/services/orchestration/egress.py:287:            docker_client_obj, proxy_container_name=proxy_container_name
backend/app/services/orchestration/cleanup.py:12:import docker
backend/app/services/orchestration/cleanup.py:19:from app.services.orchestration import docker_client, networking
backend/app/services/orchestration/cleanup.py:38:    client = docker_client.get()
backend/app/services/orchestration/cleanup.py:69:def _stop_container(client: docker.DockerClient, container_id: str | None) -> None:
backend/app/services/orchestration/cleanup.py:74:    except docker.errors.NotFound:
backend/app/services/orchestration/cleanup.py:78:    except docker.errors.APIError as exc:
backend/app/services/orchestration/cleanup.py:82:    except docker.errors.APIError as exc:
backend/app/services/orchestration/cleanup.py:139:    ``docker.containers.list()`` plus one SELECT.
backend/app/services/orchestration/cleanup.py:141:    from app.services.orchestration import docker_client
backend/app/services/orchestration/cleanup.py:153:        client = docker_client.get()
backend/app/services/orchestration/cleanup.py:157:        logger.warning("orphan_sweep.docker_list_failed", error=str(exc))
backend/app/services/orchestration/cleanup.py:219:        client = docker_client.get()
backend/app/services/orchestration/cleanup.py:223:            "docker_status": container.status,
backend/app/services/orchestration/cleanup.py:227:        return {"docker_status": "unknown"}
backend/app/services/workstation.py:18:**one-shot password** that the player must capture; if they lose
backend/app/services/workstation.py:24:import secrets
backend/app/services/workstation.py:31:from app.services.orchestration import docker_client
backend/app/services/workstation.py:39:# Network the workstation joins. ``None`` ⇒ docker's default
backend/app/services/workstation.py:62:def _new_password() -> str:
backend/app/services/workstation.py:64:    return "".join(secrets.choice(alphabet) for _ in range(PASSWORD_LEN))
backend/app/services/workstation.py:77:    one_shot_password: Optional[str] = None
backend/app/services/workstation.py:93:    client = docker_client.get()
backend/app/services/workstation.py:116:    password (the caller already has it from the original launch).
backend/app/services/workstation.py:123:    client = docker_client.get()
backend/app/services/workstation.py:137:    password = _new_password()
backend/app/services/workstation.py:150:            "SIEGE_WORKSTATION_PASSWORD": password,
backend/app/services/workstation.py:188:        one_shot_password=password,
backend/app/services/workstation.py:197:    and swallows any docker-side failure — workstation attachment
backend/app/services/workstation.py:201:    client = docker_client.get()
backend/app/services/workstation.py:229:    Called from the scheduler on an hourly interval. The home
backend/app/services/workstation.py:235:    client = docker_client.get()
backend/app/services/workstation.py:274:    client = docker_client.get()
backend/app/routers/challenges/admin.py:46:        docker_image=data.docker_image,
backend/app/routers/challenges/admin.py:47:        docker_port=data.docker_port,
backend/app/routers/challenges/admin.py:48:        docker_config=data.docker_config,
backend/app/services/orchestration/networking.py:4:docker bridge per instance and attaches only the challenge container.
backend/app/services/orchestration/networking.py:9:The egress-proxy container is created out-of-band by docker-compose
backend/app/services/orchestration/networking.py:18:import secrets
backend/app/services/orchestration/networking.py:21:import docker
backend/app/services/orchestration/networking.py:31:    return f"siege-ch-{user_id}-{slug}-{secrets.token_hex(4)}"
backend/app/services/orchestration/networking.py:35:    client: docker.DockerClient,
backend/app/services/orchestration/networking.py:54:    Returns the docker-py ``Network`` object. Caller is responsible for
backend/app/services/orchestration/networking.py:88:def _attach_egress_proxy(client: docker.DockerClient, network) -> None:
backend/app/services/orchestration/networking.py:95:    except docker.errors.NotFound as exc:
backend/app/services/orchestration/networking.py:107:def remove_network(client: docker.DockerClient, network_name: str) -> None:
backend/app/services/orchestration/networking.py:111:    except docker.errors.NotFound:
backend/app/services/orchestration/networking.py:115:    except docker.errors.APIError as exc:
backend/app/services/orchestration/forbidden.py:1:"""Refusal layer: reject docker-py kwargs that would break the sandbox.
backend/app/services/orchestration/forbidden.py:16:    """A docker-py kwarg violates the sandbox boundary."""
backend/app/services/orchestration/forbidden.py:48:    "/var/run/docker.sock",
backend/app/services/orchestration/forbidden.py:91:        # docker-py accepts list form for read-only binds; refuse the legacy
backend/app/services/orchestration/forbidden.py:108:    The launcher calls this after composing the final docker-py kwargs
backend/app/services/orchestrator.py:11:    get_docker_client,
backend/app/services/orchestrator.py:19:    "get_docker_client",
backend/app/services/orchestration/sidecar.py:28:import secrets
backend/app/services/orchestration/sidecar.py:44:_SIDECAR_LABEL_KEY = "siege.role"
backend/app/services/orchestration/sidecar.py:55:    listen_url: str  # http://<container_name>:<port>
backend/app/services/orchestration/sidecar.py:90:    return f"{_SIDECAR_NAME_PREFIX}-{safe[:48]}-{secrets.token_hex(3)}"
backend/app/services/orchestration/sidecar.py:94:    docker_client_obj,
backend/app/services/orchestration/sidecar.py:109:    challenge-container errors). On a docker-py error here, the
backend/app/services/orchestration/sidecar.py:124:    container = docker_client_obj.containers.run(
backend/app/services/orchestration/sidecar.py:146:        listen_url=f"http://{container_name}:{SIDECAR_LISTEN_PORT}",
backend/app/services/orchestration/sidecar.py:151:    docker_client_obj,
backend/app/services/orchestration/sidecar.py:157:    any failure (container already gone, docker socket flapping). The
backend/app/services/orchestration/sidecar.py:165:        container = docker_client_obj.containers.get(container_id)
backend/app/services/orchestration/docker_client.py:1:"""Long-lived Docker client wired through the docker-socket-proxy.
backend/app/services/orchestration/docker_client.py:14:import docker
backend/app/services/orchestration/docker_client.py:22:_client: Optional[docker.DockerClient] = None
backend/app/services/orchestration/docker_client.py:26:def get() -> docker.DockerClient:
backend/app/services/orchestration/docker_client.py:34:            _client = docker.DockerClient(
backend/app/services/orchestration/docker_client.py:35:                base_url=settings.DOCKER_HOST,
backend/app/services/orchestration/docker_client.py:39:                "docker.client.connected",
backend/app/services/orchestration/docker_client.py:40:                base_url=settings.DOCKER_HOST,
backend/app/services/orchestration/docker_client.py:58:                logger.warning("docker.client.close_failed", error=str(exc))
backend/app/services/orchestration/docker_client.py:62:def set_for_test(client: Optional[docker.DockerClient]) -> None:
backend/app/services/scheduler.py:37:    redis_client = aioredis.from_url(settings.REDIS_URL)
backend/app/services/scheduler.py:43:            # Reconcile orphans whose docker container vanished
backend/app/services/scheduler.py:53:    """Hourly: stop workstations whose uptime exceeds the idle
backend/app/services/scheduler.py:87:    redis_client = aioredis.from_url(settings.REDIS_URL)
backend/app/services/scheduler.py:250:        database_url=settings.DATABASE_URL,
backend/app/services/scheduler.py:311:    # Sprint 10 Phase B — hourly audit-ledger tamper sweep.
backend/app/services/orchestration/launcher.py:9:    * Profile lookup: ``challenge.docker_config["profile"]`` keyed
backend/app/services/orchestration/launcher.py:12:    * Digest enforcement: ``challenge.docker_config["digest"]`` must
backend/app/services/orchestration/launcher.py:16:      on a profile-managed field. The launcher composes its docker-py
backend/app/services/orchestration/launcher.py:27:import secrets
backend/app/services/orchestration/launcher.py:31:import docker
backend/app/services/orchestration/launcher.py:39:from app.services.orchestration import docker_client, networking, profiles
backend/app/services/orchestration/launcher.py:62:    ``docker-py`` resolving an ``image@digest`` reference and the
backend/app/services/orchestration/launcher.py:72:    name = (challenge.docker_config or {}).get("profile", "default-strict")
backend/app/services/orchestration/launcher.py:77:    digest = (challenge.docker_config or {}).get("digest")
backend/app/services/orchestration/launcher.py:122:    base = challenge.docker_image
backend/app/services/orchestration/launcher.py:198:        "ports": {f"{challenge.docker_port}/tcp": host_port},
backend/app/services/orchestration/launcher.py:228:        container_name = f"siege-{user_id}-{challenge.slug}-{secrets.token_hex(3)}"
backend/app/services/orchestration/launcher.py:229:        client = docker_client.get()
backend/app/services/orchestration/launcher.py:250:                (challenge.docker_config or {}).get("egress_allowlist") or []
backend/app/services/orchestration/launcher.py:264:        image_ref = _image_ref(challenge, digest) if digest else challenge.docker_image
backend/app/routers/v1/webhooks.py:3:Phase 12 (slice 5). All endpoints require admin role via
backend/app/routers/v1/webhooks.py:5:generated signing secret **once**; subsequent reads omit it.
backend/app/routers/v1/webhooks.py:30:    generate_subscription_secret,
backend/app/routers/v1/webhooks.py:42:    responses={403: {"description": "Admin role required"}},
backend/app/routers/v1/webhooks.py:49:    secret = generate_subscription_secret()
backend/app/routers/v1/webhooks.py:53:        target_url=str(payload.target_url),
backend/app/routers/v1/webhooks.py:54:        secret=secret,
backend/app/routers/v1/webhooks.py:61:    return _to_created(sub, secret)
backend/app/routers/v1/webhooks.py:67:    responses={403: {"description": "Admin role required"}},
backend/app/routers/v1/webhooks.py:90:        403: {"description": "Admin role required"},
backend/app/routers/v1/webhooks.py:108:        403: {"description": "Admin role required"},
backend/app/routers/v1/webhooks.py:142:        target_url=sub.target_url,
backend/app/routers/v1/webhooks.py:152:def _to_created(sub: WebhookSubscription, secret: str) -> WebhookCreatedResponse:
backend/app/routers/v1/webhooks.py:154:    base["secret"] = secret
backend/app/routers/v1/webhooks.py:165:        403: {"description": "Admin role required"},
backend/app/routers/v1/webhooks.py:209:        403: {"description": "Admin role required"},
backend/app/services/orchestration/__init__.py:8:from app.services.orchestration import docker_client, networking, profiles
backend/app/services/orchestration/__init__.py:30:def get_docker_client():
backend/app/services/orchestration/__init__.py:32:    return docker_client.get()
backend/app/services/orchestration/__init__.py:43:    "docker_client",
backend/app/services/orchestration/__init__.py:45:    "get_docker_client",
backend/app/services/validator_sandbox.py:17:   ``requires_subprocess=True`` (Phase 10's yara/sigma) run inside a
backend/app/services/validator_sandbox.py:46:# Per-call resource ceilings for the subprocess sandbox. CPU is the
backend/app/services/validator_sandbox.py:84:    if validator.requires_subprocess:
backend/app/services/validator_sandbox.py:85:        return await run_validator_subprocess(
backend/app/services/validator_sandbox.py:103:async def run_validator_subprocess(
backend/app/services/validator_sandbox.py:111:    """Run a ``requires_subprocess=True`` validator under rlimits.
backend/app/services/validator_sandbox.py:113:    Spawns ``python -m app.services.validator_subprocess_runner`` with
backend/app/services/validator_sandbox.py:129:            "subprocess sandbox requires a POSIX host (resource.setrlimit "
backend/app/services/validator_sandbox.py:147:    # We pass an explicit, minimal env (see ``_subprocess_env``) so
backend/app/services/validator_sandbox.py:153:    proc = await asyncio.create_subprocess_exec(
backend/app/services/validator_sandbox.py:157:        "app.services.validator_subprocess_runner",
backend/app/services/validator_sandbox.py:158:        stdin=asyncio.subprocess.PIPE,
backend/app/services/validator_sandbox.py:159:        stdout=asyncio.subprocess.PIPE,
backend/app/services/validator_sandbox.py:160:        stderr=asyncio.subprocess.PIPE,
backend/app/services/validator_sandbox.py:161:        env=_subprocess_env(),
backend/app/services/validator_sandbox.py:175:            f"validator {validator.name!r} subprocess exceeded "
backend/app/services/validator_sandbox.py:184:            f"validator {validator.name!r} subprocess killed by signal "
backend/app/services/validator_sandbox.py:190:            f"validator {validator.name!r} subprocess produced no output "
backend/app/services/validator_sandbox.py:198:            f"validator {validator.name!r} subprocess returned malformed "
backend/app/services/validator_sandbox.py:211:    message = str(response.get("message", "unknown subprocess error"))
backend/app/services/validator_sandbox.py:243:def _subprocess_env() -> dict[str, str]:
backend/app/services/validator_sandbox.py:246:    Drops every secret / connection-string we know about; preserves
backend/app/services/validator_sandbox.py:329:    "run_validator_subprocess",
backend/app/services/email.py:3:Sprint 6. Used by the password-reset flow today; will host
backend/app/services/email.py:23:back to the client (the password-reset endpoint maps
backend/app/services/email.py:126:            password=settings.SMTP_PASSWORD,
backend/app/services/password_reset.py:1:"""Password-reset token issue + redeem.
backend/app/services/password_reset.py:3:Sprint 6. Tokens are 32-byte cryptographically random secrets,
backend/app/services/password_reset.py:5:The cleartext is returned by :func:`issue_token` once and never
backend/app/services/password_reset.py:7:``password_reset_tokens.token_hash``.
backend/app/services/password_reset.py:10:later attempt with the same token fails validation.
backend/app/services/password_reset.py:16:import secrets
backend/app/services/password_reset.py:25:from app.services.auth import hash_password
backend/app/services/password_reset.py:36:def _hash_cleartext(token: str) -> str:
backend/app/services/password_reset.py:37:    return hashlib.sha256(token.encode("utf-8")).hexdigest()
backend/app/services/password_reset.py:40:async def issue_token(db: AsyncSession, user: User) -> str:
backend/app/services/password_reset.py:41:    """Generate a fresh single-use token for ``user``.
backend/app/services/password_reset.py:43:    Returns the cleartext token (URL-safe base64) for embedding in
backend/app/services/password_reset.py:45:    ``token_hash`` and TTL controlled by
backend/app/services/password_reset.py:51:    cleartext = secrets.token_urlsafe(32)
backend/app/services/password_reset.py:54:        token_hash=_hash_cleartext(cleartext),
backend/app/services/password_reset.py:65:async def redeem_token(
backend/app/services/password_reset.py:68:    new_password: str,
backend/app/services/password_reset.py:70:    """Validate ``cleartext`` and set ``new_password`` on the owner.
backend/app/services/password_reset.py:73:    expired, already-used). On success: marks token used, sets
backend/app/services/password_reset.py:74:    new password (hashed), flushes. Caller commits.
backend/app/services/password_reset.py:78:        raise InvalidResetToken("token missing")
backend/app/services/password_reset.py:79:    if len(new_password) < 8:
backend/app/services/password_reset.py:80:        raise InvalidResetToken("password too short")
backend/app/services/password_reset.py:82:    token_hash = _hash_cleartext(cleartext)
backend/app/services/password_reset.py:86:                PasswordResetToken.token_hash == token_hash
backend/app/services/password_reset.py:91:        raise InvalidResetToken("token not found")
backend/app/services/password_reset.py:93:        raise InvalidResetToken("token already used")
backend/app/services/password_reset.py:95:        raise InvalidResetToken("token expired")
backend/app/services/password_reset.py:103:    user.hashed_password = hash_password(new_password)
backend/app/services/password_reset.py:109:__all__ = ["InvalidResetToken", "issue_token", "redeem_token"]
backend/app/routers/instances.py:28:    r = aioredis.from_url(settings.REDIS_URL)
backend/app/routers/v1/auth.py:10:- ``POST /api/v1/auth/register`` — create user, return token pair.
backend/app/routers/v1/auth.py:11:- ``POST /api/v1/auth/login``    — authenticate, return token pair.
backend/app/routers/v1/auth.py:12:- ``POST /api/v1/auth/refresh``  — exchange refresh token for new access.
backend/app/routers/v1/auth.py:13:- ``POST /api/v1/auth/logout``   — revoke refresh token (best-effort).
backend/app/routers/v1/auth.py:16:Audit-ledger emit, account lockout, and refresh-token blacklist
backend/app/routers/v1/auth.py:64:    decode_mfa_pending_token,
backend/app/routers/v1/auth.py:66:    issue_mfa_pending_token,
backend/app/routers/v1/auth.py:75:    create_access_token,
backend/app/routers/v1/auth.py:76:    create_refresh_token,
backend/app/routers/v1/auth.py:77:    decode_token,
backend/app/routers/v1/auth.py:79:    hash_password,
backend/app/routers/v1/auth.py:81:    verify_password,
backend/app/routers/v1/auth.py:90:    r = aioredis.from_url(settings.REDIS_URL)
backend/app/routers/v1/auth.py:103:        role=user.role.value,
backend/app/routers/v1/auth.py:138:        hashed_password=hash_password(payload.password),
backend/app/routers/v1/auth.py:161:    # Sprint 9 Phase B — issue an email-verification token and email
backend/app/routers/v1/auth.py:167:        issue_token as issue_verify_token,
backend/app/routers/v1/auth.py:172:        cleartext = await issue_verify_token(db, user)
backend/app/routers/v1/auth.py:174:            f"{settings_local.frontend_url()}/verify-email"
backend/app/routers/v1/auth.py:175:            f"?token={cleartext}"
backend/app/routers/v1/auth.py:201:        # Don't fail register if SMTP / token issue blew up; the
backend/app/routers/v1/auth.py:209:        access_token=create_access_token(user.id, user.role.value),
backend/app/routers/v1/auth.py:210:        refresh_token=create_refresh_token(user.id),
backend/app/routers/v1/auth.py:218:        200: {"description": "Login success — token pair OR MFA pending"},
backend/app/routers/v1/auth.py:230:    """Authenticate by email + password.
backend/app/routers/v1/auth.py:235:        ``{user, access_token, refresh_token, token_type}``).
backend/app/routers/v1/auth.py:237:        (``{mfa_required: true, mfa_pending_token: "..."}``). The
backend/app/routers/v1/auth.py:239:        pending token + the user's TOTP / recovery code to receive
backend/app/routers/v1/auth.py:240:        the real token pair.
backend/app/routers/v1/auth.py:248:    if not user or not verify_password(payload.password, user.hashed_password):
backend/app/routers/v1/auth.py:260:                "reason": "bad_password" if user else "unknown_user",
backend/app/routers/v1/auth.py:306:    # pending token instead of the real pair. Login still counts as
backend/app/routers/v1/auth.py:309:    if user.mfa_enabled and user.mfa_secret:
backend/app/routers/v1/auth.py:326:            mfa_pending_token=issue_mfa_pending_token(user.id),
backend/app/routers/v1/auth.py:344:        access_token=create_access_token(user.id, user.role.value),
backend/app/routers/v1/auth.py:345:        refresh_token=create_refresh_token(user.id),
backend/app/routers/v1/auth.py:352:    responses={401: {"description": "Invalid or revoked refresh token"}},
backend/app/routers/v1/auth.py:360:    token = payload.refresh_token
backend/app/routers/v1/auth.py:362:    blacklisted = await redis_client.get(f"siege:blacklist:{token}")
backend/app/routers/v1/auth.py:367:        decoded = decode_token(token)
backend/app/routers/v1/auth.py:371:        raise HTTPException(status_code=401, detail="Invalid token")
backend/app/routers/v1/auth.py:374:        raise HTTPException(status_code=401, detail="Invalid token type")
backend/app/routers/v1/auth.py:379:        raise HTTPException(status_code=401, detail="Invalid token")
backend/app/routers/v1/auth.py:386:    new_access = create_access_token(user.id, user.role.value)
backend/app/routers/v1/auth.py:398:    return AuthRefreshResponse(access_token=new_access)
backend/app/routers/v1/auth.py:408:    token = payload.refresh_token
backend/app/routers/v1/auth.py:410:    if token:
backend/app/routers/v1/auth.py:412:            decoded = decode_token(token)
backend/app/routers/v1/auth.py:417:                    f"siege:blacklist:{token}", "1", ex=ttl
backend/app/routers/v1/auth.py:435:        payload={"token_revoked": bool(token)},
backend/app/routers/v1/auth.py:453:    "/forgot-password",
backend/app/routers/v1/auth.py:458:async def forgot_password_v1(
backend/app/routers/v1/auth.py:463:    """Issue a password-reset token and email the link.
backend/app/routers/v1/auth.py:478:    from app.services.password_reset import issue_token
backend/app/routers/v1/auth.py:488:        cleartext = await issue_token(db, user)
backend/app/routers/v1/auth.py:490:            f"{settings.frontend_url()}/reset-password"
backend/app/routers/v1/auth.py:491:            f"?token={cleartext}"
backend/app/routers/v1/auth.py:495:            f"Someone (hopefully you) requested a password reset on "
backend/app/routers/v1/auth.py:496:            f"siege-range. Click the link below to set a new password "
backend/app/routers/v1/auth.py:505:            subject="Reset your siege-range password",
backend/app/routers/v1/auth.py:539:            "If an account with that email exists, a password "
backend/app/routers/v1/auth.py:546:    "/reset-password",
backend/app/routers/v1/auth.py:548:    responses={400: {"description": "Invalid or expired reset token"}},
backend/app/routers/v1/auth.py:550:async def reset_password_v1(
backend/app/routers/v1/auth.py:555:    """Redeem a reset token and set a new password."""
backend/app/routers/v1/auth.py:563:    from app.services.password_reset import (
backend/app/routers/v1/auth.py:565:        redeem_token,
backend/app/routers/v1/auth.py:569:        user = await redeem_token(db, payload.token, payload.new_password)
backend/app/routers/v1/auth.py:585:            status_code=400, detail="invalid or expired token"
backend/app/routers/v1/auth.py:606:    "/change-password",
backend/app/routers/v1/auth.py:608:    responses={401: {"description": "Current password incorrect"}},
backend/app/routers/v1/auth.py:610:async def change_password_v1(
backend/app/routers/v1/auth.py:616:    """In-app password change. Requires current password."""
backend/app/routers/v1/auth.py:618:    if not verify_password(payload.current_password, current_user.hashed_password):
backend/app/routers/v1/auth.py:626:            payload={"success": False, "reason": "bad_current_password"},
backend/app/routers/v1/auth.py:630:        raise HTTPException(status_code=401, detail="current password incorrect")
backend/app/routers/v1/auth.py:632:    current_user.hashed_password = hash_password(payload.new_password)
backend/app/routers/v1/auth.py:699:    """Generate a fresh TOTP secret + provisioning URI.
backend/app/routers/v1/auth.py:703:    MFA fully enabled rotates the secret to a new one and resets
backend/app/routers/v1/auth.py:720:        secret=result.secret,
backend/app/routers/v1/auth.py:795:    """Disable MFA after re-authenticating with password + code."""
backend/app/routers/v1/auth.py:797:    if not verify_password(payload.password, current_user.hashed_password):
backend/app/routers/v1/auth.py:805:            payload={"success": False, "reason": "bad_password"},
backend/app/routers/v1/auth.py:809:        raise HTTPException(status_code=401, detail="password incorrect")
backend/app/routers/v1/auth.py:845:        401: {"description": "Pending token invalid or code rejected"},
backend/app/routers/v1/auth.py:855:    Consumes the pending token from ``/auth/login`` (response body
backend/app/routers/v1/auth.py:857:    code). Returns the real access + refresh token pair on
backend/app/routers/v1/auth.py:864:        user_id = decode_mfa_pending_token(payload.mfa_pending_token)
backend/app/routers/v1/auth.py:904:        access_token=access,
backend/app/routers/v1/auth.py:905:        refresh_token=refresh,
backend/app/routers/v1/auth.py:915:    responses={400: {"description": "Invalid or expired token"}},
backend/app/routers/v1/auth.py:922:    """Redeem an email-verification token and flip
backend/app/routers/v1/auth.py:927:        redeem_token,
backend/app/routers/v1/auth.py:931:        user = await redeem_token(db, payload.token)
backend/app/routers/v1/auth.py:945:            status_code=400, detail="invalid or expired token"
backend/app/routers/v1/auth.py:972:    """Issue a new verification token and email the link.
backend/app/routers/v1/auth.py:980:        issue_token as issue_verify_token,
backend/app/routers/v1/auth.py:985:        cleartext = await issue_verify_token(db, current_user)
backend/app/routers/v1/auth.py:987:            f"{settings_local.frontend_url()}/verify-email"
backend/app/routers/v1/auth.py:988:            f"?token={cleartext}"
backend/app/routers/ws.py:6:from app.services.auth import decode_token
backend/app/routers/ws.py:15:    token: str = Query(None),
backend/app/routers/ws.py:17:    if not token:
backend/app/routers/ws.py:18:        await websocket.close(code=4001, reason="Missing authentication token")
backend/app/routers/ws.py:22:        payload = decode_token(token)
backend/app/routers/ws.py:25:            await websocket.close(code=4001, reason="Invalid token")
backend/app/routers/ws.py:28:        await websocket.close(code=4001, reason="Invalid or expired token")
backend/app/services/mfa.py:4:secret generation, recovery-code lifecycle, login-step pending-token
backend/app/services/mfa.py:11:The MFA pending token is a short-lived JWT issued during the login
backend/app/services/mfa.py:15:access + refresh tokens.
backend/app/services/mfa.py:21:import secrets
backend/app/services/mfa.py:33:from app.services.auth import create_access_token, create_refresh_token
backend/app/services/mfa.py:49:    finished enrolment (mfa_secret unset OR mfa_enabled=False)."""
backend/app/services/mfa.py:54:    secret: str
backend/app/services/mfa.py:70:            secrets.choice(_RECOVERY_CODE_ALPHABET)
backend/app/services/mfa.py:83:    """Generate a fresh TOTP secret + provisioning URI for ``user``.
backend/app/services/mfa.py:85:    Stores the secret on the row but does NOT enable MFA yet —
backend/app/services/mfa.py:89:    rotates the secret (the previous one becomes garbage).
backend/app/services/mfa.py:92:    secret = pyotp.random_base32()
backend/app/services/mfa.py:93:    user.mfa_secret = secret
backend/app/services/mfa.py:97:    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
backend/app/services/mfa.py:102:        secret=secret, provisioning_uri=provisioning_uri
backend/app/services/mfa.py:116:    if not user.mfa_secret:
backend/app/services/mfa.py:119:    if not pyotp.TOTP(user.mfa_secret).verify(code, valid_window=1):
backend/app/services/mfa.py:142:    if not user.mfa_enabled or not user.mfa_secret:
backend/app/services/mfa.py:148:    user.mfa_secret = None
backend/app/services/mfa.py:160:    On success: returns the (access_token, refresh_token) pair.
backend/app/services/mfa.py:164:    if not user.mfa_enabled or not user.mfa_secret:
backend/app/services/mfa.py:171:        create_access_token(user.id, user.role.value),
backend/app/services/mfa.py:172:        create_refresh_token(user.id),
backend/app/services/mfa.py:188:        if pyotp.TOTP(user.mfa_secret).verify(code_str, valid_window=1):
backend/app/services/mfa.py:210:# Pending-token plumbing for the two-step login flow
backend/app/services/mfa.py:212:def issue_mfa_pending_token(user_id: int) -> str:
backend/app/services/mfa.py:235:def decode_mfa_pending_token(token: str) -> int:
backend/app/services/mfa.py:236:    """Validate the pending token and return the user_id."""
backend/app/services/mfa.py:243:            token, settings.SECRET_KEY, algorithms=["HS256"]
backend/app/services/mfa.py:246:        raise InvalidMfaCode("invalid pending token") from exc
backend/app/services/mfa.py:248:        raise InvalidMfaCode("wrong token type")
backend/app/services/mfa.py:253:        raise InvalidMfaCode("malformed pending token") from exc
backend/app/services/mfa.py:262:    "decode_mfa_pending_token",
backend/app/services/mfa.py:264:    "issue_mfa_pending_token",
backend/app/routers/stats.py:184:    if current_user.id != user_id and current_user.role != "admin":
backend/app/routers/v1/workstation.py:42:    web_url: Optional[str] = None
backend/app/routers/v1/workstation.py:48:    one_shot_password: Optional[str] = None
backend/app/routers/v1/workstation.py:65:    return request.url.scheme or "http"
backend/app/routers/v1/workstation.py:92:        "web_url": None,
backend/app/routers/v1/workstation.py:102:            body["web_url"] = f"{scheme}://{host}/workstation/{user_id:03d}/"
backend/app/routers/v1/workstation.py:104:            body["web_url"] = f"{scheme}://{host}:{d.web_host_port}/"
backend/app/routers/v1/workstation.py:133:    # workstation is idempotent and returns ``one_shot_password=None``.
backend/app/routers/v1/workstation.py:134:    if d.one_shot_password is not None:
backend/app/routers/v1/workstation.py:166:        one_shot_password=d.one_shot_password,
backend/app/routers/health.py:57:    client = aioredis.from_url(settings.REDIS_URL)
backend/app/routers/health.py:64:async def _probe_docker() -> None:
backend/app/routers/health.py:65:    # docker-py is sync; run in a thread so it doesn't block the loop
backend/app/routers/health.py:67:    # this through the long-lived client wired to the docker-socket-proxy
backend/app/routers/health.py:69:    from app.services.orchestration import docker_client
backend/app/routers/health.py:72:        client = docker_client.get()
backend/app/routers/health.py:81:    "docker": _probe_docker,
backend/app/services/challenge_loader/upsert.py:92:    challenge.docker_image = manifest.container.image
backend/app/services/challenge_loader/upsert.py:93:    challenge.docker_port = manifest.container.port
backend/app/services/challenge_loader/upsert.py:94:    challenge.docker_config = {
backend/app/routers/v1/me.py:11:import secrets
backend/app/routers/v1/me.py:35:    hash_password,
backend/app/routers/v1/me.py:36:    verify_password,
backend/app/routers/v1/me.py:60:        role=current_user.role.value,
backend/app/routers/v1/me.py:99:      - ``profile``: User row (no hashed_password)
backend/app/routers/v1/me.py:111:    profile = _row_dict(current_user, exclude=("hashed_password",))
backend/app/routers/v1/me.py:201:    - hashed_password → unguessable random hash (login disabled)
backend/app/routers/v1/me.py:205:    Pending password-reset tokens for the user are deleted.
backend/app/routers/v1/me.py:207:    Requires the current password in the body to defend against
backend/app/routers/v1/me.py:208:    drive-by deletes via stolen access tokens.
backend/app/routers/v1/me.py:211:    if not verify_password(payload.password, current_user.hashed_password):
backend/app/routers/v1/me.py:212:        raise HTTPException(status_code=401, detail="password incorrect")
backend/app/routers/v1/me.py:218:    current_user.hashed_password = hash_password(secrets.token_hex(32))
backend/app/routers/v1/admin.py:10:- ``PUT    /api/v1/admin/users/{user_id}``      — role/team/active
backend/app/routers/v1/admin.py:82:        role=u.role.value,
backend/app/routers/v1/admin.py:97:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:128:        docker_image=payload.docker_image,
backend/app/routers/v1/admin.py:129:        docker_port=payload.docker_port,
backend/app/routers/v1/admin.py:130:        docker_config=payload.docker_config,
backend/app/routers/v1/admin.py:146:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:209:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:285:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:313:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:322:    """Admin-side full challenge view including docker fields.
backend/app/routers/v1/admin.py:325:    docker_image / docker_port / docker_config so competitors can't
backend/app/routers/v1/admin.py:350:        docker_image=chal.docker_image,
backend/app/routers/v1/admin.py:351:        docker_port=chal.docker_port,
backend/app/routers/v1/admin.py:352:        docker_config=dict(chal.docker_config or {}),
backend/app/routers/v1/admin.py:373:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:447:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:464:    if "role" in updates and updates["role"] is not None:
backend/app/routers/v1/admin.py:465:        updates["role"] = UserRole(updates["role"])
backend/app/routers/v1/admin.py:484:        403: {"description": "Admin role required"},
backend/app/routers/v1/admin.py:532:            docker_image=data.get("docker_image", "alpine:3.19"),
backend/app/routers/v1/admin.py:533:            docker_port=data.get("docker_port", 8080),
backend/app/routers/v1/admin.py:534:            docker_config=data.get("docker_config", {}),
backend/app/services/scoreboard_cache.py:40:    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)
backend/app/services/validator_subprocess_runner.py:1:"""Child-process entrypoint for ``requires_subprocess=True`` validators.
backend/app/services/validator_subprocess_runner.py:3:Run as ``python -m app.services.validator_subprocess_runner``. The
backend/app/services/validator_subprocess_runner.py:4:parent (``run_validator_subprocess`` in :mod:`validator_sandbox`) writes
backend/app/services/validator_subprocess_runner.py:17:The protocol is intentionally line-based JSON, not pickle: pickle would
backend/app/services/validator_subprocess_runner.py:172:if __name__ == "__main__":  # pragma: no cover — exercised via subprocess
backend/app/services/backup.py:9:2. Builds a ``pg_dump`` subprocess against
backend/app/services/backup.py:21:Tests stub the subprocess so we never spawn a real ``pg_dump``;
backend/app/services/backup.py:35:from urllib.parse import urlparse
backend/app/services/backup.py:56:def _parse_async_url(url: str) -> dict[str, str]:
backend/app/services/backup.py:65:    plain = url.replace("+asyncpg", "")
backend/app/services/backup.py:66:    p = urlparse(plain)
backend/app/services/backup.py:74:    if p.password:
backend/app/services/backup.py:75:        out["PGPASSWORD"] = p.password
backend/app/services/backup.py:102:    database_url: str,
backend/app/services/backup.py:134:    env.update(_parse_async_url(database_url))
backend/app/services/backup.py:147:        proc = await asyncio.create_subprocess_shell(
backend/app/services/backup.py:150:            stdout=asyncio.subprocess.DEVNULL,
backend/app/services/backup.py:151:            stderr=asyncio.subprocess.PIPE,
backend/app/services/backup.py:156:            ok=False, error=f"subprocess error: {type(exc).__name__}: {exc}"
backend/app/services/email_verification.py:1:"""Email-verification token issue + redeem.
backend/app/services/email_verification.py:3:Sprint 9 Phase B. Mirrors the password-reset flow shape: a 32-byte
backend/app/services/email_verification.py:4:URL-safe secret is generated at register time, sha256-hashed at
backend/app/services/email_verification.py:8:TTL is longer than password-reset (24 hours) — users may not check
backend/app/services/email_verification.py:15:import secrets
backend/app/services/email_verification.py:32:def _hash_cleartext(token: str) -> str:
backend/app/services/email_verification.py:33:    return hashlib.sha256(token.encode("utf-8")).hexdigest()
backend/app/services/email_verification.py:36:async def issue_token(db: AsyncSession, user: User) -> str:
backend/app/services/email_verification.py:37:    """Generate a fresh single-use verification token.
backend/app/services/email_verification.py:44:    cleartext = secrets.token_urlsafe(32)
backend/app/services/email_verification.py:48:            token_hash=_hash_cleartext(cleartext),
backend/app/services/email_verification.py:59:async def redeem_token(db: AsyncSession, cleartext: str) -> User:
backend/app/services/email_verification.py:67:        raise InvalidVerificationToken("token missing")
backend/app/services/email_verification.py:69:    token_hash = _hash_cleartext(cleartext)
backend/app/services/email_verification.py:73:                EmailVerificationToken.token_hash == token_hash
backend/app/services/email_verification.py:78:        raise InvalidVerificationToken("token not found")
backend/app/services/email_verification.py:80:        raise InvalidVerificationToken("token already used")
backend/app/services/email_verification.py:82:        raise InvalidVerificationToken("token expired")
backend/app/services/email_verification.py:98:    "issue_token",
backend/app/services/email_verification.py:99:    "redeem_token",
backend/app/services/test_harness/runner.py:18:   spawns the resource-limited subprocess for
backend/app/services/test_harness/runner.py:19:   ``requires_subprocess=True`` validators.
backend/app/services/audit/events.py:38:    AUTH_PASSWORD_RESET_REQUEST: Final = "auth.password.reset.request"
backend/app/services/audit/events.py:39:    AUTH_PASSWORD_RESET_REDEEM: Final = "auth.password.reset.redeem"
backend/app/services/audit/events.py:40:    AUTH_PASSWORD_CHANGE: Final = "auth.password.change"
backend/app/services/audit/request_context.py:17:    ip = request.client.host if request.client else None
backend/app/services/webhook_dispatch.py:5:canonical JSON envelope to each ``target_url`` with an HMAC-SHA256
backend/app/services/webhook_dispatch.py:17:  from the subscription's ``secret``. Receivers verify by
backend/app/services/webhook_dispatch.py:38:import secrets as _secrets
backend/app/services/webhook_dispatch.py:61:def generate_subscription_secret() -> str:
backend/app/services/webhook_dispatch.py:62:    """Return a fresh URL-safe random secret for a new subscription."""
backend/app/services/webhook_dispatch.py:64:    return _secrets.token_hex(_SECRET_BYTES)
backend/app/services/webhook_dispatch.py:67:def sign_body(secret: str, body: bytes) -> str:
backend/app/services/webhook_dispatch.py:75:    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
backend/app/services/webhook_dispatch.py:90:    each subscription's secret, and POSTs concurrently. The function
backend/app/services/webhook_dispatch.py:103:    delivery_id = _secrets.token_hex(8)
backend/app/services/webhook_dispatch.py:221:        _SIGNATURE_HEADER: sign_body(subscription.secret, body),
backend/app/services/webhook_dispatch.py:229:                subscription.target_url, content=body, headers=headers
backend/app/services/webhook_dispatch.py:294:    subscription's *current* secret — rotating the secret therefore

codex
I found a couple of extra candidates during the skim, but I’m only including ones with direct code evidence and clear security impact. I’m pulling exact line numbers now so the final can stay compact.
exec
/bin/bash -lc "nl -ba backend/app/services/webhook_dispatch.py | sed -n '220,235p'; nl -ba backend/app/schemas/v1/webhooks.py | sed -n '28,45p'; nl -ba backend/app/routers/v1/auth.py | sed -n '452,465p'; nl -ba backend/app/services/mfa.py | sed -n '178,236p'" in /data/projects/seige-range
 succeeded in 0ms:
   220	        "Content-Type": "application/json",
   221	        _SIGNATURE_HEADER: sign_body(subscription.secret, body),
   222	        _DELIVERY_HEADER: delivery_id,
   223	        _EVENT_HEADER: event_type,
   224	    }
   225	    started = time.monotonic()
   226	    try:
   227	        async with factory() as client:
   228	            response = await client.post(
   229	                subscription.target_url, content=body, headers=headers
   230	            )
   231	        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
   232	        if 200 <= response.status_code < 300:
   233	            return _AttemptOutcome(
   234	                subscription=subscription,
   235	                status=f"ok_{response.status_code}",
    28	_KNOWN_EVENTS = {
    29	    "challenge.flag.submit.pass",
    30	    "challenge.flag.submit.fail",
    31	    "challenge.released",
    32	    "auth.register",
    33	    "auth.login.success",
    34	    "auth.login.failed",
    35	    "auth.logout",
    36	    "auth.refresh",
    37	    "auth.password.reset.request",
    38	    "auth.password.reset.redeem",
    39	    "auth.password.change",
    40	    "auth.profile.update",
    41	    "auth.account.delete",
    42	    "auth.data.export",
    43	    "auth.mfa.enroll",
    44	    "auth.mfa.confirm",
    45	    "auth.mfa.disable",
   452	@router.post(
   453	    "/forgot-password",
   454	    response_model=ForgotPasswordResponse,
   455	    status_code=status.HTTP_202_ACCEPTED,
   456	    responses={429: {"description": "Too many reset requests"}},
   457	)
   458	async def forgot_password_v1(
   459	    payload: ForgotPasswordRequest,
   460	    request: Request,
   461	    db: AsyncSession = Depends(get_db),
   462	) -> ForgotPasswordResponse:
   463	    """Issue a password-reset token and email the link.
   464	
   465	    Always returns 202 with a generic message regardless of whether
   178	) -> None:
   179	    """TOTP first; falls back to recovery codes. Marks the matched
   180	    recovery code used. Raises :class:`InvalidMfaCode` on miss."""
   181	
   182	    code_str = (code or "").strip()
   183	    if not code_str:
   184	        raise InvalidMfaCode("code missing")
   185	
   186	    # TOTP path — 6 digits.
   187	    if code_str.isdigit() and len(code_str) == 6:
   188	        if pyotp.TOTP(user.mfa_secret).verify(code_str, valid_window=1):
   189	            return
   190	
   191	    # Recovery-code path — alphanumeric, length matches.
   192	    candidate = _hash_recovery_code(code_str)
   193	    row: Optional[MfaRecoveryCode] = (
   194	        await db.execute(
   195	            select(MfaRecoveryCode).where(
   196	                MfaRecoveryCode.user_id == user.id,
   197	                MfaRecoveryCode.code_hash == candidate,
   198	                MfaRecoveryCode.used_at.is_(None),
   199	            )
   200	        )
   201	    ).scalars().first()
   202	    if row is not None:
   203	        row.used_at = datetime.now(timezone.utc)
   204	        return
   205	
   206	    raise InvalidMfaCode("code did not match")
   207	
   208	
   209	# ---------------------------------------------------------------------------
   210	# Pending-token plumbing for the two-step login flow
   211	# ---------------------------------------------------------------------------
   212	def issue_mfa_pending_token(user_id: int) -> str:
   213	    """Short-lived JWT carrying ``{type:"mfa_pending"}`` + sub.
   214	
   215	    Uses the same ``python-jose`` library as the rest of the auth
   216	    stack so signature verification is uniform.
   217	    """
   218	
   219	    from jose import jwt as jose_jwt
   220	
   221	    settings = get_settings()
   222	    payload = {
   223	        "sub": str(user_id),
   224	        "type": "mfa_pending",
   225	        "exp": int(
   226	            (
   227	                datetime.now(timezone.utc)
   228	                + timedelta(seconds=_MFA_PENDING_TTL_SECONDS)
   229	            ).timestamp()
   230	        ),
   231	    }
   232	    return jose_jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
   233	
   234	
   235	def decode_mfa_pending_token(token: str) -> int:
   236	    """Validate the pending token and return the user_id."""

exec
/bin/bash -lc "nl -ba backend/app/routers/ws.py | sed -n '12,24p'; nl -ba backend/app/services/backup.py | sed -n '140,151p'; nl -ba backend/app/routers/stats.py | sed -n '178,188p'; nl -ba backend/app/routers/v1/auth.py | sed -n '962,992p'; nl -ba backend/app/routers/auth.py | sed -n '42,90p'" in /data/projects/seige-range
exec
/bin/bash -lc "nl -ba backend/app/middleware/security_headers.py | sed -n '80,120p'; nl -ba backend/app/main.py | sed -n '150,215p'; nl -ba backend/app/routers/auth.py | sed -n '106,130p'; nl -ba backend/app/routers/v1/auth.py | sed -n '240,330p'; nl -ba backend/app/middleware/rate_limit.py | sed -n '40,60p'" in /data/projects/seige-range
 succeeded in 0ms:
    12	@router.websocket("/ws")
    13	async def websocket_endpoint(
    14	    websocket: WebSocket,
    15	    token: str = Query(None),
    16	):
    17	    if not token:
    18	        await websocket.close(code=4001, reason="Missing authentication token")
    19	        return
    20	
    21	    try:
    22	        payload = decode_token(token)
    23	        user_id = int(payload.get("sub", 0))
    24	        if not user_id:
   140	        # buffer for multi-GB dumps. The double quotes around
   141	        # the path are safe — ``out_path`` is built from ASCII
   142	        # timestamp.
   143	        cmd = (
   144	            f"{pg_dump_path} --no-owner --no-privileges "
   145	            f"| gzip -c > '{out_path}'"
   146	        )
   147	        proc = await asyncio.create_subprocess_shell(
   148	            cmd,
   149	            env=env,
   150	            stdout=asyncio.subprocess.DEVNULL,
   151	            stderr=asyncio.subprocess.PIPE,
   178	@router.get("/user/{user_id}")
   179	async def user_stats(
   180	    user_id: int,
   181	    current_user: User = Depends(get_current_user),
   182	    db: AsyncSession = Depends(get_db),
   183	):
   184	    if current_user.id != user_id and current_user.role != "admin":
   185	        raise HTTPException(status_code=403, detail="Access denied.")
   186	
   187	    user_result = await db.execute(select(User).where(User.id == user_id))
   188	    user = user_result.scalars().first()
   962	@router.post(
   963	    "/resend-verification",
   964	    response_model=ResendVerificationResponse,
   965	    status_code=status.HTTP_202_ACCEPTED,
   966	)
   967	async def resend_verification_v1(
   968	    request: Request,
   969	    current_user: User = Depends(get_current_user),
   970	    db: AsyncSession = Depends(get_db),
   971	) -> ResendVerificationResponse:
   972	    """Issue a new verification token and email the link.
   973	
   974	    No-op (still 202) if the user is already verified, so callers
   975	    can't probe verification state with this endpoint.
   976	    """
   977	
   978	    from app.services.email import send_email
   979	    from app.services.email_verification import (
   980	        issue_token as issue_verify_token,
   981	    )
   982	
   983	    settings_local = get_settings()
   984	    if not current_user.email_verified:
   985	        cleartext = await issue_verify_token(db, current_user)
   986	        link = (
   987	            f"{settings_local.frontend_url()}/verify-email"
   988	            f"?token={cleartext}"
   989	        )
   990	        await send_email(
   991	            to=current_user.email,
   992	            subject="Confirm your siege-range email",
    42	@router.post("/register", status_code=status.HTTP_201_CREATED)
    43	async def register(
    44	    data: UserCreate,
    45	    request: Request,
    46	    db: AsyncSession = Depends(get_db),
    47	):
    48	    email = data.email
    49	    username = data.username
    50	    password = data.password
    51	    display_name = data.display_name or username
    52	    team = data.team
    53	
    54	    existing = await db.execute(
    55	        select(User).where((User.email == email) | (User.username == username))
    56	    )
    57	    if existing.scalar_one_or_none():
    58	        raise HTTPException(status_code=409, detail="Email or username already taken")
    59	
    60	    user = User(
    61	        email=email,
    62	        username=username,
    63	        hashed_password=hash_password(password),
    64	        display_name=display_name,
    65	        team=team,
    66	        created_at=datetime.now(timezone.utc),
    67	    )
    68	    db.add(user)
    69	    await db.flush()
    70	    await db.refresh(user)
    71	
    72	    await audit_append(
    73	        db,
    74	        event_type=EventType.AUTH_REGISTER,
    75	        actor_type=ActorType.USER,
    76	        actor_id=user.id,
    77	        resource_type="user",
    78	        resource_id=user.id,
    79	        payload={
    80	            "username": user.username,
    81	            "team": user.team.value if user.team else None,
    82	        },
    83	        **context_from_request(request),
    84	    )
    85	    await db.commit()
    86	
    87	    access_token = create_access_token(user.id, user.role.value)
    88	    refresh_token = create_refresh_token(user.id)
    89	
    90	    return {

 succeeded in 0ms:
    80	        # ``report-uri`` is the legacy directive (still honoured by
    81	        # every browser); ``report-to`` requires a separate
    82	        # Reporting-Endpoints header which isn't worth the extra
    83	        # plumbing today.
    84	        directives.append(f"report-uri {_CSP_REPORT_PATH}")
    85	    return "; ".join(directives)
    86	
    87	
    88	class REDACTEDHeadersMiddleware(BaseHTTPMiddleware):
    89	    def __init__(self, app, *, is_production: bool) -> None:
    90	        super().__init__(app)
    91	        self._is_production = is_production
    92	        self._csp = _build_csp()
    93	
    94	    async def dispatch(
    95	        self, request: Request, call_next: RequestResponseEndpoint
    96	    ) -> Response:
    97	        response = await call_next(request)
    98	
    99	        response.headers.setdefault("X-Content-Type-Options", "nosniff")
   100	        response.headers.setdefault("X-Frame-Options", "DENY")
   101	        response.headers.setdefault(
   102	            "Referrer-Policy", "strict-origin-when-cross-origin"
   103	        )
   104	        response.headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
   105	
   106	        if self._is_production:
   107	            response.headers.setdefault(
   108	                "Strict-Transport-REDACTED",
   109	                "max-age=31536000; includeSubDomains",
   110	            )
   111	
   112	        if request.url.path not in _DOC_PATHS:
   113	            response.headers.setdefault("Content-REDACTED-Policy", self._csp)
   114	
   115	        return response
   150	        pass
   151	    logger.info("Shutdown complete.")
   152	
   153	
   154	app = FastAPI(title="Siege Range API", version="2.5.0", lifespan=lifespan)
   155	
   156	# Sprint 11 Phase C — opt-in OpenTelemetry tracing. No-op when
   157	# OTEL_EXPORTER_OTLP_ENDPOINT is unset. Failure to configure
   158	# (missing dep, bad endpoint) logs WARN and degrades to disabled
   159	# — the platform must always boot.
   160	from app.database import engine as _db_engine
   161	from app.observability.tracing import configure_tracing
   162	
   163	configure_tracing(app, _db_engine)
   164	
   165	from app.middleware.logging_mw import LoggingMiddleware
   166	from app.middleware.metrics import PrometheusMetricsMiddleware
   167	from app.middleware.security_headers import REDACTEDHeadersMiddleware
   168	
   169	# Middleware order: outer-most runs last on the response. We want the
   170	# request-id logger to see the response **after** security headers have
   171	# been attached, so register the headers middleware first (it ends up
   172	# inner-most relative to LoggingMiddleware).
   173	app.add_middleware(REDACTEDHeadersMiddleware, is_production=_settings.is_production)
   174	app.add_middleware(LoggingMiddleware)
   175	# Prometheus metrics — outermost, so it sees the actual response
   176	# status code Starlette returns to the client (after any later
   177	# middleware mutates it).
   178	app.add_middleware(PrometheusMetricsMiddleware)
   179	
   180	_allowed_origins = _settings.allowed_origins_list()
   181	if not _allowed_origins:
   182	    logger.warning(
   183	        "CORS disabled: ALLOWED_ORIGINS is empty and APP_ENV=%s",
   184	        _settings.APP_ENV,
   185	    )
   186	
   187	app.add_middleware(
   188	    CORSMiddleware,
   189	    allow_origins=_allowed_origins,
   190	    allow_credentials=True,
   191	    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
   192	    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
   193	    expose_headers=["X-Request-ID"],
   194	    max_age=600,
   195	)
   196	
   197	from app.routers.auth import router as auth_router
   198	from app.routers.challenges import router as challenges_router
   199	from app.routers.health import router as health_router
   200	from app.routers.instances import router as instances_router
   201	from app.routers.leaderboard import router as leaderboard_router
   202	from app.routers.stats import router as stats_router
   203	from app.routers.writeups import router as writeups_router
   204	from app.routers.competitions import router as competitions_router
   205	from app.routers.notifications import router as notifications_router
   206	from app.routers.admin import router as admin_router
   207	from app.routers.ws import router as ws_router
   208	from app.routers.v1 import router as api_v1_router
   209	
   210	app.include_router(health_router)
   211	app.include_router(auth_router)
   212	app.include_router(challenges_router)
   213	app.include_router(instances_router)
   214	app.include_router(leaderboard_router)
   215	app.include_router(stats_router)
   106	@router.post("/login")
   107	async def login(
   108	    data: UserLogin,
   109	    request: Request,
   110	    db: AsyncSession = Depends(get_db),
   111	    redis_client=Depends(get_redis),
   112	):
   113	    email = data.email
   114	    password = data.password
   115	    ctx = context_from_request(request)
   116	
   117	    await check_account_lockout(email, redis_client)
   118	
   119	    result = await db.execute(select(User).where(User.email == email))
   120	    user = result.scalar_one_or_none()
   121	
   122	    if not user or not verify_password(password, user.hashed_password):
   123	        if user:
   124	            await record_failed_login(email, redis_client)
   125	        await audit_append(
   126	            db,
   127	            event_type=EventType.AUTH_LOGIN_FAILED,
   128	            actor_type=ActorType.USER if user else ActorType.ANONYMOUS,
   129	            actor_id=user.id if user else None,
   130	            resource_type="user",
   240	        the real token pair.
   241	    """
   242	    ctx = context_from_request(request)
   243	    await check_account_lockout(payload.email, redis_client)
   244	
   245	    result = await db.execute(select(User).where(User.email == payload.email))
   246	    user = result.scalar_one_or_none()
   247	
   248	    if not user or not verify_password(payload.password, user.hashed_password):
   249	        if user:
   250	            await record_failed_login(payload.email, redis_client)
   251	        await audit_append(
   252	            db,
   253	            event_type=EventType.AUTH_LOGIN_FAILED,
   254	            actor_type=ActorType.USER if user else ActorType.ANONYMOUS,
   255	            actor_id=user.id if user else None,
   256	            resource_type="user",
   257	            resource_id=user.id if user else None,
   258	            payload={
   259	                "email": payload.email,
   260	                "reason": "bad_password" if user else "unknown_user",
   261	            },
   262	            **ctx,
   263	        )
   264	        await db.commit()
   265	        raise HTTPException(status_code=401, detail="Invalid credentials")
   266	
   267	    if not user.is_active:
   268	        await audit_append(
   269	            db,
   270	            event_type=EventType.AUTH_LOGIN_FAILED,
   271	            actor_type=ActorType.USER,
   272	            actor_id=user.id,
   273	            resource_type="user",
   274	            resource_id=user.id,
   275	            payload={"email": payload.email, "reason": "account_disabled"},
   276	            **ctx,
   277	        )
   278	        await db.commit()
   279	        raise HTTPException(status_code=403, detail="Account is disabled")
   280	
   281	    # Sprint 10 Phase C — operator opt-in: refuse login until the
   282	    # user has clicked through their verification email.
   283	    settings_for_gate = get_settings()
   284	    if (
   285	        settings_for_gate.REQUIRE_EMAIL_VERIFIED
   286	        and not user.email_verified
   287	    ):
   288	        await audit_append(
   289	            db,
   290	            event_type=EventType.AUTH_LOGIN_FAILED,
   291	            actor_type=ActorType.USER,
   292	            actor_id=user.id,
   293	            resource_type="user",
   294	            resource_id=user.id,
   295	            payload={"email": payload.email, "reason": "email_not_verified"},
   296	            **ctx,
   297	        )
   298	        await db.commit()
   299	        raise HTTPException(
   300	            status_code=403, detail="email not verified"
   301	        )
   302	
   303	    await clear_failed_logins(payload.email, redis_client)
   304	
   305	    # MFA short-circuit: if the user has MFA enabled we return a
   306	    # pending token instead of the real pair. Login still counts as
   307	    # "successful first factor" — emit the audit row but don't bump
   308	    # last_login until the second factor verifies.
   309	    if user.mfa_enabled and user.mfa_secret:
   310	        await audit_append(
   311	            db,
   312	            event_type=EventType.AUTH_LOGIN_SUCCESS,
   313	            actor_type=ActorType.USER,
   314	            actor_id=user.id,
   315	            resource_type="user",
   316	            resource_id=user.id,
   317	            payload={
   318	                "username": user.username,
   319	                "mfa_pending": True,
   320	            },
   321	            **ctx,
   322	        )
   323	        await db.commit()
   324	        return MfaPendingResponse(
   325	            mfa_required=True,
   326	            mfa_pending_token=issue_mfa_pending_token(user.id),
   327	        )
   328	
   329	    user.last_login = datetime.now(timezone.utc)
   330	    await audit_append(
    40	
    41	
    42	async def flag_rate_limit(request: Request) -> None:
    43	    user_id = getattr(request.state, "user_id", request.client.host)
    44	    key = f"siege:ratelimit:flag:{user_id}"
    45	    await _check_rate_limit(key, 10, 60, request)
    46	
    47	
    48	async def auth_rate_limit(request: Request) -> None:
    49	    ip = request.client.host
    50	    key = f"siege:ratelimit:auth:{ip}"
    51	    await _check_rate_limit(key, 5, 60, request)
    52	
    53	
    54	async def general_rate_limit(request: Request) -> None:
    55	    user_id = getattr(request.state, "user_id", request.client.host)
    56	    key = f"siege:ratelimit:general:{user_id}"
    57	    await _check_rate_limit(key, 100, 60, request)

exec
/bin/bash -lc "nl -ba backend/app/routers/v1/auth.py | sed -n '248,263p'; nl -ba backend/app/routers/auth.py | sed -n '120,124p'; nl -ba frontend/package.json | sed -n '10,28p'; nl -ba .github/workflows/ci.yml | sed -n '35,48p'; find . -name 'pytest.ini' -o -name 'pyproject.toml' -o -name 'setup.cfg'" in /data/projects/seige-range
 succeeded in 0ms:
   248	    if not user or not verify_password(payload.password, user.hashed_password):
   249	        if user:
   250	            await record_failed_login(payload.email, redis_client)
   251	        await audit_append(
   252	            db,
   253	            event_type=EventType.AUTH_LOGIN_FAILED,
   254	            actor_type=ActorType.USER if user else ActorType.ANONYMOUS,
   255	            actor_id=user.id if user else None,
   256	            resource_type="user",
   257	            resource_id=user.id if user else None,
   258	            payload={
   259	                "email": payload.email,
   260	                "reason": "bad_password" if user else "unknown_user",
   261	            },
   262	            **ctx,
   263	        )
   120	    user = result.scalar_one_or_none()
   121	
   122	    if not user or not verify_password(password, user.hashed_password):
   123	        if user:
   124	            await record_failed_login(email, redis_client)
    10	    "e2e": "playwright test",
    11	    "e2e:list": "playwright test --list",
    12	    "e2e:ui": "playwright test --ui"
    13	  },
    14	  "dependencies": {
    15	    "axios": "^1.6.7",
    16	    "clsx": "^2.1.0",
    17	    "lucide-react": "^0.344.0",
    18	    "react": "^18.2.0",
    19	    "react-dom": "^18.2.0",
    20	    "react-router-dom": "^6.22.1",
    21	    "recharts": "^2.12.2",
    22	    "zustand": "^4.5.1"
    23	  },
    24	  "devDependencies": {
    25	    "@playwright/test": "^1.59.1",
    26	    "@tailwindcss/vite": "^4.0.0",
    27	    "@vitejs/plugin-react": "^4.2.1",
    28	    "autoprefixer": "^10.4.17",
    35	          python -m pip install --upgrade pip
    36	          pip install -r requirements.txt -r requirements-test.txt
    37	
    38	      - name: run pytest — unit tests only (integration suite needs
    39	          testcontainers config that isn't wired into CI yet)
    40	        working-directory: backend
    41	        env:
    42	          APP_ENV: test
    43	          SECRET_KEY: ci-test-secret-do-not-use-in-prod-0123456789abcdef0123456789abcdef
    44	          ADMIN_PASSWORD: CIAdminPasswordA1!
    45	          ALLOWED_ORIGINS: http://localhost:3000
    46	        run: |
    47	          python -m pytest tests/unit/ -v --no-cov
    48	
./backend/pytest.ini
./backend/pyproject.toml
./packages/bluerange-spec/pyproject.toml

exec
/bin/bash -lc "nl -ba backend/app/schemas/v1/webhooks.py | sed -n '52,62p'; nl -ba backend/pytest.ini | sed -n '1,80p'; nl -ba backend/app/services/auth.py | sed -n '29,58p'; nl -ba backend/app/routers/v1/auth.py | sed -n '841,908p'" in /data/projects/seige-range
 succeeded in 0ms:
    52	    "*",  # wildcard: deliver every event the platform emits
    53	}
    54	
    55	
    56	class WebhookCreateRequest(BaseModel):
    57	    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    58	
    59	    name: str = Field(min_length=1, max_length=200)
    60	    target_url: HttpUrl
    61	    events: List[str] = Field(min_length=1, max_length=32)
    62	
     1	[pytest]
     2	testpaths = tests
     3	asyncio_mode = auto
     4	filterwarnings =
     5	    ignore::DeprecationWarning:passlib.*
     6	    ignore::DeprecationWarning:jose.*
     7	addopts =
     8	    -ra
     9	    --strict-markers
    10	    --strict-config
    11	    --cov=app.services.auth
    12	    --cov=app.services.scoring
    13	    --cov=app.services.audit
    14	    --cov=app.services.hints
    15	    --cov=app.services.flag_submission
    16	    --cov=app.services.challenge_browse
    17	    --cov=app.services.challenge_loader
    18	    --cov=app.services.flag_dispatch
    19	    --cov=app.services.validator_registry
    20	    --cov=app.services.validator_sandbox
    21	    --cov=app.services.validator_subprocess_runner
    22	    --cov=app.services.test_harness
    23	    --cov=app.services.api_v1
    24	    --cov=app.services.webhook_dispatch
    25	    --cov=app.routers.v1
    26	    --cov=app.validators
    27	    --cov=app.routers.auth
    28	    --cov=app.routers.challenges
    29	    --cov=app.routers.admin
    30	    --cov=app.routers.competitions
    31	    --cov=app.routers.health
    32	    --cov=app.routers.instances
    33	    --cov=app.routers.leaderboard
    34	    --cov=app.routers.notifications
    35	    --cov=app.routers.stats
    36	    --cov=app.routers.writeups
    37	    --cov=app.security.seccomp
    38	    --cov=app.services.orchestration
    39	    --cov=app.services.scheduler
    40	    --cov=app.services.ws_manager
    41	    --cov-report=term-missing
    42	    # Phase 12 (slice 12): project-wide gate bumped from the Phase 5
    43	    # 60% floor to 80% per the Phase 0 commitment. Slices 1–11 left
    44	    # the project at ~86%; the new gate locks in the margin.
    45	    --cov-fail-under=80
    46	markers =
    47	    integration: tests that hit the testcontainer Postgres/Redis
    48	    unit: in-process unit tests with no external deps (mocked docker, no DB)
    29	def create_access_token(user_id: int, role: str) -> str:
    30	    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    31	    payload = {
    32	        "sub": str(user_id),
    33	        "role": role,
    34	        "type": "access",
    35	        "exp": expire,
    36	    }
    37	    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    38	
    39	
    40	def create_refresh_token(user_id: int) -> str:
    41	    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    42	    payload = {
    43	        "sub": str(user_id),
    44	        "type": "refresh",
    45	        "exp": expire,
    46	    }
    47	    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    48	
    49	
    50	def decode_token(token: str) -> dict:
    51	    try:
    52	        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    53	        return payload
    54	    except JWTError:
    55	        raise HTTPException(
    56	            status_code=status.HTTP_401_UNAUTHORIZED,
    57	            detail="Invalid or expired token",
    58	        )
   841	@router.post(
   842	    "/mfa/verify",
   843	    response_model=AuthTokenPairResponse,
   844	    responses={
   845	        401: {"description": "Pending token invalid or code rejected"},
   846	    },
   847	)
   848	async def mfa_verify_v1(
   849	    payload: MfaVerifyRequest,
   850	    request: Request,
   851	    db: AsyncSession = Depends(get_db),
   852	) -> AuthTokenPairResponse:
   853	    """Second-factor step of the login flow.
   854	
   855	    Consumes the pending token from ``/auth/login`` (response body
   856	    when MFA is enabled) plus the user's TOTP code (or a recovery
   857	    code). Returns the real access + refresh token pair on
   858	    success.
   859	    """
   860	
   861	    ctx = context_from_request(request)
   862	
   863	    try:
   864	        user_id = decode_mfa_pending_token(payload.mfa_pending_token)
   865	    except InvalidMfaCode as exc:
   866	        raise HTTPException(status_code=401, detail=str(exc))
   867	
   868	    user = (
   869	        await db.execute(select(User).where(User.id == user_id))
   870	    ).scalar_one_or_none()
   871	    if user is None or not user.is_active:
   872	        raise HTTPException(status_code=401, detail="user not found")
   873	
   874	    try:
   875	        access, refresh = await verify_login_code(db, user, payload.code)
   876	    except (InvalidMfaCode, MfaNotEnrolled) as exc:
   877	        await audit_append(
   878	            db,
   879	            event_type=EventType.AUTH_MFA_VERIFY_FAILED,
   880	            actor_type=ActorType.USER,
   881	            actor_id=user.id,
   882	            resource_type="user",
   883	            resource_id=user.id,
   884	            payload={"reason": str(exc)},
   885	            **ctx,
   886	        )
   887	        await db.commit()
   888	        raise HTTPException(status_code=401, detail="code rejected")
   889	
   890	    user.last_login = datetime.now(timezone.utc)
   891	    await audit_append(
   892	        db,
   893	        event_type=EventType.AUTH_MFA_VERIFY_SUCCESS,
   894	        actor_type=ActorType.USER,
   895	        actor_id=user.id,
   896	        resource_type="user",
   897	        resource_id=user.id,
   898	        payload={"username": user.username},
   899	        **ctx,
   900	    )
   901	    await db.commit()
   902	    return AuthTokenPairResponse(
   903	        user=_to_auth_user(user),
   904	        access_token=access,
   905	        refresh_token=refresh,
   906	    )
   907	
   908	

exec
/bin/bash -lc "rg -n \"auth_rate_limit|Depends\\(auth_rate_limit\\)\" backend/app/routers backend/app/services backend/app/main.py" in /data/projects/seige-range
 succeeded in 0ms:
backend/app/routers/auth.py:25:from app.middleware.rate_limit import auth_rate_limit

codex
[CRITICAL] backend/app/middleware/security_headers.py:108 — redacted header names used for HSTS/CSP
  Verdict: CONFIRMED — Emits non-canonical header names at 108 and 113.

[HIGH] backend/app/main.py:154 — FastAPI docs/OpenAPI not disabled
  Verdict: CONFIRMED — `FastAPI(...)` leaves default `/docs`, `/redoc`, `/openapi.json`.

[CRITICAL] backend/app/routers/auth.py:106 — legacy login bypasses MFA
  Verdict: CONFIRMED — v0 login returns tokens; v1 gates MFA at `v1/auth.py:309`.

[HIGH] backend/app/middleware/rate_limit.py:48 — auth rate limiter unused
  Verdict: CONFIRMED — Imported only, no `Depends(auth_rate_limit)`.

[HIGH] backend/app/middleware/rate_limit.py:43 — rate limit keys use proxy peer
  Verdict: CONFIRMED — Uses `request.client.host`; no forwarded-client handling found.

[CRITICAL] backend/app/services/webhook_dispatch.py:229 — webhook SSRF to arbitrary URL
  Verdict: CONFIRMED — `HttpUrl` only at schema line 60; no private-IP block.

[HIGH] backend/app/routers/v1/auth.py:452 — forgot-password lacks rate limit
  Verdict: CONFIRMED — 429 documented; no limiter dependency.

[HIGH] backend/app/services/mfa.py:178 — MFA verify lacks attempt counter
  Verdict: CONFIRMED — No per-token/user counter; pending JWT TTL is 300s.

[HIGH] backend/app/routers/v1/auth.py:248 — login timing oracle
  Verdict: CONFIRMED — Missing-user path skips bcrypt; same in v0 at `auth.py:122`.

[HIGH] backend/app/routers/v1/auth.py:258 — failed-login audit stores raw email
  Verdict: DOWNGRADE — Privacy issue confirmed, but not HIGH security impact by itself.

[MEDIUM] backend/app/models.py:562 — god file over 300 lines
  Verdict: CONFIRMED — `models.py` 562 lines; `flag_submission.py` 614 lines.

[HIGH] frontend/package.json:15 — floating dependency ranges
  Verdict: CONFIRMED — Caret ranges throughout dependencies/devDependencies.

[HIGH] .github/workflows/ci.yml:47 — CI disables coverage and integration tests
  Verdict: CONFIRMED — Runs `tests/unit/ -v --no-cov`; `backend/pytest.ini` has 80% gate.

[HIGH] backend/app/routers/ws.py:15 — WebSocket token in query string
  Verdict: CONFIRMED — Access token accepted as `?token=`, likely logged by access logs.

[MEDIUM] backend/app/routers/v1/auth.py:962 — resend verification lacks rate limit
  Verdict: CONFIRMED — Authenticated endpoint can repeatedly send email.

[MEDIUM] backend/app/routers/auth.py:42 — legacy register bypasses email verification
  Verdict: CONFIRMED — v0 immediately returns tokens; v1 has email verification flow.

[MEDIUM] backend/app/services/auth.py:50 — JWT decode lacks issuer/audience validation
  Verdict: CONFIRMED — Only signature/expiry/type checked, contrary to CLAUDE §3.2.

[MEDIUM] backend/app/services/backup.py:147 — backup uses shell pipeline
  Verdict: NEEDS-MORE-INFO — `create_subprocess_shell` present; exploitability depends on `BACKUP_DIR`.

VERDICT: KICK-BACK
tokens used
101,704
[CRITICAL] backend/app/middleware/security_headers.py:108 — redacted header names used for HSTS/CSP
  Verdict: CONFIRMED — Emits non-canonical header names at 108 and 113.

[HIGH] backend/app/main.py:154 — FastAPI docs/OpenAPI not disabled
  Verdict: CONFIRMED — `FastAPI(...)` leaves default `/docs`, `/redoc`, `/openapi.json`.

[CRITICAL] backend/app/routers/auth.py:106 — legacy login bypasses MFA
  Verdict: CONFIRMED — v0 login returns tokens; v1 gates MFA at `v1/auth.py:309`.

[HIGH] backend/app/middleware/rate_limit.py:48 — auth rate limiter unused
  Verdict: CONFIRMED — Imported only, no `Depends(auth_rate_limit)`.

[HIGH] backend/app/middleware/rate_limit.py:43 — rate limit keys use proxy peer
  Verdict: CONFIRMED — Uses `request.client.host`; no forwarded-client handling found.

[CRITICAL] backend/app/services/webhook_dispatch.py:229 — webhook SSRF to arbitrary URL
  Verdict: CONFIRMED — `HttpUrl` only at schema line 60; no private-IP block.

[HIGH] backend/app/routers/v1/auth.py:452 — forgot-password lacks rate limit
  Verdict: CONFIRMED — 429 documented; no limiter dependency.

[HIGH] backend/appcodex
[CRITICAL] backend/app/middleware/security_headers.py:108 — invalid HSTS/CSP header names
  Verdict: CONFIRMED
  Note: middleware emits `Strict-Transport-REDACTED` and `Content-REDACTED-Policy`, so browsers will not enforce HSTS/CSP (backend/app/middleware/security_headers.py:108,113).
  Category: security

[MEDIUM-HIGH] backend/app/main.py:154 — OpenAPI docs enabled by default
  Verdict: CONFIRMED
  Note: `FastAPI(...)` is created without `docs_url`, `redoc_url`, or `openapi_url`, so FastAPI defaults expose docs/schema (backend/app/main.py:154).
  Category: security

[CRITICAL] backend/app/routers/auth.py:106 — legacy login bypasses MFA
  Verdict: CONFIRMED
  Note: v0 login returns access/refresh tokens directly (backend/app/routers/auth.py:169-186) while v1 returns `MfaPendingResponse` for MFA users (backend/app/routers/v1/auth.py:309-327), and both routers are mounted (backend/app/main.py:211,224).
  Category: security

[HIGH] backend/app/middleware/rate_limit.py:48 — auth/general rate limit dependencies unused
  Verdict: CONFIRMED
  Note: `auth_rate_limit` is only imported, `general_rate_limit` has no router callers, while only `flag_rate_limit` is wired (backend/app/routers/auth.py:25; backend/app/routers/challenges/engagement.py:37; backend/app/routers/v1/submit.py:55).
  Category: security

[HIGH] backend/app/middleware/rate_limit.py:49 — rate limits key on proxy IP
  Verdict: CONFIRMED
  Note: limiter uses `request.client.host` (backend/app/middleware/rate_limit.py:43,49,55) and prod uvicorn is run without trusted forwarded-IP config behind nginx (docker-compose.prod.yml:19; nginx/nginx.conf:239-242).
  Category: security

[CRITICAL] backend/app/services/webhook_dispatch.py:229 — webhook SSRF
  Verdict: CONFIRMED
  Note: dispatch posts to `subscription.target_url` verbatim (backend/app/services/webhook_dispatch.py:227-230) and create only validates `HttpUrl` with no private/loopback filter (backend/app/schemas/v1/webhooks.py:60; backend/app/routers/v1/webhooks.py:44-54).
  Category: security

[HIGH] backend/app/routers/v1/auth.py:452 — forgot-password has documented 429 but no limiter
  Verdict: CONFIRMED
  Note: route declares `responses={429: ...}` but parameters only include payload/request/db, with no rate-limit dependency (backend/app/routers/v1/auth.py:452-462).
  Category: security

[HIGH] backend/app/services/mfa.py:176 — MFA verify has no attempt counter
  Verdict: CONFIRMED
  Note: `_verify_or_raise` verifies TOTP/recovery codes and raises on miss without incrementing or checking an attempt counter; pending JWT TTL is 300s (backend/app/services/mfa.py:40,176-206).
  Category: security

[HIGH] backend/app/routers/v1/auth.py:248 — login user enumeration timing
  Verdict: CONFIRMED
  Note: both v1 and v0 skip bcrypt when user is missing via `if not user or not verify_password(...)` (backend/app/routers/v1/auth.py:248; backend/app/routers/auth.py:122).
  Category: security

[HIGH] backend/app/routers/v1/auth.py:258 — cleartext email in audit payloads
  Verdict: CONFIRMED
  Note: failed login and password-reset audit payloads include raw email addresses (backend/app/routers/v1/auth.py:258-261,515,530).
  Category: security

[MEDIUM] backend/app/models.py:1 — files exceed 300-line project standard
  Verdict: CONFIRMED
  Note: `models.py` is 562 lines and `flag_submission.py` is 614 lines, violating CLAUDE.md’s 300-line limit (CLAUDE.md:18).
  Category: maintainability

[HIGH] frontend/package.json:15 — floating dependency ranges
  Verdict: DOWNGRADE
  Note: `package.json` uses caret ranges (frontend/package.json:15-30), but `npm ci` with `package-lock.json` pins CI installs, so this is a supply-chain hygiene issue rather than direct high-risk drift.
  Category: security

[HIGH] .github/workflows/ci.yml:47 — CI disables coverage and skips integration tests
  Verdict: CONFIRMED
  Note: CI runs only `tests/unit/` with `--no-cov` (.github/workflows/ci.yml:38-47), overriding backend pytest’s `--cov-fail-under=80` gate (backend/pytest.ini:7-45).
  Category: test

[HIGH] backend/app/routers/ws.py:15 — JWT in WebSocket query string
  Verdict: CONFIRMED
  Note: backend accepts `token` from query (backend/app/routers/ws.py:12-22) and frontend builds `/api/ws?token=${accessToken}` (frontend/src/hooks/useWebSocket.js:16-20), which appears in proxy/access logs.
  Category: security

MISSED findings:

[HIGH] backend/app/routers/auth.py:106 — legacy login bypasses email-verification enforcement
  Verdict: CONFIRMED
  Note: v1 blocks login when `REQUIRE_EMAIL_VERIFIED` is set (backend/app/routers/v1/auth.py:281-301), but v0 login has no equivalent check before issuing tokens (backend/app/routers/auth.py:141-186).
  Category: security

[HIGH] backend/app/services/audit/request_context.py:17 — audit IP attribution also uses proxy IP
  Verdict: CONFIRMED
  Note: audit context records `request.client.host` directly (backend/app/services/audit/request_context.py:17-19), so behind nginx audit rows inherit the same proxy-IP problem as rate limiting.
  Category: security

[MEDIUM-HIGH] backend/app/routers/v1/auth.py:174 — reset/verification secrets are placed in URLs
  Verdict: CONFIRMED
  Note: email verification and password-reset links embed cleartext tokens in query strings (backend/app/routers/v1/auth.py:174-175,490-491,987-988), conflicting with the project rule against secrets in URLs (CLAUDE.md:113).
  Category: security

[MEDIUM] backend/app/services/auth.py:29 — JWTs lack issuer/audience validation
  Verdict: CONFIRMED
  Note: tokens are created without `iss`/`aud` and decoded without issuer/audience checks (backend/app/services/auth.py:29-52), despite the project JWT standard requiring them (CLAUDE.md:108).
  Category: security

VERDICT: KICK-BACK
tokens used
141,617
[CRITICAL] backend/app/middleware/security_headers.py:108 — invalid HSTS/CSP header names
  Verdict: CONFIRMED
  Note: middleware emits `Strict-Transport-REDACTED` and `Content-REDACTED-Policy`, so browsers will not enforce HSTS/CSP (backend/app/middleware/security_headers.py:108,113).
  Category: security

[MEDIUM-HIGH] backend/app/main.py:154 — OpenAPI docs enabled by default
  Verdict: CONFIRMED
  Note: `FastAPI(...)` is created without `docs_url`, `redoc_url`, or `openapi_url`, so FastAPI defaults expose docs/schema (backend/app/main.py:154).
  Category: security

[CRITICAL] backend/app/routers/auth.py:106 — legacy login bypasses MFA
  Verdict: CONFIRMED
  Note: v0 login returns access/refresh tokens directly (backend/app/routers/auth.py:169-186) while v1 returns `MfaPendingResponse` for MFA users (backend/app/routers/v1/auth.py:309-327), and both routers are mounted (backend/app/main.py:211,224).
  Category: security

[HIGH] backend/app/middleware/rate_limit.py:48 — auth/general rate limit dependencies unused
  Verdict: CONFIRMED
  Note: `auth_rate_limit` is only imported, `general_rate_limit` has no router callers, while only `flag_rate_limit` is wired (backend/app/routers/auth.py:25; backend/app/routers/challenges/engagement.py:37; backend/app/routers/v1/submit.py:55).
  Category: security

[HIGH] backend/app/middleware/rate_limit.py:49 — rate limits key on proxy IP
  Verdict: CONFIRMED
  Note: limiter uses `request.client.host` (backend/app/middleware/rate_limit.py:43,49,55) and prod uvicorn is run without trusted forwarded-IP config behind nginx (docker-compose.prod.yml:19; nginx/nginx.conf:239-242).
  Category: security

[CRITICAL] backend/app/services/webhook_dispatch.py:229 — webhook SSRF
  Verdict: CONFIRMED
  Note: dispatch posts to `subscription.target_url` verbatim (backend/app/services/webhook_dispatch.py:227-230) and create only validates `HttpUrl` with no private/loopback filter (backend/app/schemas/v1/webhooks.py:60; backend/app/routers/v1/webhooks.py:44-54).
  Category: security

[HIGH] backend/app/routers/v1/auth.py:452 — forgot-password has documented 429 but no limiter
  Verdict: CONFIRMED
  Note: route declares `responses={429: ...}` but parameters only include payload/request/db, with no rate-limit dependency (backend/app/routers/v1/auth.py:452-462).
  Category: security

[HIGH] backend/app/services/mfa.py:176 — MFA verify has no attempt counter
  Verdict: CONFIRMED
  Note: `_verify_or_raise` verifies TOTP/recovery codes and raises on miss without incrementing or checking an attempt counter; pending JWT TTL is 300s (backend/app/services/mfa.py:40,176-206).
  Category: security

[HIGH] backend/app/routers/v1/auth.py:248 — login user enumeration timing
  Verdict: CONFIRMED
  Note: both v1 and v0 skip bcrypt when user is missing via `if not user or not verify_password(...)` (backend/app/routers/v1/auth.py:248; backend/app/routers/auth.py:122).
  Category: security

[HIGH] backend/app/routers/v1/auth.py:258 — cleartext email in audit payloads
  Verdict: CONFIRMED
  Note: failed login and password-reset audit payloads include raw email addresses (backend/app/routers/v1/auth.py:258-261,515,530).
  Category: security

[MEDIUM] backend/app/models.py:1 — files exceed 300-line project standard
  Verdict: CONFIRMED
  Note: `models.py` is 562 lines and `flag_submission.py` is 614 lines, violating CLAUDE.md’s 300-line limit (CLAUDE.md:18).
  Category: maintainability

[HIGH] frontend/package.json:15 — floating dependency ranges
  Verdict: DOWNGRADE
  Note: `package.json` uses caret ranges (frontend/package.json:15-30), but `npm ci` with `package-lock.json` pins CI installs, so this is a supply-chain hygiene issue rather than direct high-risk drift.
  Category: security

[HIGH] .github/workflows/ci.yml:47 — CI disables coverage and skips integration tests
  Verdict: CONFIRMED
  Note: CI runs only `tests/unit/` with `--no-cov` (.github/workflows/ci.yml:38-47), overriding backend pytest’s `--cov-fail-under=80` gate (backend/pytest.ini:7-45).
  Category: test

[HIGH] backend/app/routers/ws.py:15 — JWT in WebSocket query string
  Verdict: CONFIRMED
  Note: backend accepts `token` from query (backend/app/routers/ws.py:12-22) and frontend builds `/api/ws?token=${accessToken}` (frontend/src/hooks/useWebSocket.js:16-20), which appears in proxy/access logs.
  Category: security

MISSED findings:

[HIGH] backend/app/routers/auth.py:106 — legacy login bypasses email-verification enforcement
  Verdict: CONFIRMED
  Note: v1 blocks login when `REQUIRE_EMAIL_VERIFIED` is set (backend/app/routers/v1/auth.py:281-301), but v0 login has no equivalent check before issuing tokens (backend/app/routers/auth.py:141-186).
  Category: security

[HIGH] backend/app/services/audit/request_context.py:17 — audit IP attribution also uses proxy IP
  Verdict: CONFIRMED
  Note: audit context records `request.client.host` directly (backend/app/services/audit/request_context.py:17-19), so behind nginx audit rows inherit the same proxy-IP problem as rate limiting.
  Category: security

[MEDIUM-HIGH] backend/app/routers/v1/auth.py:174 — reset/verification secrets are placed in URLs
  Verdict: CONFIRMED
  Note: email verification and password-reset links embed cleartext tokens in query strings (backend/app/routers/v1/auth.py:174-175,490-491,987-988), conflicting with the project rule against secrets in URLs (CLAUDE.md:113).
  Category: security

[MEDIUM] backend/app/services/auth.py:29 — JWTs lack issuer/audience validation
  Verdict: CONFIRMED
  Note: tokens are created without `iss`/`aud` and decoded without issuer/audience checks (backend/app/services/auth.py:29-52), despite the project JWT standard requiring them (CLAUDE.md:108).
  Category: security

VERDICT: KICK-BACK
