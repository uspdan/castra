"""Time-bounded competition windows (jeopardy / KOTH / attack-defence)."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)

from app.models._base import Base, utcnow


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


__all__ = ["Competition"]
