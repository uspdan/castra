"""v1 scoreboard response models."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScoreboardEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    # Phase 12 (slice 21): the user's public ID. Surfaced so the
    # frontend leaderboard can highlight the viewer's own row by
    # cross-referencing :class:`app.schemas.v1.me.MeResponse.id`.
    # User IDs are not secret on this platform (they appear in
    # writeup attribution, audit ledger payloads, etc.).
    user_id: int = Field(ge=1)
    username: str
    display_name: str
    team: Optional[str] = None
    total_points: int = Field(ge=0)
    total_solves: int = Field(ge=0)
    current_streak: int = Field(ge=0)


class ScoreboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: List[ScoreboardEntry]
    team_filter: Optional[str] = None
    generated_at: datetime
