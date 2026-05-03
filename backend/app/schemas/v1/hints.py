"""v1 hint-unlock response model.

The hint-unlock endpoint takes no body — the next still-locked hint is
selected server-side. The response carries the index, text, and cost
declared in the manifest. ``cost`` defaults to 0 for legacy seed
challenges whose hints are bare strings.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HintUnlockResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    text: str
    cost: int = Field(default=0, ge=0)
