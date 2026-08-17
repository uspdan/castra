"""Top-level v1 challenge manifest.

The manifest is the single source of truth for a challenge: its
identity, scoring, container, flags, hints, artefacts, and tests. The
platform's loader reads ``manifest.yaml`` (or ``manifest.json``) and
validates it against this model.

Backwards-incompatible changes to v1 require a new ``spec_version``
literal. Additive (optional) changes are permitted within v1 provided
existing manifests continue to validate unchanged.
"""

from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .artifact import Artifact
from .author import Author
from .container import Container
from .flag import Flag
from .hint import Hint
from .tests import TestSuite


SPEC_VERSION: Literal["1"] = "1"


_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,99}[a-z0-9])?$")
_TEAMS = ("red", "blue", "purple")


class ChallengeManifest(BaseModel):
    """v1 manifest. Top-level entry-point parsed by the loader."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    spec_version: Literal["1"]
    slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=10_000)

    team: Literal["red", "blue", "purple"]
    category: str = Field(min_length=1, max_length=100)

    difficulty: int = Field(ge=1, le=5)
    points: int = Field(ge=1, le=100_000)

    license: str = Field(min_length=1, max_length=100)
    author: Author

    container: Container

    flags: List[Flag] = Field(min_length=1, max_length=20)
    hints: List[Hint] = Field(default_factory=list, max_length=20)
    artifacts: List[Artifact] = Field(default_factory=list, max_length=200)

    skills: List[str] = Field(default_factory=list, max_length=20)
    mitre_techniques: List[str] = Field(default_factory=list, max_length=20)
    prerequisites: List[str] = Field(default_factory=list, max_length=20)

    tests: TestSuite = Field(default_factory=TestSuite)

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "slug must be 1-100 lowercase alphanumerics with internal hyphens"
            )
        return v

    @field_validator("mitre_techniques")
    @classmethod
    def _mitre_format(cls, v: List[str]) -> List[str]:
        # Accept T1078, T1078.001, TA0001 (tactic). Reject anything else
        # so authors don't paste prose in.
        pattern = re.compile(r"^T[A-Z]?\d{3,4}(\.\d{3})?$")
        for tech in v:
            if not pattern.match(tech):
                raise ValueError(f"mitre_techniques entry not recognised: {tech!r}")
        return v

    @field_validator("prerequisites")
    @classmethod
    def _prereq_slugs(cls, v: List[str]) -> List[str]:
        for s in v:
            if not _SLUG_RE.match(s):
                raise ValueError(f"prerequisite is not a valid slug: {s!r}")
        return v

    @model_validator(mode="after")
    def _check_flag_ids(self) -> "ChallengeManifest":
        ids = [f.id for f in self.flags]
        if len(set(ids)) != len(ids):
            raise ValueError("flags[].id values must be unique within a challenge")
        return self

    @model_validator(mode="after")
    def _check_test_refs(self) -> "ChallengeManifest":
        if not self.tests.cases:
            return self
        valid = {f.id for f in self.flags}
        for case in self.tests.cases:
            if case.flag_id not in valid:
                raise ValueError(
                    f"tests.cases[{case.name!r}].flag_id refers to unknown flag {case.flag_id!r}"
                )
        return self

    @model_validator(mode="after")
    def _slug_not_self_prereq(self) -> "ChallengeManifest":
        if self.slug in self.prerequisites:
            raise ValueError("a challenge cannot list itself as a prerequisite")
        return self
