"""``/api/v1/webhooks`` admin CRUD.

Phase 12 (slice 5). All endpoints require admin role via
:func:`require_admin`. The create response surfaces the freshly-
generated signing secret **once**; subsequent reads omit it.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, WebhookDelivery, WebhookSubscription
from app.schemas.v1.webhook_deliveries import (
    WebhookDeliveryListResponse,
    WebhookDeliveryResponse,
)
from app.schemas.v1.webhooks import (
    WebhookCreateRequest,
    WebhookCreatedResponse,
    WebhookListResponse,
    WebhookResponse,
)
from app.services.auth import require_admin
from app.services.webhook_dispatch import (
    generate_subscription_secret,
    replay_delivery,
)


router = APIRouter()


@router.post(
    "/webhooks",
    response_model=WebhookCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses={403: {"description": "Admin role required"}},
)
async def create_webhook_v1(
    payload: WebhookCreateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WebhookCreatedResponse:
    secret = generate_subscription_secret()
    sub = WebhookSubscription(
        owner_user_id=admin.id,
        name=payload.name,
        target_url=str(payload.target_url),
        secret=secret,
        events=list(payload.events),
        is_active=True,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return _to_created(sub, secret)


@router.get(
    "/webhooks",
    response_model=WebhookListResponse,
    responses={403: {"description": "Admin role required"}},
)
async def list_webhooks_v1(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WebhookListResponse:
    rows = (
        await db.execute(
            select(WebhookSubscription).order_by(
                WebhookSubscription.created_at.desc()
            )
        )
    ).scalars().all()
    return WebhookListResponse(
        items=[_to_response(row) for row in rows],
        total=len(rows),
    )


@router.get(
    "/webhooks/{subscription_id}",
    response_model=WebhookResponse,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "Subscription not found"},
    },
)
async def get_webhook_v1(
    subscription_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    sub = await _load(db, subscription_id)
    return _to_response(sub)


@router.delete(
    "/webhooks/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "Subscription not found"},
    },
)
async def delete_webhook_v1(
    subscription_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sub = await _load(db, subscription_id)
    await db.delete(sub)
    await db.commit()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
async def _load(db: AsyncSession, subscription_id: int) -> WebhookSubscription:
    sub = (
        await db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.id == subscription_id
            )
        )
    ).scalars().first()
    if sub is None:
        raise HTTPException(status_code=404, detail="webhook not found")
    return sub


def _to_response(sub: WebhookSubscription) -> WebhookResponse:
    return WebhookResponse(
        id=sub.id,
        name=sub.name,
        target_url=sub.target_url,
        events=list(sub.events or []),
        is_active=bool(sub.is_active),
        created_at=sub.created_at,
        last_delivery_at=sub.last_delivery_at,
        last_status=sub.last_status,
        last_error=sub.last_error,
    )


def _to_created(sub: WebhookSubscription, secret: str) -> WebhookCreatedResponse:
    base = _to_response(sub).model_dump()
    base["secret"] = secret
    return WebhookCreatedResponse(**base)


# ---------------------------------------------------------------------------
# Deliveries (slice 6)
# ---------------------------------------------------------------------------
@router.get(
    "/webhooks/{subscription_id}/deliveries",
    response_model=WebhookDeliveryListResponse,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "Subscription not found"},
    },
)
async def list_webhook_deliveries_v1(
    subscription_id: int,
    page: int = Query(1, ge=1, le=10_000),
    per_page: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryListResponse:
    await _load(db, subscription_id)  # 404 if missing

    total = (
        await db.execute(
            select(func.count(WebhookDelivery.id)).where(
                WebhookDelivery.subscription_id == subscription_id
            )
        )
    ).scalar() or 0

    rows = (
        await db.execute(
            select(WebhookDelivery)
            .where(WebhookDelivery.subscription_id == subscription_id)
            .order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).scalars().all()

    return WebhookDeliveryListResponse(
        items=[_to_delivery(r) for r in rows],
        total=int(total),
        page=page,
        per_page=per_page,
    )


@router.post(
    "/webhooks/{subscription_id}/deliveries/{delivery_id}/replay",
    response_model=WebhookDeliveryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Admin role required"},
        404: {"description": "Subscription or delivery not found"},
    },
)
async def replay_webhook_delivery_v1(
    subscription_id: int,
    delivery_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryResponse:
    sub = await _load(db, subscription_id)

    # The delivery_id is the ``X-Siege-Delivery-Id`` header value, not
    # the integer row id. Pick the most recent attempt with that
    # delivery_id on this subscription as the canonical replay
    # source — any of them carries the same payload, and "most
    # recent" is the one operators are most likely investigating.
    delivery = (
        await db.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.subscription_id == subscription_id,
                WebhookDelivery.delivery_id == delivery_id,
            )
            .order_by(WebhookDelivery.attempt.desc())
            .limit(1)
        )
    ).scalars().first()
    if delivery is None:
        raise HTTPException(status_code=404, detail="delivery not found")

    new_row = await replay_delivery(
        db=db, delivery=delivery, subscription=sub
    )
    await db.commit()
    await db.refresh(new_row)
    return _to_delivery(new_row)


def _to_delivery(row: WebhookDelivery) -> WebhookDeliveryResponse:
    return WebhookDeliveryResponse(
        id=row.id,
        subscription_id=row.subscription_id,
        event_type=row.event_type,
        delivery_id=row.delivery_id,
        payload=dict(row.payload or {}),
        attempt=int(row.attempt or 1),
        status=row.status,
        http_status=row.http_status,
        response_ms=row.response_ms,
        error=row.error,
        created_at=row.created_at,
    )
