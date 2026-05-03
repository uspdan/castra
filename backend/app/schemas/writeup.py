from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WriteupCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=50_000)
    title: Optional[str] = Field(None, max_length=200)


class WriteupRate(BaseModel):
    rating: int = Field(..., ge=1, le=5)


class WriteupCreateAck(BaseModel):
    id: int
    title: str
    detail: str


class WriteupRatingResponse(BaseModel):
    rating: float
    rating_count: int


class WriteupListItem(BaseModel):
    id: int
    title: str
    content: str
    author_display_name: Optional[str] = None
    rating: float
    rating_count: int
    created_at: datetime


class WriteupListResponse(BaseModel):
    items: list[WriteupListItem]
    total: int
    page: int
    per_page: int
