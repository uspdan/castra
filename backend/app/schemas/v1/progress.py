"""v1 challenge-progress response model.

Per-flag breakdown for the calling user's progress on a single
challenge. Backed by the ``solved_flags`` table introduced in
Phase 12 (slice 3); challenges without v1 flag definitions report a
single synthetic ``"legacy"`` entry that mirrors the per-challenge
``Solve``.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class FlagProgressEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flag_id: str
    flag_type: str
    label: Optional[str] = None
    # ``points`` is the manifest-declared base value. ``points_awarded``
    # is the actual points the user received on capture (after the
    # first-blood / streak / hint multipliers in calculate_flag_points).
    # The two diverge for v1 multi-flag challenges where bonuses fire
    # per-flag; for legacy single-flag challenges they're equal.
    points: int = Field(ge=0)
    points_awarded: Optional[int] = Field(default=None, ge=0)
    captured: bool
    captured_at: Optional[datetime] = None
    is_first_blood_flag: Optional[bool] = None
    validator_name: Optional[str] = None


class ChallengeProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_slug: str
    flags: List[FlagProgressEntry]
    total_flags: int = Field(ge=0)
    captured_flags: int = Field(ge=0)
    total_points_possible: int = Field(ge=0)
    points_captured: int = Field(ge=0)
    fully_captured: bool
