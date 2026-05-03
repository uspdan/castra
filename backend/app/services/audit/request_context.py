"""Extract audit-relevant context from a FastAPI/Starlette ``Request``.

Centralised so emit-point callers don't each reimplement IP / request-id
plucking. Returns a dict suitable for splatting into ``ledger.append``.
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request


def context_from_request(request: Request | None) -> dict[str, Any]:
    if request is None:
        return {"ip_address": None, "request_id": None}
    ip = request.client.host if request.client else None
    request_id = getattr(request.state, "request_id", None)
    return {"ip_address": ip, "request_id": request_id}
