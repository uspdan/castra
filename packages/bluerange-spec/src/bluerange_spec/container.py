"""Container image / port descriptor for a challenge.

v1 records the image reference and port. Phase 9 added the
``egress_allowlist`` slot that pairs with ``profile=egress-proxied`` —
manifests for that profile declare a list of FQDNs the challenge is
allowed to reach. Profile-name validation against the platform's
``PROFILES`` registry lives in the loader, not this spec; the spec
stays platform-agnostic so external tooling can parse a manifest
without importing the backend.
"""

from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
# Lowercase image references, optional registry, repository path, and
# optional tag. Validation is deliberately loose: registry hosts vary
# wildly and we'd rather accept a wider surface than block a legitimate
# image. Strict pinning is enforced by ``digest`` separately.
_IMAGE_RE = re.compile(
    r"^[a-z0-9]([a-z0-9._\-/]*[a-z0-9])?(:[a-zA-Z0-9._\-]+)?$"
)
# RFC-1123-ish FQDN: labels of [a-z0-9-] separated by dots, each label
# 1–63 chars, total length up to 253. Lower-cased on input.
_FQDN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$"
)
_EGRESS_PROFILE_NAME = "egress-proxied"


class Container(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    image: str = Field(min_length=1, max_length=300)
    port: int = Field(ge=1, le=65535)
    digest: Optional[str] = Field(default=None, min_length=71, max_length=71)
    profile: str = Field(default="default-strict", min_length=1, max_length=64)
    egress_allowlist: Optional[List[str]] = Field(default=None, max_length=64)

    @field_validator("image")
    @classmethod
    def _image_format(cls, v: str) -> str:
        if not _IMAGE_RE.match(v):
            raise ValueError(
                "image must be a valid OCI reference "
                "(lowercase, optional :tag, no digest — pin via 'digest')"
            )
        return v

    @field_validator("digest")
    @classmethod
    def _digest_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.lower()
        if not _DIGEST_RE.match(v):
            raise ValueError("digest must be of the form 'sha256:<64-hex>'")
        return v

    @field_validator("profile")
    @classmethod
    def _profile_format(cls, v: str) -> str:
        # Profile-name vs. PROFILES validation lives in the loader so
        # this package stays free of platform imports. We only enforce
        # the kebab-case shape here.
        if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError("profile must be kebab-case")
        return v

    @field_validator("egress_allowlist")
    @classmethod
    def _allowlist_entries(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned: List[str] = []
        for entry in v:
            if not isinstance(entry, str):
                raise ValueError("egress_allowlist entries must be strings")
            lowered = entry.strip().lower()
            if not _FQDN_RE.match(lowered):
                raise ValueError(
                    f"egress_allowlist entry {entry!r} is not a valid FQDN"
                )
            cleaned.append(lowered)
        return cleaned

    @model_validator(mode="after")
    def _allowlist_only_with_egress_profile(self) -> "Container":
        if (
            self.egress_allowlist is not None
            and self.profile != _EGRESS_PROFILE_NAME
        ):
            raise ValueError(
                "egress_allowlist is only valid when profile='egress-proxied'"
            )
        return self
