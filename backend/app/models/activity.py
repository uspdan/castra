"""Player activity records — solves, per-flag attribution, writeups,
learning-path curation."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models._base import Base, utcnow


class Solve(Base):
    __tablename__ = "solves"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "challenge_id", name="uq_solve_user_challenge"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    points_awarded = Column(Integer, nullable=False)
    hint_used = Column(Boolean, default=False, nullable=False)
    is_first_blood = Column(Boolean, default=False, nullable=False)
    time_to_solve = Column(Integer, nullable=True)
    solved_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="solves")
    challenge = relationship("Challenge", back_populates="solves")


class SolvedFlag(Base):
    """Per-flag attribution row.

    Phase 12 (slice 3) sidecar to the per-challenge :class:`Solve`
    table. ``Solve`` still represents "challenge captured" and
    drives the scoreboard; this table records *which* flag the user
    matched so multi-flag challenges can expose per-flag progress
    without changing the scoring contract.

    For legacy single-flag challenges (no ``ChallengeFlag`` rows),
    ``flag_id`` is the sentinel ``"legacy"`` so the schema's
    NOT NULL constraint is satisfied without a special-case
    nullable column.
    """

    __tablename__ = "solved_flags"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "challenge_id", "flag_id",
            name="uq_solved_flag_user_challenge_flag",
        ),
        Index("ix_solved_flags_user_id", "user_id"),
        Index("ix_solved_flags_challenge_id", "challenge_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    flag_id = Column(String(64), nullable=False)
    points_awarded = Column(Integer, nullable=False)
    is_first_blood_flag = Column(Boolean, default=False, nullable=False)
    validator_name = Column(String(64), nullable=True)
    solved_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Writeup(Base):
    __tablename__ = "writeups"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "challenge_id", name="uq_writeup_user_challenge"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    title = Column(String(200), nullable=False, server_default="")
    content = Column(Text, nullable=False)
    rating = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)
    is_approved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user = relationship("User", back_populates="writeups")
    challenge = relationship("Challenge")


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    team = Column(String(10), nullable=False)
    difficulty_range = Column(JSON, default=dict)
    challenge_order = Column(JSON, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


__all__ = ["LearningPath", "Solve", "SolvedFlag", "Writeup"]
