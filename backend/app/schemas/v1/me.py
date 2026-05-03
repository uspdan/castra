"""v1 ``GET /api/v1/me`` response model.

The legacy ``GET /auth/me`` returns the SQLAlchemy ``User`` row dumped
through Pydantic — that surface leaks whichever columns the model has
plus computed totals tacked on at the router. v1 freezes the shape:
identity fields the client may need + computed totals + rank, and
nothing else.

Phase 12 (slice 21): ``id`` added so the leaderboard "highlight my
row" feature can match scoreboard rows against the viewer. A user's
own ID is not internal data — they can already see their username,
team, and totals — so exposing it here is consistent with the
locked-public-surface principle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    username: str
    display_name: str
    email: str
    role: str
    team: Optional[str] = None
    is_active: bool
    created_at: datetime

    total_points: int = Field(ge=0)
    total_solves: int = Field(ge=0)
    current_streak: int = Field(ge=0)
    rank: Optional[int] = Field(default=None, ge=1)
