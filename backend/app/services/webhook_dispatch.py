"""Outbound webhook dispatch.

Phase 12 (slice 5). Looks up active :class:`WebhookSubscription` rows
whose ``events`` list contains the firing event type, then POSTs a
canonical JSON envelope to each ``target_url`` with an HMAC-SHA256
signature header.

Design constraints (CLAUDE.md §3, §15):

* **Best-effort delivery.** A single attempt with a 5-second
  timeout. Network failures, non-2xx responses, and unsigned 4xx
  responses all flow into ``last_status`` / ``last_error`` on the
  subscription row but never raise into the caller. The submission
  flow that triggers dispatch must not 500 because Slack is
  flapping.
* **HMAC-signed body.** ``X-Siege-Signature: sha256=<hex>`` derived
  from the subscription's ``secret``. Receivers verify by
  recomputing — the same scheme GitHub / Stripe / Linear use.
* **Replay protection.** ``X-Siege-Delivery-Id`` header is a
  per-call UUID; receivers can de-dupe.
* **Receiver isolation.** Each subscription is dispatched on its
  own ``httpx.AsyncClient`` so a slow receiver doesn't head-of-line
  block the others. Failures are logged + persisted; the function
  returns when every subscription has been attempted.

A future slice will bring retries with exponential backoff + a
deliveries-history table for replay. For slice 5 the inline
``last_status`` / ``last_error`` fields are the only persisted
observability.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets as _secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebhookDelivery, WebhookSubscription
from app.services.webhook_ssrf import UnsafeUrlError, assert_url_safe


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

    Exposed for tests + hypothetical receiver-side verification
    helpers. The ``sha256=`` prefix matches the GitHub / Stripe
    style; receivers can split on ``=`` to extract the hex digest.
    """

    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


async def deliver_event(
    *,
    db: AsyncSession,
    event_type: str,
    payload: Mapping[str, Any],
    http_client_factory=None,
) -> None:
    """Fan out a single audit event to every matching subscription.

    Loads active :class:`WebhookSubscription` rows whose ``events``
    list contains ``event_type``, signs the canonical JSON body with
    each subscription's secret, and POSTs concurrently. The function
    returns when every dispatch task has completed (or its 5-second
    timeout has elapsed). Per-row ``last_*`` fields are updated and
    committed in the calling transaction.

    ``http_client_factory`` is a test seam; production callers
    omit it and a fresh ``httpx.AsyncClient`` is used per attempt.
    """

    subscriptions = await _matching_subscriptions(db, event_type)
    if not subscriptions:
        return

    delivery_id = _secrets.token_hex(8)
    canonical_body = _canonical_body(event_type, delivery_id, payload)

    # R32: production callers reuse the module-scoped client so the
    # connection pool persists across attempts + fan-outs. Tests
    # still pass ``http_client_factory`` to stub the HTTP layer.
    factory = http_client_factory or _default_http_client
    shared_client = (
        _get_shared_client() if http_client_factory is None else None
    )
    # HTTP fan-out runs concurrently; the results (per-subscription
    # status / error) are persisted to the DB *serially* afterwards.
    # Mixing concurrent ``db.add`` / ``db.flush`` calls into the same
    # session triggers SQLAlchemy's "flush within flush" warning and
    # is genuinely racy on the unit-of-work tracker — the post-hoc
    # write loop avoids both.
    outcomes: list[_AttemptOutcome] = await asyncio.gather(
        *(
            _attempt_one(
                subscription=sub,
                event_type=event_type,
                delivery_id=delivery_id,
                body=canonical_body,
                factory=factory,
                shared_client=shared_client,
            )
            for sub in subscriptions
        ),
        return_exceptions=False,
    )
    now = datetime.now(timezone.utc)
    for outcome in outcomes:
        sub = outcome.subscription
        sub.last_delivery_at = now
        sub.last_status = outcome.status
        sub.last_error = (
            (outcome.error or "")[:500] if outcome.error else None
        )
        db.add(sub)
        # Phase 12 (slice 6): record an attempt row in
        # ``webhook_deliveries`` so the v1 list endpoint and replay
        # endpoint have something to read.
        db.add(
            WebhookDelivery(
                subscription_id=sub.id,
                event_type=event_type,
                delivery_id=delivery_id,
                payload=dict(payload),
                attempt=1,
                status=outcome.status,
                http_status=outcome.http_status,
                response_ms=outcome.response_ms,
                error=(outcome.error or "")[:500] if outcome.error else None,
                created_at=now,
            )
        )
    await db.flush()


async def _matching_subscriptions(
    db: AsyncSession, event_type: str
) -> list[WebhookSubscription]:
    rows = (
        await db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.is_active.is_(True)
            )
        )
    ).scalars().all()
    out: list[WebhookSubscription] = []
    for row in rows:
        events = list(row.events or [])
        if event_type in events or "*" in events:
            out.append(row)
    return out


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


