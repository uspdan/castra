"""Author identity for a challenge."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Author(BaseModel):
    """Identity of the human who authored a challenge.

    Either ``email`` or ``url`` should be provided so that a reviewer can
    contact the author or follow up; we don't enforce one being present
    in v1, but the loader emits a warning when both are absent.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=320)
    url: Optional[str] = Field(default=None, max_length=500)
