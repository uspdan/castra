"""v1 challenge response models — locked public contract."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PublicHint(BaseModel):
    """A hint as exposed publicly: text only when unlocked."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    locked: bool
    text: Optional[str] = None
    cost: int = Field(default=0, ge=0)


class PublicTopSolver(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    username: str
    solved_at: datetime
    points_awarded: int


class PublicChallengePrerequisite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    user_completed: bool


class PublicChallengeListItem(BaseModel):
    """Compact list-view of a challenge.

    No internal IDs, no docker_image, no flag_hash. ``team`` /
    ``category`` / ``difficulty`` are normalised string enums.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    category: str
    difficulty: int = Field(ge=1, le=5)
    points: int = Field(ge=0)
    team: str
    solve_count: int = Field(ge=0)
    user_solved: bool
    first_blood_user: Optional[str] = None
    released_at: Optional[datetime] = None


class PublicChallengeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[PublicChallengeListItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)


class PublicChallengeDetail(BaseModel):
    """Full detail-view of a challenge.

    ``hints`` carries text only for hints the viewer has unlocked.
    ``mitre_techniques`` is the canonical ATT&CK list. Internal
    fields (docker_image, docker_port, manifest_sha256, source_path)
    are deliberately absent; admin endpoints surface those.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    description: str
    category: str
    difficulty: int = Field(ge=1, le=5)
    points: int = Field(ge=0)
    team: str
    skills: List[str] = Field(default_factory=list)
    mitre_techniques: List[str] = Field(default_factory=list)
    hints: List[PublicHint] = Field(default_factory=list)
    solve_count: int = Field(ge=0)
    user_solved: bool
    top_solvers: List[PublicTopSolver] = Field(default_factory=list)
    prerequisites: List[PublicChallengePrerequisite] = Field(default_factory=list)
    writeup_count: int = Field(ge=0)
    released_at: Optional[datetime] = None
