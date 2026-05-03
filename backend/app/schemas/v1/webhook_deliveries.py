"""v1 webhook delivery DTOs (slice 6).

One :class:`WebhookDeliveryResponse` row per dispatch attempt. Used by:

* ``GET /api/v1/webhooks/{id}/deliveries`` — paginated history
* ``POST /api/v1/webhooks/{id}/deliveries/{delivery_id}/replay`` —
  the response body is the freshly-inserted attempt row

Fields are shaped for an admin "is this hook healthy / what was the
last failure" UI; the canonical payload is included so operators can
inspect what was actually sent without re-deriving it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    subscription_id: int
    event_type: str
    delivery_id: str
    payload: Dict[str, Any]
    attempt: int = Field(ge=1)
    status: str
    http_status: Optional[int] = None
    response_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime


class WebhookDeliveryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[WebhookDeliveryResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=200)
