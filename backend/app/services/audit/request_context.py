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
    # R17 — if the operator has opted into hashed IPs in the ledger,
    # HMAC the cleartext peer with the dedicated PII salt so the row
    # can be made unresolvable by rotating the salt at erasure time.
    if ip is not None:
        import hashlib as _hashlib
        import hmac as _hmac

        from app.config import get_settings

        settings = get_settings()
        if getattr(settings, "AUDIT_HASH_IPS", False):
            ip = _hmac.new(
                settings.audit_pii_salt().encode(),
                ip.encode(),
                _hashlib.sha256,
            ).hexdigest()
    return {"ip_address": ip, "request_id": request_id}
