"""Test cases declared by a challenge author.

Phase 11 introduces the ``bluerange-test`` runner that consumes these
cases and exercises the validator pipeline end-to-end without standing
up the platform. v1 only requires the schema to be present so authors
can start writing tests immediately; the runner itself ships in
Phase 11.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


TestExpected = Literal["pass", "fail"]


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    flag_id: str = Field(min_length=1, max_length=64)
    submission: str = Field(min_length=1, max_length=4096)
    expected: TestExpected
    description: Optional[str] = Field(default=None, max_length=500)


class TestSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: List[TestCase] = Field(default_factory=list, max_length=200)
