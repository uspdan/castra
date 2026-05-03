"""Tests for the in-process WebSocket manager + Redis fan-out.

Covers the WebSocketManager class end-to-end with AsyncMock-backed
WebSocket and Redis stand-ins. The Redis pub/sub listener is exercised
via an in-memory message channel so we can pump a single message
through and assert local broadcast.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from unittest.mock import AsyncMock

from app.services.ws_manager import WebSocketManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_socket() -> AsyncMock:
    """A minimal async-mock that quacks like a starlette WebSocket."""

    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# connect / disconnect
# ---------------------------------------------------------------------------
class TestConnectDisconnect:
    async def test_connect_accepts_and_records_socket(self):
        mgr = WebSocketManager()
        ws = _make_socket()

        await mgr.connect(ws, user_id=1)

        ws.accept.assert_awaited_once()
        assert mgr.connections[1] == [ws]

    async def test_multiple_sockets_per_user(self):
        mgr = WebSocketManager()
        a, b = _make_socket(), _make_socket()

        await mgr.connect(a, user_id=1)
        await mgr.connect(b, user_id=1)

        assert mgr.connections[1] == [a, b]

    async def test_disconnect_removes_socket(self):
        mgr = WebSocketManager()
        ws = _make_socket()
        await mgr.connect(ws, user_id=1)

        await mgr.disconnect(ws, user_id=1)
        assert 1 not in mgr.connections

    async def test_disconnect_unknown_socket_is_noop(self):
        mgr = WebSocketManager()
        # No prior connect — disconnect must not raise.
        await mgr.disconnect(_make_socket(), user_id=42)
        await mgr.disconnect(_make_socket(), user_id=42)

    async def test_disconnect_keeps_remaining_sockets_for_user(self):
        mgr = WebSocketManager()
        a, b = _make_socket(), _make_socket()
        await mgr.connect(a, user_id=1)
        await mgr.connect(b, user_id=1)

        await mgr.disconnect(a, user_id=1)
        assert mgr.connections[1] == [b]


# ---------------------------------------------------------------------------
# send_to_user
# ---------------------------------------------------------------------------
class TestSendToUser:
    async def test_delivers_to_all_user_sockets(self):
        mgr = WebSocketManager()
        a, b = _make_socket(), _make_socket()
        await mgr.connect(a, user_id=1)
        await mgr.connect(b, user_id=1)

        await mgr.send_to_user(1, {"type": "ping"})
        a.send_json.assert_awaited_once_with({"type": "ping"})
        b.send_json.assert_awaited_once_with({"type": "ping"})

    async def test_skips_unknown_user(self):
        mgr = WebSocketManager()
        # Not raising = pass.
        await mgr.send_to_user(404, {"type": "noop"})

    async def test_drops_failing_sockets(self):
        mgr = WebSocketManager()
        good = _make_socket()
        bad = _make_socket()
        bad.send_json.side_effect = RuntimeError("socket closed")

        await mgr.connect(good, user_id=1)
        await mgr.connect(bad, user_id=1)

        await mgr.send_to_user(1, {"type": "test"})
        # Good socket received; bad socket disconnected.
        good.send_json.assert_awaited_once()
        assert mgr.connections[1] == [good]


# ---------------------------------------------------------------------------
# broadcast — local + Redis publish
# ---------------------------------------------------------------------------
class TestBroadcast:
    async def test_sends_to_every_connected_user(self):
        mgr = WebSocketManager()
        a = _make_socket()
        b = _make_socket()
        await mgr.connect(a, user_id=1)
        await mgr.connect(b, user_id=2)

        await mgr.broadcast({"type": "global"})
        a.send_json.assert_awaited_once_with({"type": "global"})
        b.send_json.assert_awaited_once_with({"type": "global"})

    async def test_publishes_to_redis_when_set(self):
        mgr = WebSocketManager()
        redis_stub = AsyncMock()
        mgr.set_redis(redis_stub)

        await mgr.broadcast({"type": "fanout"})
        redis_stub.publish.assert_awaited_once()
        channel, payload = redis_stub.publish.await_args.args
        assert channel == "siege:ws"
        assert json.loads(payload) == {"type": "fanout"}

    async def test_redis_publish_failure_does_not_block_local(self):
        mgr = WebSocketManager()
        ws = _make_socket()
        await mgr.connect(ws, user_id=1)

        redis_stub = AsyncMock()
        redis_stub.publish.side_effect = RuntimeError("redis unreachable")
        mgr.set_redis(redis_stub)

        await mgr.broadcast({"type": "still-delivered"})
        ws.send_json.assert_awaited_once_with({"type": "still-delivered"})

    async def test_drops_failing_sockets_during_broadcast(self):
        mgr = WebSocketManager()
        good = _make_socket()
        bad = _make_socket()
        bad.send_json.side_effect = RuntimeError("socket closed")
        await mgr.connect(good, user_id=1)
        await mgr.connect(bad, user_id=2)

        await mgr.broadcast({"type": "test"})

        assert mgr.connections == {1: [good]}


# ---------------------------------------------------------------------------
# Redis listener
# ---------------------------------------------------------------------------
class _FakePubSub:
    """In-memory pubsub stand-in supporting one subscribe + iter."""

    def __init__(self, messages: list[dict]):
        self._messages = list(messages)
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []

    async def subscribe(self, channel):
        self.subscribed.append(channel)

    async def unsubscribe(self, channel):
        self.unsubscribed.append(channel)

    def listen(self):
        async def _gen():
            for m in self._messages:
                yield m
            # Block forever so the manager's task is the one that
            # cancels — matches production semantics.
            await asyncio.sleep(3600)
        return _gen()


class _FakeRedis:
    def __init__(self, messages):
        self._messages = messages

    def pubsub(self):
        return _FakePubSub(self._messages)


class TestRedisListener:
    async def test_dispatches_message_to_local_sockets(self):
        mgr = WebSocketManager()
        ws = _make_socket()
        await mgr.connect(ws, user_id=1)

        payload = {"type": "from-redis"}
        redis = _FakeRedis(
            [{"type": "message", "data": json.dumps(payload)}]
        )

        task = asyncio.create_task(mgr.start_redis_listener(redis))
        # Yield a few times so the listener consumes the queued
        # message before we cancel.
        for _ in range(20):
            await asyncio.sleep(0)
            if ws.send_json.await_count:
                break

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        ws.send_json.assert_awaited_with(payload)

    async def test_ignores_non_message_envelopes(self):
        mgr = WebSocketManager()
        ws = _make_socket()
        await mgr.connect(ws, user_id=1)

        redis = _FakeRedis(
            [
                {"type": "subscribe", "data": 1},
                {"type": "message", "data": json.dumps({"ok": True})},
            ]
        )
        task = asyncio.create_task(mgr.start_redis_listener(redis))
        for _ in range(20):
            await asyncio.sleep(0)
            if ws.send_json.await_count:
                break
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        ws.send_json.assert_awaited_once_with({"ok": True})

    async def test_swallows_decode_errors(self):
        mgr = WebSocketManager()
        ws = _make_socket()
        await mgr.connect(ws, user_id=1)

        redis = _FakeRedis(
            [
                {"type": "message", "data": "not-json"},
                {"type": "message", "data": json.dumps({"v": 1})},
            ]
        )
        task = asyncio.create_task(mgr.start_redis_listener(redis))
        for _ in range(40):
            await asyncio.sleep(0)
            if ws.send_json.await_count:
                break
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        ws.send_json.assert_awaited_once_with({"v": 1})


# ---------------------------------------------------------------------------
# set_redis
# ---------------------------------------------------------------------------
class TestSetRedis:
    def test_assigns_client(self):
        mgr = WebSocketManager()
        client = object()
        mgr.set_redis(client)
        assert mgr._redis is client
