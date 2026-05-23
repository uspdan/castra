"""WebSocket auth (R11 audit finding).

Token MUST be sent via a ``Sec-WebSocket-Protocol`` subprotocol of
the shape ``siege-auth.<JWT>`` — never as a ``?token=`` query
string. Query-string auth lands the JWT verbatim in uvicorn's
access log + every intermediate proxy log.

Backwards compatibility for the legacy ``?token=`` query parameter
was removed in v2.5.1 along with the legacy ``/auth/*`` HTTP
router; older clients must upgrade.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.auth import decode_token
from app.services.ws_manager import ws_manager

logger = logging.getLogger("siege_range")

router = APIRouter(tags=["websocket"])

_SUBPROTO_PREFIX = "siege-auth."


def _extract_token_from_subprotocols(websocket: WebSocket) -> tuple[str | None, str | None]:
    """Return (token, matched_subprotocol) or (None, None).

    Browsers expose the negotiated subprotocols on the
    ``Sec-WebSocket-Protocol`` request header as a comma-separated
    list. We accept the first entry that starts with
    ``siege-auth.`` — the suffix is the JWT.
    """

    header = websocket.headers.get("sec-websocket-protocol", "")
    if not header:
        return None, None
    for raw in header.split(","):
        candidate = raw.strip()
        if candidate.startswith(_SUBPROTO_PREFIX):
            token = candidate[len(_SUBPROTO_PREFIX):]
            if token:
                return token, candidate
    return None, None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token, matched_subproto = _extract_token_from_subprotocols(websocket)
    if not token:
        # Accept the connection just long enough to send a clean
        # close — closing before accept produces a network error
        # that browsers can't surface to the JS handler. The 4001
        # code is consistent with the prior contract.
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub", 0))
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Echo the matched subprotocol back so the browser accepts the
    # handshake. Starlette's WebSocket.accept honours subprotocol=.
    await ws_manager.connect(websocket, user_id, subprotocol=matched_subproto)

    heartbeat_task = asyncio.create_task(_heartbeat(websocket))

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("websocket loop ended with exception", exc_info=True)
    finally:
        heartbeat_task.cancel()
        await ws_manager.disconnect(websocket, user_id)


async def _heartbeat(websocket: WebSocket):
    try:
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break
    except asyncio.CancelledError:
        pass
