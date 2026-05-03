"""Artifact files distributed alongside a challenge.

Artifacts are user-facing files (logs, packet captures, memory dumps)
the player downloads to complete the challenge. The manifest pins each
artifact by SHA-256 so the platform can verify integrity at load time
and reject tampered or replaced files.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
# Reject absolute paths and parent traversal. Forward slashes only —
# manifests are platform-agnostic and Windows-style backslashes are not
# accepted in artefact paths.
_PATH_RE = re.compile(r"^[A-Za-z0-9._\-/]+$")


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    path: str = Field(min_length=1, max_length=512)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: Optional[int] = Field(default=None, ge=0, le=10 * 1024 * 1024 * 1024)
    description: Optional[str] = Field(default=None, max_length=500)

    @field_validator("path")
    @classmethod
    def _path_safe(cls, v: str) -> str:
        if v.startswith("/"):
            raise ValueError("artifact path must be relative")
        if ".." in v.split("/"):
            raise ValueError("artifact path must not traverse parents")
        if not _PATH_RE.match(v):
            raise ValueError("artifact path contains disallowed characters")
        return v

    @field_validator("sha256")
    @classmethod
    def _sha_lower_hex(cls, v: str) -> str:
        v = v.lower()
        if not _SHA256_RE.match(v):
            raise ValueError("sha256 must be 64 lowercase hex chars")
        return v
