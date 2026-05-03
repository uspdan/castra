"""v1 flag-submission request + response models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SubmitFlagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    flag: str = Field(min_length=1, max_length=8192)


class SubmitFlagResponse(BaseModel):
    """Result of a flag submission.

    ``flag_id`` and ``validator`` are populated only on a correct
    submission. They identify which v1 flag matched and which
    validator plugin reported the match — useful for clients that
    track per-flag progress in multi-flag challenges.
    """

    model_config = ConfigDict(extra="forbid")

    correct: bool
    points_awarded: Optional[int] = Field(default=None, ge=0)
    is_first_blood: Optional[bool] = None
    flag_id: Optional[str] = None
    validator: Optional[str] = None
