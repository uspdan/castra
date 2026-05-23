"""Outbound webhook subscriptions + delivery history."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)

from app.models._base import Base, utcnow


class WebhookSubscription(Base):
    """Outbound webhook subscription owned by an admin.

    Phase 12 (slice 5). When an audit-ledger event matching the
    subscription's ``events`` list fires, the dispatcher POSTs a
    canonical JSON envelope to ``target_url`` with an
    ``X-Siege-Signature`` HMAC-SHA256 header. ``secret`` is
    generated server-side at create time and surfaced to the admin
    **once** in the create response — subsequent reads (list /
    detail) omit it, matching the secret-distribution model GitHub
    / Stripe webhooks use.

    ``last_delivery_at`` / ``last_status`` / ``last_error`` track
    the most recent attempt for observability.
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


class WebhookDelivery(Base):
    """One row per outbound webhook attempt (slice 6).

    Captures the canonical body, signing-time delivery_id, attempt
    number, status word + HTTP status, wall-clock duration, and any
    error message. Provides the data the v1 list-deliveries
    endpoint surfaces and the input for the replay endpoint (the
    canonical body is re-signed against the *current* subscription
    secret on replay so secret rotation invalidates outstanding
    deliveries cleanly).

    Append-only; soft-delete is *not* a use case. Operators wanting
    retention bounds get the scheduled prune job in
    ``services/scheduler.py``.
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


__all__ = ["WebhookDelivery", "WebhookSubscription"]
