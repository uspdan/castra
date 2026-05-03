from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Notification
from app.services.auth import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base_filter = or_(
        Notification.is_global == True,
        Notification.target_user_id == current_user.id,
    )

    total_result = await db.execute(
        select(func.count(Notification.id)).where(base_filter)
    )
    total = total_result.scalar()

    result = await db.execute(
        select(Notification)
        .where(base_filter)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    notifications = result.scalars().all()

    items = [
        {
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "notification_type": n.notification_type,
            "is_global": n.is_global,
            "is_read": n.is_read,
            "created_at": str(n.created_at) if n.created_at else None,
        }
        for n in notifications
    ]

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalars().first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    if not notification.is_global and notification.target_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    notification.is_read = True
    await db.commit()

    return {"detail": "Notification marked as read."}


@router.put("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        update(Notification)
        .where(
            or_(
                Notification.is_global == True,
                Notification.target_user_id == current_user.id,
            ),
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await db.execute(stmt)
    await db.commit()

    return {"detail": "All notifications marked as read."}


@router.get("/unread-count")
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count(Notification.id)).where(
            or_(
                Notification.is_global == True,
                Notification.target_user_id == current_user.id,
            ),
            Notification.is_read == False,
        )
    )
    count = result.scalar()

    return {"unread_count": count}
