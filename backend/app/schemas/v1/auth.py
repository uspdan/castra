"""v1 auth request / response models — locked contract.

The legacy ``/auth/*`` endpoints return ad-hoc dicts (and the user
columns of whatever the SQLAlchemy ``User`` row happens to expose).
The v1 surface freezes the shape: every response is a pydantic model
with ``ConfigDict(extra="forbid")`` so an unintended column cannot
leak. Every request is schema-validated at the boundary
(CLAUDE.md §3.1). Phase 12 (post-slice 21) — front-door
auth migration.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{2,32}$")


class AuthUser(BaseModel):
    """Locked user shape returned alongside auth responses."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    username: str
    display_name: str
    email: str
    role: str
    team: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class AuthRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=64)
    team: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        return v

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = (v or "").strip()
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "username must be 2-32 chars of letters/digits/_/-/."
            )
        return v

    @field_validator("team")
    @classmethod
    def _team(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ("red", "blue"):
            raise ValueError("team must be 'red' or 'blue'")
        return v


class AuthLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return (v or "").strip().lower()


class AuthRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, max_length=4096)


class AuthLogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: Optional[str] = Field(default=None, max_length=4096)


class AuthTokenPairResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: AuthUser
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthRefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"


class AuthLogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
