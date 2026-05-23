"""In-app notifications (per-user + global)."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)

from app.models._base import Base, utcnow


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


__all__ = ["Notification"]
