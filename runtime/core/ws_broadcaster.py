"""WebSocket broadcast hub — zero-polling telemetry push.

Provides a singleton `Broadcaster` that manages connected WebSocket clients.
The `TelemetryCollector` publishes snapshots here; all connected Flutter
clients receive them instantly without polling.

Event envelope::

    {
        "type": "TELEMETRY_TICK",   # | "FUSE_TRIPPED" | "ALERT" | ...
        "ts_utc": "2026-...",
        "seq": 42,
        "payload": { ... }
    }
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect

_LOG = logging.getLogger("pecunator.ws_broadcaster")


class Broadcaster:
    """Fan-out WebSocket broadcaster (singleton).

    Usage::

        from runtime.core.ws_broadcaster import get_broadcaster
        bc = get_broadcaster()

        # From TelemetryCollector or AlertDispatcher:
        await bc.publish("TELEMETRY_TICK", snapshot_dict)

        # From the /ws/telemetry endpoint:
        await bc.accept(websocket)
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._seq = 0
        self._last_snapshot: Optional[dict[str, Any]] = None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def last_snapshot(self) -> Optional[dict[str, Any]]:
        return self._last_snapshot

    # ── Client management ────────────────────────────────────────────

    async def accept(self, ws: WebSocket) -> None:
        """Accept a WebSocket, send latest snapshot, then listen until disconnect."""
        await ws.accept()
        self._clients.add(ws)
        _LOG.info("ws_broadcaster: client connected (%d total)", len(self._clients))

        # Send the most recent snapshot immediately so the UI doesn't start empty
        if self._last_snapshot:
            try:
                await ws.send_text(json.dumps(self._last_snapshot, default=str))
            except Exception:
                pass

        try:
            # Keep connection alive — read and discard client messages
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            self._clients.discard(ws)
            _LOG.info("ws_broadcaster: client disconnected (%d remain)", len(self._clients))

    # ── Publishing ───────────────────────────────────────────────────

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Broadcast an event to all connected clients."""
        self._seq += 1
        envelope = {
            "type": event_type,
            "ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "seq": self._seq,
            "payload": payload,
        }

        if event_type == "TELEMETRY_TICK":
            self._last_snapshot = envelope

        if not self._clients:
            return

        message = json.dumps(envelope, default=str)
        dead: list[WebSocket] = []

        for ws in list(self._clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._clients.discard(ws)
            _LOG.debug("ws_broadcaster: pruned dead client (%d remain)", len(self._clients))

    def publish_sync(self, event_type: str, payload: dict[str, Any]) -> None:
        """Non-async publish — schedules onto the running event loop.

        Safe to call from synchronous code (e.g. AlertDispatcher callbacks).
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event_type, payload))
        except RuntimeError:
            # No running loop — silently skip
            pass

    # ── Status ───────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        return {
            "connected_clients": len(self._clients),
            "total_published": self._seq,
            "has_last_snapshot": self._last_snapshot is not None,
        }


# ── Singleton ───────────────────────────────────────────────────────

_instance: Optional[Broadcaster] = None


def get_broadcaster() -> Broadcaster:
    """Return the global Broadcaster singleton."""
    global _instance
    if _instance is None:
        _instance = Broadcaster()
    return _instance
