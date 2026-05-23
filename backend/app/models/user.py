"""User identity + per-user credential / verification tokens."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.models._base import Base, TeamType, UserRole, utcnow


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(200), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.operator, nullable=False)
    team = Column(Enum(TeamType), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    # Sprint 7 Phase C — TOTP MFA.
    mfa_secret = Column(String(64), nullable=True)
    mfa_enabled = Column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    # Sprint 9 Phase B — login is operator-gated on this.
    email_verified = Column(
        Boolean, default=False, nullable=False, server_default="false"
    )

    solves = relationship("Solve", back_populates="user", lazy="selectin")
    instances = relationship(
        "ChallengeInstance", back_populates="user", lazy="selectin"
    )
    writeups = relationship("Writeup", back_populates="user", lazy="selectin")
    streak = relationship(
        "Streak", back_populates="user", uselist=False, lazy="selectin"
    )


class Streak(Base):
    __tablename__ = "streaks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False
    )
    current_streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    last_solve_date = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="streak")


class PasswordResetToken(Base):
    """Single-use token issued by ``POST /auth/forgot-password``.

    Sprint 6. ``token_hash`` stores sha256(cleartext) so a DB leak
    never exposes a usable reset link. The cleartext is emailed to
    the user once via ``services/email.py`` and never persisted.
    Single-use — ``redeem_token`` sets ``used_at`` on success and
    later attempts fail validation.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class MfaRecoveryCode(Base):
    """Single-use 8-character recovery code for an MFA-enrolled user.

    Sprint 7. The cleartext is shown once at enrol-confirm time and
    never persisted; only the sha256 hash lives here. ``used_at``
    flips on first redeem so a code cannot be replayed.
    """

    __tablename__ = "mfa_recovery_codes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash = Column(String(64), nullable=False, unique=True, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class EmailVerificationToken(Base):
    """Single-use token issued by ``POST /auth/register`` (and by
    ``POST /auth/resend-verification``).

    Sprint 9 Phase B. Same hash-at-rest discipline as
    ``PasswordResetToken``: cleartext is mailed once, sha256 hash
    lives in this table.
    """

    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


__all__ = [
    "EmailVerificationToken",
    "MfaRecoveryCode",
    "PasswordResetToken",
    "Streak",
    "User",
]
