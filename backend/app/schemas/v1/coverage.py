"""v1 ATT&CK coverage response models.

Per-technique aggregate counts across the released challenge catalogue:
how many challenges reference each technique, how many of those the
viewer has solved. Useful for skill-tree dashboards and gap analysis.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class AttackCoverageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technique_id: str = Field(min_length=1, max_length=16)
    challenge_count: int = Field(ge=0)
    solved_by_viewer: int = Field(ge=0)


class AttackCoverageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: List[AttackCoverageEntry]
    total_techniques: int = Field(ge=0)
    total_challenges: int = Field(ge=0)
