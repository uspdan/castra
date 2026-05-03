from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class CompetitionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    challenge_ids: List[int] = []
    is_active: bool = False
    hints_disabled: bool = True
    format: str = "jeopardy"

    @field_validator("format")
    @classmethod
    def _format(cls, v: str) -> str:
        if v not in ("jeopardy", "attack-defense"):
            raise ValueError("format must be 'jeopardy' or 'attack-defense'")
        return v

    @model_validator(mode="after")
    def _check_window(self) -> "CompetitionCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be strictly after starts_at")
        return self


class CompetitionResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    challenge_ids: List[int] = []
    is_active: bool
    hints_disabled: bool
    format: str
    created_by: Optional[int] = None
    created_at: datetime
    scoreboard: Optional[List[Dict[str, Any]]] = None

    model_config = {"from_attributes": True}
