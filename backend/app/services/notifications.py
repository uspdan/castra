"""Notification service — DB row + WebSocket fan-out in one call.

The frontend's ``useWebSocket`` hook already routes
``{type: "notification", …}`` events into the ``notificationStore``
which feeds ``NotificationDropdown``. The backend, however,
historically only inserted ``Notification`` rows and relied on the
client to refresh the drawer on its next page navigation. This
helper closes the gap: every Notification creation also publishes
to ``ws_manager`` so the drawer updates live.

Use this everywhere a Notification row is created. The caller is
responsible for committing the surrounding transaction; this helper
flushes but does NOT commit so it composes with the existing
audit-ledger + scoring writes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification
from app.services.ws_manager import ws_manager


logger = structlog.get_logger()


async def create_notification(
    db: AsyncSession,
    *,
    title: str,
    message: str,
    notification_type: str,
    target_user_id: Optional[int] = None,
    is_global: bool = False,
) -> Notification:
    """Create a notification row and broadcast it to live WS clients.

    Routing:
        * ``is_global=True``  → ``ws_manager.broadcast`` (all sockets).
        * ``target_user_id`` set, not global → ``send_to_user``.
        * Both unset → row is created but not broadcast (rare; used
          for system-only / audit-only notifications).

    The WS publish is best-effort: a Redis or socket failure is
    logged at WARN but does NOT propagate. Callers must not rely
    on the broadcast having reached every client; the row in the
    DB is the source of truth (the drawer refetches via
    ``GET /notifications/`` on next navigation).
    """

    now = datetime.now(timezone.utc)
    row = Notification(
        title=title,
        message=message,
        notification_type=notification_type,
        target_user_id=target_user_id,
        is_global=is_global,
        created_at=now,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)

    payload = {
        "type": "notification",
        "id": row.id,
        "title": title,
        "message": message,
        "notification_type": notification_type,
        "is_global": is_global,
        "target_user_id": target_user_id,
        "created_at": now.isoformat(),
    }

    try:
        if is_global:
            await ws_manager.broadcast(payload)
        elif target_user_id is not None:
            await ws_manager.send_to_user(target_user_id, payload)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning(
            "notification.broadcast_failed",
            notification_id=row.id,
            error=f"{type(exc).__name__}: {exc}",
        )

    return row


__all__ = ["create_notification"]
