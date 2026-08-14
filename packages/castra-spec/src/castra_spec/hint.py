"""Progressive hints for a challenge."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Hint(BaseModel):
    """One hint, with the points cost incurred when it is unlocked.

    The platform deducts ``cost`` from the awarded score when the user
    has unlocked this hint before solving. The cost may be 0 (free
    hint).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=2000)
    cost: int = Field(default=0, ge=0, le=10_000)
