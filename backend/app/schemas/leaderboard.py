from typing import Optional

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    display_name: Optional[str] = None
    team: Optional[str] = None
    total_points: int = 0
    total_solves: int = 0
    current_streak: int = 0
    longest_streak: int = 0


class TeamStats(BaseModel):
    team: str
    total_points: int = 0
    total_solves: int = 0
    member_count: int = 0
    avg_points_per_member: float = 0.0


class WeeklyEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    display_name: Optional[str] = None
    team: Optional[str] = None
    weekly_points: int = 0
    weekly_solves: int = 0
