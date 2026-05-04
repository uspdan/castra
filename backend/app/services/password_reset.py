"""Password-reset token issue + redeem.

Sprint 6. Tokens are 32-byte cryptographically random secrets,
URL-safe-base64-encoded for the email link, sha256-hashed at rest.
The cleartext is returned by :func:`issue_token` once and never
persisted; the hash is what lives in
``password_reset_tokens.token_hash``.

Single-use semantics: a successful redeem sets ``used_at`` so a
later attempt with the same token fails validation.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import PasswordResetToken, User
from app.services.auth import hash_password


class InvalidResetToken(ValueError):
    """Raised when a redeem attempt fails for any reason.

    The router maps this to a generic 400 so we don't leak which
    branch (unknown / expired / used) failed.
    """


def _hash_cleartext(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_token(db: AsyncSession, user: User) -> str:
    """Generate a fresh single-use token for ``user``.

    Returns the cleartext token (URL-safe base64) for embedding in
    the email link. Inserts a row with sha256(cleartext) under
    ``token_hash`` and TTL controlled by
    ``settings.PASSWORD_RESET_TTL_MINUTES``. Caller is responsible
    for committing the surrounding transaction.
    """

    settings = get_settings()
    cleartext = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_cleartext(cleartext),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        used_at=None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.flush()
    return cleartext


async def redeem_token(
    db: AsyncSession,
    cleartext: str,
    new_password: str,
) -> User:
    """Validate ``cleartext`` and set ``new_password`` on the owner.

    Raises :class:`InvalidResetToken` on any failure (unknown,
    expired, already-used). On success: marks token used, sets
    new password (hashed), flushes. Caller commits.
    """

    if not cleartext:
        raise InvalidResetToken("token missing")
    if len(new_password) < 8:
        raise InvalidResetToken("password too short")

    token_hash = _hash_cleartext(cleartext)
    row: Optional[PasswordResetToken] = (
        await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
    ).scalars().first()
    if row is None:
        raise InvalidResetToken("token not found")
    if row.used_at is not None:
        raise InvalidResetToken("token already used")
    if row.expires_at < datetime.now(timezone.utc):
        raise InvalidResetToken("token expired")

    user: Optional[User] = (
        await db.execute(select(User).where(User.id == row.user_id))
    ).scalars().first()
    if user is None:
        raise InvalidResetToken("user not found")

    user.hashed_password = hash_password(new_password)
    row.used_at = datetime.now(timezone.utc)
    await db.flush()
    return user


__all__ = ["InvalidResetToken", "issue_token", "redeem_token"]
