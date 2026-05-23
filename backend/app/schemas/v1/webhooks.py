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

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


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
    "auth.password.reset.request",
    "auth.password.reset.redeem",
    "auth.password.change",
    "auth.profile.update",
    "auth.account.delete",
    "auth.data.export",
    "auth.mfa.enroll",
    "auth.mfa.confirm",
    "auth.mfa.disable",
    "auth.mfa.verify.success",
    "auth.mfa.verify.failed",
    "instance.launch",
    "instance.stop",
    "instance.reset",
    "instance.expired",
    "*",  # wildcard: deliver every event the platform emits
}


# R18 audit finding — events that carry personal data. Subscribing
# to any of these (or the wildcard ``*``) requires the operator to
# acknowledge the DPA framework: the receiver is acting as a
# Processor on the operator's behalf and needs its own DPA before
# data flows to it.
_PII_BEARING_EVENTS: frozenset[str] = frozenset(
    {
        "auth.register",
        "auth.login.success",
        "auth.login.failed",
        "auth.logout",
        "auth.refresh",
        "auth.password.reset.request",
        "auth.password.reset.redeem",
        "auth.password.change",
        "auth.profile.update",
        "auth.account.delete",
        "auth.data.export",
        "auth.mfa.enroll",
        "auth.mfa.confirm",
        "auth.mfa.disable",
        "auth.mfa.verify.success",
        "auth.mfa.verify.failed",
        "auth.email.verify.request",
        "auth.email.verify.redeem",
        "*",
    }
)


class WebhookCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    target_url: HttpUrl
    events: List[str] = Field(min_length=1, max_length=32)
    # R18: when subscribing to PII-bearing events the admin must
    # acknowledge that the receiver is a Processor on their behalf
    # and that a DPA is in place. Refused subscriptions without
    # this flag won't fan out auth.* / wildcard traffic, which is
    # the fail-closed shape we want.
    dpa_acknowledged: bool = Field(
        default=False,
        description=(
            "Set to true when the configured receiver is covered "
            "by a Data Processing Agreement. Required when "
            "subscribing to auth.* events or the '*' wildcard."
        ),
    )

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

    @model_validator(mode="after")
    def _require_dpa_for_pii_events(self) -> "WebhookCreateRequest":
        # R18 — refuse PII-bearing subscriptions unless the admin
        # has flagged dpa_acknowledged=true. Documented in
        # docs/privacy.md §4 — operators configuring webhooks are
        # acting as Controllers; the receiver is a Processor and
        # needs its own DPA.
        pii_hits = sorted(set(self.events) & _PII_BEARING_EVENTS)
        if pii_hits and not self.dpa_acknowledged:
            raise ValueError(
                f"events {pii_hits} carry personal data; set "
                "dpa_acknowledged=true to confirm the receiver is "
                "covered by a Data Processing Agreement before "
                "subscribing. See docs/privacy.md for context."
            )
        return self


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
