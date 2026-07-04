"""v1 competition DTOs — locked, ``extra="forbid"`` on every model."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_FORMATS = ("jeopardy", "attack-defense")


class CompetitionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    challenge_ids: List[int] = Field(default_factory=list)
    is_active: bool = False
    hints_disabled: bool = True
    format: str = "jeopardy"

    @field_validator("format")
    @classmethod
    def _format(cls, v: str) -> str:
        if v not in _FORMATS:
            raise ValueError(f"format must be one of {_FORMATS}")
        return v

    @model_validator(mode="after")
    def _window(self) -> "CompetitionCreateRequest":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be strictly after starts_at")
        return self


class CompetitionCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    title: str
    detail: str


class CompetitionScoreboardRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    user_id: int = Field(ge=1)
    username: str
    display_name: Optional[str] = None
    team: Optional[str] = None
    total_points: int = Field(ge=0)
    total_solves: int = Field(ge=0)


class CompetitionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    title: str
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool
    is_live: bool
    challenge_count: int = Field(ge=0)
    created_at: Optional[datetime] = None


class CompetitionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    title: str
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    is_active: bool
    is_live: bool
    challenge_ids: List[int] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    scoreboard: Optional[List[CompetitionScoreboardRow]] = None


class CompetitionActivateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    detail: str
