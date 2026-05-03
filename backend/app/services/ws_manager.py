import asyncio
import json
from typing import Dict, List

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class WebSocketManager:
    def __init__(self):
        self.connections: Dict[int, List[WebSocket]] = {}
        self._redis = None

    def set_redis(self, redis_client):
        self._redis = redis_client

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.connections:
            self.connections[user_id] = []
        self.connections[user_id].append(websocket)
        logger.info("WebSocket connected", user_id=user_id)

    async def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.connections:
            try:
                self.connections[user_id].remove(websocket)
            except ValueError:
                pass
            if not self.connections[user_id]:
                del self.connections[user_id]
        logger.info("WebSocket disconnected", user_id=user_id)

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        # Publish to Redis for cross-worker broadcast
        if self._redis:
            try:
                await self._redis.publish("siege:ws", data)
            except Exception as e:
                logger.error("Redis publish failed", error=str(e))
        # Send to local connections
        await self._broadcast_local(message)

    async def _broadcast_local(self, message: dict):
        disconnected = []
        for user_id, sockets in self.connections.items():
            for ws in sockets:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append((user_id, ws))

        for user_id, ws in disconnected:
            await self.disconnect(ws, user_id)

    async def send_to_user(self, user_id: int, message: dict):
        if user_id in self.connections:
            disconnected = []
            for ws in self.connections[user_id]:
                try:
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                await self.disconnect(ws, user_id)

    async def start_redis_listener(self, redis_client):
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("siege:ws")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        await self._broadcast_local(data)
                    except Exception as e:
                        logger.error("Redis listener error", error=str(e))
        except asyncio.CancelledError:
            await pubsub.unsubscribe("siege:ws")
        except Exception as e:
            logger.error("Redis listener crashed", error=str(e))


ws_manager = WebSocketManager()
