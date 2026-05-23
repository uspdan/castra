"""Shared SQLAlchemy primitives + enums.

Lives at ``app.models._base`` rather than ``app.models`` so the
package's ``__init__.py`` (the public façade) doesn't have to be
the place where ``DeclarativeBase`` gets subclassed.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


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


__all__ = [
    "Base",
    "InstanceStatus",
    "TeamType",
    "UserRole",
    "utcnow",
]
