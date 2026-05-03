"""v1 webhook subscription DTOs.

The locked contract is:

* ``WebhookCreateRequest`` — admin sends ``name``, ``target_url``,
  ``events``. The server generates the secret.
* ``WebhookCreatedResponse`` — surfaced **once** at create time
  with ``secret`` populated. Subsequent reads omit the secret.
* ``WebhookResponse`` — returned by list / detail. No secret leak.

Phase 12 slice 5 deliberately ships no update endpoint; admins who
need to rotate a secret or change events should DELETE + re-POST.
A patch endpoint is a future slice.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# Allowed event names. Restricted to the audit-ledger event vocabulary
# the platform actually emits today; anything else is rejected at
# create time so the admin sees the failure immediately rather than
# waiting forever for a webhook that will never fire.
_KNOWN_EVENTS = {
    "challenge.flag.submit.pass",
    "challenge.flag.submit.fail",
    "challenge.released",
    "auth.register",
    "auth.login.success",
    "auth.login.failed",
    "auth.logout",
    "auth.refresh",
    "instance.launch",
    "instance.stop",
    "instance.reset",
    "instance.expired",
    "*",  # wildcard: deliver every event the platform emits
}


class WebhookCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    target_url: HttpUrl
    events: List[str] = Field(min_length=1, max_length=32)

    @field_validator("events")
    @classmethod
    def _events_known(cls, v: List[str]) -> List[str]:
        unknown = sorted(set(v) - _KNOWN_EVENTS)
        if unknown:
            raise ValueError(
                f"unknown event types: {unknown}. "
                f"Known: {sorted(_KNOWN_EVENTS)}"
            )
        if "*" in v and len(v) != 1:
            raise ValueError(
                "wildcard '*' must be the only entry when used"
            )
        # de-dupe while preserving order
        seen: set[str] = set()
        out: List[str] = []
        for entry in v:
            if entry not in seen:
                seen.add(entry)
                out.append(entry)
        return out


class WebhookResponse(BaseModel):
    """Read-side view of a subscription (no secret)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    target_url: str
    events: List[str]
    is_active: bool
    created_at: datetime
    last_delivery_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None


class WebhookCreatedResponse(WebhookResponse):
    """One-time create response. Carries the secret exactly once."""

    secret: str = Field(min_length=32)


class WebhookListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[WebhookResponse]
    total: int = Field(ge=0)
