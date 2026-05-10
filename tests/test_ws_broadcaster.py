"""Tests for the WebSocket broadcaster singleton."""

import asyncio
import json
import pytest

from runtime.core.ws_broadcaster import Broadcaster, get_broadcaster


class FakeWebSocket:
    """Minimal fake WebSocket for testing."""

    def __init__(self):
        self.accepted = False
        self.sent: list[str] = []
        self._recv_queue: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def send_text(self, text: str):
        if self.closed:
            raise RuntimeError("WebSocket closed")
        self.sent.append(text)

    async def receive_text(self) -> str:
        return await self._recv_queue.get()

    def close(self):
        self.closed = True
        self._recv_queue.put_nowait("__close__")


class TestBroadcaster:
    """Unit tests for Broadcaster."""

    def test_singleton_returns_same_instance(self):
        a = get_broadcaster()
        b = get_broadcaster()
        assert a is b

    def test_initial_state(self):
        bc = Broadcaster()
        assert bc.client_count == 0
        assert bc.last_snapshot is None
        status = bc.status()
        assert status["connected_clients"] == 0
        assert status["total_published"] == 0
        assert status["has_last_snapshot"] is False

    @pytest.mark.asyncio
    async def test_publish_no_clients(self):
        bc = Broadcaster()
        await bc.publish("TELEMETRY_TICK", {"equity_usdt": 100.0})
        assert bc.last_snapshot is not None
        assert bc.last_snapshot["type"] == "TELEMETRY_TICK"
        assert bc.last_snapshot["payload"]["equity_usdt"] == 100.0

    @pytest.mark.asyncio
    async def test_publish_to_connected_client(self):
        bc = Broadcaster()
        ws = FakeWebSocket()

        # Simulate client connection in background
        async def connect_and_receive():
            await ws.accept()
            bc._clients.add(ws)

        await connect_and_receive()

        await bc.publish("TELEMETRY_TICK", {"weight": 42})
        assert len(ws.sent) == 1
        data = json.loads(ws.sent[0])
        assert data["type"] == "TELEMETRY_TICK"
        assert data["payload"]["weight"] == 42
        assert data["seq"] == 1

    @pytest.mark.asyncio
    async def test_publish_prunes_dead_clients(self):
        bc = Broadcaster()
        ws = FakeWebSocket()
        ws.closed = True  # Simulate dead client
        bc._clients.add(ws)

        await bc.publish("TEST", {"x": 1})
        assert bc.client_count == 0  # Dead client pruned

    @pytest.mark.asyncio
    async def test_sequence_increments(self):
        bc = Broadcaster()
        await bc.publish("A", {})
        await bc.publish("B", {})
        await bc.publish("C", {})
        assert bc._seq == 3
        assert bc.status()["total_published"] == 3

    @pytest.mark.asyncio
    async def test_last_snapshot_only_for_telemetry_tick(self):
        bc = Broadcaster()
        await bc.publish("ALERT", {"msg": "test"})
        assert bc.last_snapshot is None  # ALERT doesn't update last_snapshot

        await bc.publish("TELEMETRY_TICK", {"equity": 50})
        assert bc.last_snapshot is not None
        assert bc.last_snapshot["type"] == "TELEMETRY_TICK"

    def test_publish_sync_schedules_task(self):
        bc = Broadcaster()
        # publish_sync should not raise even without a running loop
        bc.publish_sync("TEST", {"x": 1})  # Should silently skip
