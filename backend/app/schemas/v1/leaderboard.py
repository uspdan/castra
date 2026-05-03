"""v1 leaderboard response models — locked contract.

The legacy ``/leaderboard/teams`` and ``/leaderboard/weekly`` endpoints
return ad-hoc lists / dicts. v1 wraps them in envelope responses with
explicit field sets so the contract is OpenAPI-derivable.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TeamLeaderboardEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: str
    total_points: int = Field(ge=0)
    total_solves: int = Field(ge=0)
    member_count: int = Field(ge=0)
    avg_points_per_member: float = Field(ge=0.0)


class TeamLeaderboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teams: List[TeamLeaderboardEntry]
    generated_at: datetime


class WeeklyLeaderboardEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1)
    user_id: int = Field(ge=1)
    username: str
    display_name: str
    team: Optional[str] = None
    total_points: int = Field(ge=0)
    total_solves: int = Field(ge=0)
    current_streak: int = Field(ge=0)


class WeeklyLeaderboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: List[WeeklyLeaderboardEntry]
    team_filter: Optional[str] = None
    week_start: datetime
    generated_at: datetime
