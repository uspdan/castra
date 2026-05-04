import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    operator = "operator"
    admin = "admin"


class TeamType(str, enum.Enum):
    red = "red"
    blue = "blue"


class InstanceStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    stopped = "stopped"
    failed = "failed"


def utcnow():
    return datetime.now(timezone.utc)


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

    solves = relationship("Solve", back_populates="user", lazy="selectin")
    instances = relationship("ChallengeInstance", back_populates="user", lazy="selectin")
    writeups = relationship("Writeup", back_populates="user", lazy="selectin")
    streak = relationship("Streak", back_populates="user", uselist=False, lazy="selectin")


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
    # ``challenge_flags`` table. Legacy seed challenges keep using this
    # column until Phase 8's validator registry replaces the
    # submission path.
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


class Solve(Base):
    __tablename__ = "solves"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_solve_user_challenge"),
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


class HintUnlock(Base):
    __tablename__ = "hint_unlocks"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", "hint_index", name="uq_hint_user_challenge_index"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    hint_index = Column(Integer, nullable=False)
    unlocked_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


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
    status = Column(Enum(InstanceStatus), default=InstanceStatus.pending, nullable=False)
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
    # (``egress-proxied-sidecar`` profile). Tracks the docker container
    # id of the dedicated tinyproxy spawned alongside the challenge so
    # cleanup paths can remove it when the instance stops.
    sidecar_container_id = Column(String(100), nullable=True)

    user = relationship("User", back_populates="instances")
    challenge = relationship("Challenge")


class Writeup(Base):
    __tablename__ = "writeups"
    __table_args__ = (
        UniqueConstraint("user_id", "challenge_id", name="uq_writeup_user_challenge"),
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
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="writeups")
    challenge = relationship("Challenge")


class Streak(Base):
    __tablename__ = "streaks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    current_streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    last_solve_date = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="streak")


class Competition(Base):
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=False)
    challenge_ids = Column(JSON, default=list)
    is_active = Column(Boolean, default=False, nullable=False)
    hints_disabled = Column(Boolean, default=True, nullable=False)
    format = Column(String(50), default="jeopardy")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLedger(Base):
    """Append-only, hash-chained audit ledger.

    Writes are funnelled through services.audit.ledger.append() — never
    construct or mutate rows of this table directly. UPDATE and DELETE are
    refused at the DB level by triggers installed in migration 002.
    """

    __tablename__ = "audit_ledger"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    seq = Column(BigInteger, nullable=False, unique=True)
    prev_hash = Column(String(64), nullable=False)
    this_hash = Column(String(64), nullable=False, unique=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor_type = Column(String(32), nullable=False)
    actor_id = Column(String(64), nullable=True)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(128), nullable=True)
    ip_address = Column(String(64), nullable=True)
    request_id = Column(String(64), nullable=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    message = Column(Text, nullable=True)
    notification_type = Column(String(50), default="info")
    is_global = Column(Boolean, default=False, nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


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


class ChallengeFlag(Base):
    """Typed flag definition for a v1-loaded challenge.

    One row per flag declared in the manifest. ``flag_type`` names the
    validator plugin (Phase 8) that will process submissions; ``config``
    holds the validator-specific payload (e.g. regex pattern,
    multi-part list). ``value_hash`` is populated only for the ``exact``
    type, where the cleartext is never stored.
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

    Phase 7 stores path + sha256; Phase 8 / 11 will resolve the path to
    a sandboxed read-only mount when the validator runs.
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


class WebhookDelivery(Base):
    """One row per outbound webhook attempt (slice 6).

    Captures the canonical body, signing-time delivery_id, attempt
    number, status word + HTTP status, wall-clock duration, and any
    error message. Provides the data the v1 list-deliveries endpoint
    surfaces and the input for the replay endpoint (the canonical
    body is re-signed against the *current* subscription secret on
    replay so secret rotation invalidates outstanding deliveries
    cleanly).

    Append-only; no soft delete. Operators wanting history retention
    bounds get a separate scheduler job in a future slice.
    """

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index(
            "ix_webhook_deliveries_subscription_created",
            "subscription_id",
            "created_at",
        ),
        Index("ix_webhook_deliveries_delivery_id", "delivery_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(
        Integer,
        ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(64), nullable=False)
    delivery_id = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    attempt = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False)
    http_status = Column(Integer, nullable=True)
    response_ms = Column(Integer, nullable=True)
    error = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class WebhookSubscription(Base):
    """Outbound webhook subscription owned by an admin.

    Phase 12 (slice 5). When an audit-ledger event matching the
    subscription's ``events`` list fires, the dispatcher POSTs a
    canonical JSON envelope to ``target_url`` with an
    ``X-Siege-Signature`` HMAC-SHA256 header. ``secret`` is generated
    server-side at create time and surfaced to the admin **once** in
    the create response — subsequent reads (list / detail) omit it,
    matching the secret-distribution model GitHub / Stripe webhooks
    use.

    ``last_delivery_at`` / ``last_status`` / ``last_error`` track the
    most recent attempt for observability. A full deliveries history
    table is a future slice; the inline "last attempt" fields are
    enough for the admin UI's "is this hook healthy" indicator.
    """

    __tablename__ = "webhook_subscriptions"
    __table_args__ = (
        Index("ix_webhook_subscriptions_owner", "owner_user_id"),
        Index("ix_webhook_subscriptions_active", "is_active"),
    )

    id = Column(Integer, primary_key=True, index=True)
    owner_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    name = Column(String(200), nullable=False)
    target_url = Column(String(500), nullable=False)
    secret = Column(String(128), nullable=False)
    events = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_delivery_at = Column(DateTime(timezone=True), nullable=True)
    last_status = Column(String(32), nullable=True)
    last_error = Column(String(500), nullable=True)


class SolvedFlag(Base):
    """Per-flag attribution row.

    Phase 12 (slice 3) sidecar to the per-challenge :class:`Solve`
    table. ``Solve`` still represents "challenge captured" and drives
    the scoreboard; this table records *which* flag the user matched
    so multi-flag challenges can expose per-flag progress without
    changing the scoring contract.

    For legacy single-flag challenges (no ``ChallengeFlag`` rows),
    ``flag_id`` is the sentinel ``"legacy"`` so the schema's NOT NULL
    constraint is satisfied without a special-case nullable column.
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

