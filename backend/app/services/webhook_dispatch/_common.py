"""Shared helpers for outbound webhook dispatch.

Holds the bits every dispatch path reuses:

* ``generate_subscription_secret`` — admin-facing secret minting.
* ``sign_body`` — HMAC-SHA256 over the canonical body.
* ``_canonical_body`` — deterministic JSON envelope for signing.
* HTTP client management — ``_new_http_client``,
  ``_get_shared_client``, ``aclose_shared_client``,
  ``_default_http_client`` (test-seam alias).
* ``_AttemptOutcome`` — dataclass returned by ``_attempt_one``.
* ``_attempt_one`` — pure HTTP attempt for a single subscription,
  with the R4 dispatch-time SSRF re-check.

Public surface intentionally re-exported from
``app.services.webhook_dispatch`` so external callers keep their
existing imports.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets as _secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import httpx
import structlog

from app.models import WebhookSubscription
from app.services import webhook_ssrf
from app.services.webhook_ssrf import UnsafeUrlError

# Tests monkeypatch ``app.services.webhook_dispatch.assert_url_safe``
# to bypass the dispatch-time SSRF check; we resolve the name at
# call time so the patch takes effect.
def _lookup_assert_url_safe():
    import app.services.webhook_dispatch as _pkg

    return getattr(_pkg, "assert_url_safe", webhook_ssrf.assert_url_safe)


logger = structlog.get_logger()

_DEFAULT_TIMEOUT_S = 5.0
_SIGNATURE_HEADER = "X-Siege-Signature"
_DELIVERY_HEADER = "X-Siege-Delivery-Id"
_EVENT_HEADER = "X-Siege-Event"
_SECRET_BYTES = 32  # 64 hex chars; well above 128-bit margin


def generate_subscription_secret() -> str:
    """Return a fresh URL-safe random secret for a new subscription."""

    return _secrets.token_hex(_SECRET_BYTES)


def sign_body(secret: str, body: bytes) -> str:
    """Compute the ``sha256=<hex>`` signature for ``body``.

    The ``sha256=`` prefix matches the GitHub / Stripe style;
    receivers can split on ``=`` to extract the hex digest.
    """

    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _canonical_body(
    event_type: str, delivery_id: str, payload: Mapping[str, Any]
) -> bytes:
    envelope = {
        "event_type": event_type,
        "delivery_id": delivery_id,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": dict(payload),
    }
    # ``sort_keys=True`` so the receiver-side recomputation is
    # deterministic regardless of dict iteration order.
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


# ---------------------------------------------------------------------------
# HTTP client management (R32)
# ---------------------------------------------------------------------------
def _new_http_client() -> httpx.AsyncClient:
    """R24 audit finding — pin TLS + redirect behaviour explicitly."""

    return httpx.AsyncClient(
        timeout=_DEFAULT_TIMEOUT_S,
        verify=True,
        follow_redirects=False,
    )


_shared_client: httpx.AsyncClient | None = None


def _get_shared_client() -> httpx.AsyncClient:
    """Return the lazily-built module-scoped client. Idempotent."""

    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = _new_http_client()
    return _shared_client


async def aclose_shared_client() -> None:
    """Close the module client. Call from the FastAPI lifespan
    shutdown hook; idempotent."""

    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
    _shared_client = None


def _default_http_client():
    """Backwards-compatible alias preserved for callers still
    passing the factory by name. Production code uses the shared
    client directly via :func:`_get_shared_client`."""

    return _new_http_client()


# ---------------------------------------------------------------------------
# Attempt outcome + the single-attempt function
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _AttemptOutcome:
    """Per-subscription outcome of a single dispatch attempt."""

    subscription: WebhookSubscription
    status: str
    http_status: int | None
    response_ms: int
    error: str | None


async def _attempt_one(
    *,
    subscription: WebhookSubscription,
    event_type: str,
    delivery_id: str,
    body: bytes,
    factory,
    shared_client: httpx.AsyncClient | None = None,
) -> _AttemptOutcome:
    """Pure HTTP attempt for a single subscription.

    Returns an :class:`_AttemptOutcome` and never raises; the caller
    serialises the resulting ``last_*`` writes + delivery row
    inserts onto the shared session.
    """

    headers = {
        "Content-Type": "application/json",
        _SIGNATURE_HEADER: sign_body(subscription.secret, body),
        _DELIVERY_HEADER: delivery_id,
        _EVENT_HEADER: event_type,
    }
    started = time.monotonic()
    # R4 audit finding — re-resolve at dispatch time. The
    # create-time check doesn't catch DNS-rebinding; this check
    # narrows the window dramatically.
    try:
        _lookup_assert_url_safe()(subscription.target_url)
    except UnsafeUrlError as exc:
        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
        return _AttemptOutcome(
            subscription=subscription,
            status="refused_ssrf",
            http_status=None,
            response_ms=elapsed_ms,
            error=f"refused at dispatch: {exc}",
        )
    try:
        if shared_client is not None:
            # Production path — reuse the module client (R32).
            response = await shared_client.post(
                subscription.target_url, content=body, headers=headers
            )
        else:
            async with factory() as client:
                response = await client.post(
                    subscription.target_url, content=body, headers=headers
                )
        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
        if 200 <= response.status_code < 300:
            return _AttemptOutcome(
                subscription=subscription,
                status=f"ok_{response.status_code}",
                http_status=response.status_code,
                response_ms=elapsed_ms,
                error=None,
            )
        return _AttemptOutcome(
            subscription=subscription,
            status=f"http_{response.status_code}",
            http_status=response.status_code,
            response_ms=elapsed_ms,
            error=f"non-2xx response: {response.status_code}",
        )
    except httpx.TimeoutException:
        return _AttemptOutcome(
            subscription=subscription,
            status="timeout",
            http_status=None,
            response_ms=int((time.monotonic() - started) * 1000),
            error="request timed out",
        )
    except httpx.HTTPError as exc:
        return _AttemptOutcome(
            subscription=subscription,
            status="network_error",
            http_status=None,
            response_ms=int((time.monotonic() - started) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 — never propagate to caller
        logger.error(
            "webhook dispatch internal error",
            subscription_id=subscription.id,
            event_type=event_type,
            error=f"{type(exc).__name__}: {exc}",
        )
        return _AttemptOutcome(
            subscription=subscription,
            status="internal_error",
            http_status=None,
            response_ms=int((time.monotonic() - started) * 1000),
            error=f"{type(exc).__name__}: {exc}",
        )


__all__ = [
    "_AttemptOutcome",
    "_attempt_one",
    "_canonical_body",
    "_default_http_client",
    "_get_shared_client",
    "_new_http_client",
    "aclose_shared_client",
    "generate_subscription_secret",
    "logger",
    "sign_body",
]
