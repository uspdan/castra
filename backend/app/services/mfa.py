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
    "confirm_enrolment",
    "decode_mfa_pending_token",
    "disable_mfa",
    "issue_mfa_pending_token",
    "start_enrolment",
    "verify_login_code",
]
