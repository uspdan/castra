import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]*[a-z0-9]$")
FLAG_PATTERN = re.compile(r"^CTF\{.+\}$")
ALLOWED_TEAMS = ("red", "blue")


def _validate_slug(v: str) -> str:
    if not SLUG_PATTERN.match(v):
        raise ValueError(
            "Slug must be lowercase alphanumeric with hyphens, length >= 2"
        )
    return v


def _validate_flag(v: str) -> str:
    if not FLAG_PATTERN.match(v):
        raise ValueError("Flag must be in CTF{REDACTED} format")
    return v


class ChallengeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=2, max_length=64)
    description: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=100)
    team: str
    difficulty: int = Field(..., ge=1, le=5)
    points: int = Field(..., ge=1, le=10000)
    flag: str
    hints: List[Dict[str, Any]] = []
    skills: List[str] = []
    mitre_techniques: List[str] = []
    docker_image: str = Field(..., min_length=1, max_length=300)
    docker_port: int = Field(..., ge=1, le=65535)
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


class ChallengeUpdate(BaseModel):
    slug: Optional[str] = Field(None, min_length=2, max_length=64)
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    team: Optional[str] = None
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    points: Optional[int] = Field(None, ge=1, le=10000)
    flag: Optional[str] = None
    hints: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None
    mitre_techniques: Optional[List[str]] = None
    docker_image: Optional[str] = Field(None, min_length=1, max_length=300)
    docker_port: Optional[int] = Field(None, ge=1, le=65535)
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


class ChallengeResponse(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    category: str
    team: str
    difficulty: int
    points: int
    hints: List[Dict[str, Any]] = []
    skills: List[str] = []
    mitre_techniques: List[str] = []
    docker_image: str
    docker_port: int
    prerequisite_ids: List[int] = []
    is_released: bool
    released_at: Optional[datetime] = None
    created_at: datetime
    solve_count: int = 0
    user_solved: bool = False
    first_blood_user: Optional[str] = None

    model_config = {"from_attributes": True}


class ChallengeListResponse(BaseModel):
    items: List[ChallengeResponse]
    total: int
    page: int
    per_page: int


class FlagSubmission(BaseModel):
    flag: str = Field(..., min_length=1, max_length=512)


class HintResponse(BaseModel):
    index: int
    text: str
    cost: int


class FeedbackCreate(BaseModel):
    difficulty_rating: int
    quality_rating: int
    feedback_text: Optional[str] = None

    @field_validator("difficulty_rating", "quality_rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("Rating must be 1-5")
        return v
