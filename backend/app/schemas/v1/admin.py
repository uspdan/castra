"""v1 admin write surface — locked request / response models.

Wraps challenge CRUD, release, user role updates, and the seed
trigger under a single locked DTO family. The legacy ``/admin/*`` and
``/challenges/*`` admin endpoints stay live for compat; this surface
is the one the migrated Playwright fixture (and any external
operators) drive.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.challenge import (
    _validate_flag,
    _validate_slug,
    ALLOWED_TEAMS,
)


# ---------------------------------------------------------------------------
# Challenge create / update / release / delete
# ---------------------------------------------------------------------------
class AdminChallengeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=64)
    description: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=100)
    team: str
    difficulty: int = Field(ge=1, le=5)
    points: int = Field(ge=1, le=10_000)
    flag: str
    hints: List[Dict[str, Any]] = []
    skills: List[str] = []
    mitre_techniques: List[str] = []
    docker_image: str = Field(min_length=1, max_length=300)
    docker_port: int = Field(ge=1, le=65_535)
    docker_config: Dict[str, Any] = {}
    prerequisite_ids: List[int] = []

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: str) -> str:
        return _validate_slug(v)

    @field_validator("flag")
    @classmethod
    def _flag(cls, v: str) -> str:
        return _validate_flag(v)

    @field_validator("team")
    @classmethod
    def _team(cls, v: str) -> str:
        if v not in ALLOWED_TEAMS:
            raise ValueError(f"team must be one of {ALLOWED_TEAMS}")
        return v


class AdminChallengeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Optional[str] = Field(default=None, min_length=2, max_length=64)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, min_length=1)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    team: Optional[str] = None
    difficulty: Optional[int] = Field(default=None, ge=1, le=5)
    points: Optional[int] = Field(default=None, ge=1, le=10_000)
    flag: Optional[str] = None
    hints: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None
    mitre_techniques: Optional[List[str]] = None
    docker_image: Optional[str] = Field(default=None, min_length=1, max_length=300)
    docker_port: Optional[int] = Field(default=None, ge=1, le=65_535)
    docker_config: Optional[Dict[str, Any]] = None
    prerequisite_ids: Optional[List[int]] = None

    @field_validator("slug")
    @classmethod
    def _slug(cls, v: Optional[str]) -> Optional[str]:
        return _validate_slug(v) if v is not None else v

    @field_validator("flag")
    @classmethod
    def _flag(cls, v: Optional[str]) -> Optional[str]:
        return _validate_flag(v) if v is not None else v

    @field_validator("team")
    @classmethod
    def _team(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_TEAMS:
            raise ValueError(f"team must be one of {ALLOWED_TEAMS}")
        return v


class AdminChallengeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    slug: str
    title: str
    category: str
    team: str
    difficulty: int = Field(ge=1, le=5)
    points: int = Field(ge=1)
    is_released: bool
    is_active: bool
    released_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# User role / status updates
# ---------------------------------------------------------------------------
class AdminUserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Optional[str] = None
    team: Optional[str] = None
    is_active: Optional[bool] = None
    display_name: Optional[str] = Field(default=None, max_length=100)

    @field_validator("role")
    @classmethod
    def _role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("operator", "admin"):
            raise ValueError("role must be 'operator' or 'admin'")
        return v

    @field_validator("team")
    @classmethod
    def _team(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ALLOWED_TEAMS:
            raise ValueError(f"team must be one of {ALLOWED_TEAMS}")
        return v


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    username: str
    email: str
    display_name: str
    role: str
    team: Optional[str] = None
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Multi-flag challenge flags (typed validator plugins)
# ---------------------------------------------------------------------------
class AdminChallengeFlagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag_id: str = Field(min_length=1, max_length=64)
    flag_type: str = Field(min_length=1, max_length=32)
    points: int = Field(ge=1, le=10_000)
    label: Optional[str] = Field(default=None, max_length=200)
    # ``value`` is the cleartext for ``exact`` flags (hashed before
    # insert) or the validator-specific config for typed flags.
    value: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class AdminChallengeFlagResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    flag_id: str
    flag_type: str
    points: int = Field(ge=1)
    label: Optional[str] = None


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------
class AdminSeedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: int = Field(ge=0)
    skipped: int = Field(ge=0)