def _new_http_client() -> httpx.AsyncClient:
    """Construct a fresh client with the platform's TLS + redirect
    pins. Used by the lazy module-scoped client below + by tests
    that want a private client.

    R24 audit finding: both options match the current httpx
    defaults, but pin them explicitly so a future httpx release
    can't quietly turn on redirect-following (re-introducing the
    SSRF surface tracked in R4) or relax TLS verification.
    """

    return httpx.AsyncClient(
        timeout=_DEFAULT_TIMEOUT_S,
        verify=True,
        follow_redirects=False,
    )


# R32 audit finding — keep one httpx client per process and reuse
# its connection pool. Construction-per-attempt was paying the full
# TCP + TLS handshake on every dispatch, which is noticeable when a
# fan-out hits many subscriptions or a high-frequency event type.
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


# Backwards-compatible alias preserved for any caller still passing
# the old factory by name. Production code uses the shared client
# directly via ``_get_shared_client()``.
def _default_http_client():
    return _new_http_client()


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
    serialises the resulting `last_*` writes + delivery row inserts
    onto the shared session.
    """

    headers = {
        "Content-Type": "application/json",
        _SIGNATURE_HEADER: sign_body(subscription.secret, body),
        _DELIVERY_HEADER: delivery_id,
        _EVENT_HEADER: event_type,
    }
    started = time.monotonic()
    # R4 audit finding — re-resolve at dispatch time. The
    # create-time check (in routers/v1/webhooks.py) doesn't catch
    # DNS-rebinding: an attacker-controlled hostname can return a
    # public IP on the first lookup and a private IP on subsequent
    # lookups. There's still a small TOCTOU window between this
    # check and httpx's own resolve, but it dramatically narrows
    # the surface; a transport-level resolved-IP pin is the next
    # tier of hardening.
    try:
        assert_url_safe(subscription.target_url)
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
            # Production path — reuse the module client (R32). No
            # ``async with`` here; closing the shared client between
            # attempts defeats the whole point of sharing it. The
            # lifespan shutdown hook closes it on app teardown.
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


# ---------------------------------------------------------------------------
# Replay (slice 6)
# ---------------------------------------------------------------------------
async def replay_delivery(
    *,
    db: AsyncSession,
    delivery: WebhookDelivery,
    subscription: WebhookSubscription,
    http_client_factory=None,
) -> WebhookDelivery:
    """Re-dispatch a previously recorded delivery.

    Re-uses the original ``delivery_id`` and canonical payload so
    receivers can de-dupe (they should treat repeated delivery_ids as
    the same logical event). The body is re-signed against the
    subscription's *current* secret — rotating the secret therefore
    invalidates outstanding replays cleanly.

    Returns the freshly-inserted :class:`WebhookDelivery` row,
    flushed but not committed; the caller owns the surrounding tx.
    """

    canonical_body = _canonical_body(
        delivery.event_type, delivery.delivery_id, delivery.payload or {}
    )
    factory = http_client_factory or _default_http_client
    shared_client = _get_shared_client() if http_client_factory is None else None
    outcome = await _attempt_one(
        subscription=subscription,
        event_type=delivery.event_type,
        delivery_id=delivery.delivery_id,
        body=canonical_body,
        factory=factory,
        shared_client=shared_client,
    )

    # Update the subscription's "last_*" cache.
    now = datetime.now(timezone.utc)
    subscription.last_delivery_at = now
    subscription.last_status = outcome.status
    subscription.last_error = (
        (outcome.error or "")[:500] if outcome.error else None
    )
    db.add(subscription)

    # Compute the next attempt number across all rows sharing this
    # delivery_id. The first attempt (attempt=1) was the original
    # ``deliver_event`` call; replays bump from there.
    prior_max = (
        await db.execute(
            select(func.max(WebhookDelivery.attempt)).where(
                WebhookDelivery.delivery_id == delivery.delivery_id,
                WebhookDelivery.subscription_id == subscription.id,
            )
        )
    ).scalar() or 0
    next_attempt = int(prior_max) + 1

    new_row = WebhookDelivery(
        subscription_id=subscription.id,
        event_type=delivery.event_type,
        delivery_id=delivery.delivery_id,
        payload=dict(delivery.payload or {}),
        attempt=next_attempt,
        status=outcome.status,
        http_status=outcome.http_status,
        response_ms=outcome.response_ms,
        error=(outcome.error or "")[:500] if outcome.error else None,
        created_at=now,
    )
    db.add(new_row)
    await db.flush()
    return new_row


# ---------------------------------------------------------------------------
# Retry + retention (slice 7)
# ---------------------------------------------------------------------------
_RETRY_MAX_ATTEMPTS = 5
_RETRY_BASE_DELAY_S = 30  # 30s, 60s, 120s, 240s, 480s — full schedule under 16min


def _is_retriable(status: str) -> bool:
    """Return True iff a delivery in ``status`` should be retried.

    Retriable failures are transient: timeouts, network errors,
    internal-error fallthroughs, and 5xx responses. 4xx responses are
    treated as final — the receiver rejected the body, retrying with
    the same payload won't help, and we'd just keep hammering them.
    """

    if status.startswith("ok_"):
        return False
    if status in {"timeout", "network_error", "internal_error"}:
        return True
    if status.startswith("http_5"):
        return True
    return False  # http_4xx and unknown statuses are final


def _next_retry_due_at(created_at: datetime, attempt: int) -> datetime:
    """Compute the earliest UTC instant the ``attempt``-th delivery
    may be retried.

    Exponential backoff: ``base * 2^(attempt-1)`` from the failed
    attempt's ``created_at``. Attempt 1 → +30s, 2 → +60s, 3 → +120s, etc.
    """

    delay = _RETRY_BASE_DELAY_S * (2 ** max(0, attempt - 1))
    base = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    return base + timedelta(seconds=delay)


async def retry_failed_deliveries(
    db: AsyncSession,
    *,
    max_attempts: int = _RETRY_MAX_ATTEMPTS,
    now: datetime | None = None,
    http_client_factory=None,
) -> int:
    """Replay every retriable delivery whose backoff has elapsed.

    Scans ``webhook_deliveries`` for the most-recent attempt per
    ``(subscription_id, delivery_id)`` pair. Skips rows that are
    succeeded (``ok_*``), terminally failed (``http_4xx``),
    cap-reached (``attempt >= max_attempts``), or still inside the
    backoff window. The remainder are replayed via
    :func:`replay_delivery`.

    Commits each replay independently so a poison row doesn't block
    the rest of the queue. Returns the number of rows actually
    re-dispatched (regardless of outcome).
    """

    current_time = now or datetime.now(timezone.utc)

    # Latest attempt per (subscription_id, delivery_id). The
    # subquery uses MAX(attempt) — the rows we want to consider are
    # the heads of each delivery_id's chain.
    latest_attempt_subq = (
        select(
            WebhookDelivery.subscription_id,
            WebhookDelivery.delivery_id,
            func.max(WebhookDelivery.attempt).label("max_attempt"),
        )
        .group_by(
            WebhookDelivery.subscription_id, WebhookDelivery.delivery_id
        )
        .subquery()
    )

    rows = (
        await db.execute(
            select(WebhookDelivery)
            .join(
                latest_attempt_subq,
                (WebhookDelivery.subscription_id == latest_attempt_subq.c.subscription_id)
                & (WebhookDelivery.delivery_id == latest_attempt_subq.c.delivery_id)
                & (WebhookDelivery.attempt == latest_attempt_subq.c.max_attempt),
            )
            .order_by(WebhookDelivery.created_at.asc())
        )
    ).scalars().all()

    replayed = 0
    for head in rows:
        if not _is_retriable(head.status):
            continue
        if head.attempt >= max_attempts:
            continue
        due_at = _next_retry_due_at(head.created_at, head.attempt)
        if current_time < due_at:
            continue

        subscription = (
            await db.execute(
                select(WebhookSubscription).where(
                    WebhookSubscription.id == head.subscription_id,
                    WebhookSubscription.is_active.is_(True),
                )
            )
        ).scalars().first()
        if subscription is None:
            # Subscription deleted or disabled since the last attempt;
            # skip silently rather than retrying into a void.
            continue

        try:
            await replay_delivery(
                db=db,
                delivery=head,
                subscription=subscription,
                http_client_factory=http_client_factory,
            )
            await db.commit()
            replayed += 1
        except Exception as exc:  # noqa: BLE001 — never propagate to scheduler
            logger.error(
                "webhook retry failed",
                subscription_id=head.subscription_id,
                delivery_id=head.delivery_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            try:
                await db.rollback()
            except Exception:  # noqa: BLE001
                pass
    return replayed


async def prune_old_deliveries(
    db: AsyncSession,
    *,
    retention_days: int = 30,
    now: datetime | None = None,
) -> int:
    """Delete ``webhook_deliveries`` rows older than ``retention_days``.

    Bulk DELETE without per-row hooks. Returns the count of rows
    removed for logging. The caller is responsible for the
    surrounding commit.
    """

    if retention_days < 1:
        raise ValueError("retention_days must be >= 1")
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=retention_days)
    from sqlalchemy import delete as sa_delete

    result = await db.execute(
        sa_delete(WebhookDelivery).where(
            WebhookDelivery.created_at < cutoff
        )
    )
    await db.flush()
    return int(result.rowcount or 0)
