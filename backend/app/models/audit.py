"""Audit ledger — append-only + hash-chained."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    JSON,
    String,
)

from app.models._base import Base, utcnow


class AuditLedger(Base):
    """Append-only, hash-chained audit ledger.

    Writes are funnelled through ``services.audit.ledger.append()``
    — never construct or mutate rows of this table directly.
    UPDATE and DELETE are refused at the DB level by triggers
    installed in migration 002.
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
    created_at = Column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


__all__ = ["AuditLedger"]
