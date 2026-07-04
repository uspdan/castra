"""v1 write-up DTOs — locked, ``extra="forbid"`` on every model.

The legacy ``/writeups`` router returned hand-built dicts; v1 freezes the
shapes so internal columns cannot leak and the contract is stable.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WriteupCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=50_000)
    title: Optional[str] = Field(default=None, max_length=200)


class WriteupCreatedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    title: str
    detail: str


class WriteupItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    title: str
    content: str
    author_display_name: Optional[str] = None
    rating: float = Field(ge=0)
    rating_count: int = Field(ge=0)
    created_at: datetime


class WriteupListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[WriteupItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(ge=1)


class WriteupRateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)


class WriteupRatingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: float = Field(ge=0)
    rating_count: int = Field(ge=0)


class WriteupApproveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    detail: str
