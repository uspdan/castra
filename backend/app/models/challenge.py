"""Challenge catalogue + per-challenge associations.

Challenge, ChallengeFlag, ChallengeArtifact, ChallengeFeedback,
ChallengeInstance, HintUnlock.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.models._base import Base, InstanceStatus, TeamType, utcnow


class Challenge(Base):
    __tablename__ = "challenges"
    __table_args__ = (
        Index("ix_challenges_team_category", "team", "category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(200), unique=True, index=True, nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), index=True, nullable=False)
    team = Column(Enum(TeamType), index=True, nullable=False)
    difficulty = Column(Integer, nullable=False)
    points = Column(Integer, nullable=False)
    # NULL on v1-loaded challenges: those declare flags via the
    # ``challenge_flags`` table. Legacy seed challenges keep using
    # this column.
    flag_hash = Column(String(64), nullable=True)
    hints = Column(JSON, default=list)
    skills = Column(JSON, default=list)
    mitre_techniques = Column(JSON, default=list)
    docker_image = Column(String(300), nullable=False)
    docker_port = Column(Integer, nullable=False)
    docker_config = Column(JSON, default=dict)
    prerequisite_ids = Column(JSON, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    is_released = Column(Boolean, default=False, nullable=False)
    released_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Phase 7 — bluerange-spec v1 manifest tracking.
    spec_version = Column(String(8), nullable=True)
    manifest_sha256 = Column(String(64), nullable=True)
    source_path = Column(String(500), nullable=True)
    loaded_at = Column(DateTime(timezone=True), nullable=True)
    pending_review = Column(Boolean, default=False, nullable=False)
    license = Column(String(100), nullable=True)
    author_json = Column(JSON, nullable=True)

    solves = relationship("Solve", back_populates="challenge", lazy="selectin")
    flag_definitions = relationship(
        "ChallengeFlag",
        back_populates="challenge",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    artifacts = relationship(
        "ChallengeArtifact",
        back_populates="challenge",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ChallengeFlag(Base):
    """Typed flag definition for a v1-loaded challenge.

    One row per flag declared in the manifest. ``flag_type`` names
    the validator plugin (Phase 8) that will process submissions;
    ``config`` holds the validator-specific payload (e.g. regex
    pattern, multi-part list). ``value_hash`` is populated only for
    the ``exact`` type, where the cleartext is never stored.
    """

    __tablename__ = "challenge_flags"
    __table_args__ = (
        UniqueConstraint("challenge_id", "flag_id", name="uq_challenge_flag_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(
        Integer,
        ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flag_id = Column(String(64), nullable=False)
    flag_type = Column(String(32), nullable=False)
    points = Column(Integer, nullable=False)
    label = Column(String(200), nullable=True)
    value_hash = Column(String(64), nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    challenge = relationship("Challenge", back_populates="flag_definitions")


class ChallengeArtifact(Base):
    """Manifest record of a single artifact file shipped with a challenge.

    Phase 7 stores path + sha256; Phase 8 / 11 will resolve the path
    to a sandboxed read-only mount when the validator runs.
    """

    __tablename__ = "challenge_artifacts"
    __table_args__ = (
        UniqueConstraint("challenge_id", "path", name="uq_challenge_artifact_path"),
    )

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(
        Integer,
        ForeignKey("challenges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path = Column(String(512), nullable=False)
    sha256 = Column(String(64), nullable=False)
    size_bytes = Column(BigInteger, nullable=True)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    challenge = relationship("Challenge", back_populates="artifacts")


class ChallengeFeedback(Base):
    __tablename__ = "challenge_feedback"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_feedback_user_challenge"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    difficulty_rating = Column(Integer, nullable=False)
    quality_rating = Column(Integer, nullable=False)
    feedback_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ChallengeInstance(Base):
    __tablename__ = "challenge_instances"
    __table_args__ = (
        Index("ix_instance_user_status", "user_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    container_id = Column(String(100), nullable=True)
    container_name = Column(String(200), nullable=True)
    status = Column(
        Enum(InstanceStatus), default=InstanceStatus.pending, nullable=False
    )
    assigned_ip = Column(String(50), nullable=True)
    assigned_port = Column(Integer, nullable=True)
    network_name = Column(String(200), nullable=True)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    stopped_at = Column(DateTime(timezone=True), nullable=True)
    applied_profile = Column(
        String(64), nullable=False, server_default="default-strict"
    )
    applied_digest = Column(String(71), nullable=True)
    seccomp_profile_sha256 = Column(String(64), nullable=True)
    # Phase 12 follow-up: per-instance egress-proxy sidecar
    # (``egress-proxied-sidecar`` profile).
    sidecar_container_id = Column(String(100), nullable=True)

    user = relationship("User", back_populates="instances")
    challenge = relationship("Challenge")


class HintUnlock(Base):
    __tablename__ = "hint_unlocks"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "challenge_id", "hint_index",
            name="uq_hint_user_challenge_index",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    hint_index = Column(Integer, nullable=False)
    unlocked_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


__all__ = [
    "Challenge",
    "ChallengeArtifact",
    "ChallengeFeedback",
    "ChallengeFlag",
    "ChallengeInstance",
    "HintUnlock",
]
