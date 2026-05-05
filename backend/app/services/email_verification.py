"""Email-verification token issue + redeem.

Sprint 9 Phase B. Mirrors the password-reset flow shape: a 32-byte
URL-safe secret is generated at register time, sha256-hashed at
rest, and emailed to the user. The user redeems via
``POST /auth/verify-email`` and we flip ``users.email_verified``.

TTL is longer than password-reset (24 hours) — users may not check
mail immediately after sign-up.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailVerificationToken, User


_TTL_HOURS = 24


class InvalidVerificationToken(ValueError):
    """Raised when a redeem attempt fails for any reason."""


def _hash_cleartext(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_token(db: AsyncSession, user: User) -> str:
    """Generate a fresh single-use verification token.

    Returns the cleartext for the email link. Insert is flushed
    but not committed; the caller's surrounding transaction
    commits.
    """

    cleartext = secrets.token_urlsafe(32)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_cleartext(cleartext),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=_TTL_HOURS),
            used_at=None,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.flush()
    return cleartext


async def redeem_token(db: AsyncSession, cleartext: str) -> User:
    """Validate ``cleartext`` and mark the user verified.

    Raises :class:`InvalidVerificationToken` on any failure
    (unknown / expired / already-used).
    """

    if not cleartext:
        raise InvalidVerificationToken("token missing")

    token_hash = _hash_cleartext(cleartext)
    row: Optional[EmailVerificationToken] = (
        await db.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == token_hash
            )
        )
    ).scalars().first()
    if row is None:
        raise InvalidVerificationToken("token not found")
    if row.used_at is not None:
        raise InvalidVerificationToken("token already used")
    if row.expires_at < datetime.now(timezone.utc):
        raise InvalidVerificationToken("token expired")

    user: Optional[User] = (
        await db.execute(select(User).where(User.id == row.user_id))
    ).scalars().first()
    if user is None:
        raise InvalidVerificationToken("user not found")

    user.email_verified = True
    row.used_at = datetime.now(timezone.utc)
    await db.flush()
    return user


__all__ = [
    "InvalidVerificationToken",
    "issue_token",
    "redeem_token",
]
