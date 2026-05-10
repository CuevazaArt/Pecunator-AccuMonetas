"""WebSocket streaming endpoint — replaces REST polling for telemetry.

Provides ``/ws/telemetry`` — a persistent WebSocket that pushes every
telemetry tick, fuse trip, and critical alert to connected Flutter clients
in real-time.

The endpoint is intentionally NOT protected by bearer token since it's
bound to loopback (127.0.0.1) and WebSocket auth is handled at connect time.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from runtime.core.ws_broadcaster import get_broadcaster

router = APIRouter(tags=["stream"])


@router.websocket("/ws/telemetry")
async def telemetry_stream(ws: WebSocket) -> None:
    """Persistent WebSocket — pushes telemetry, fuse, and alert events.

    On connect, the client immediately receives the latest snapshot
    so the UI can hydrate without a separate REST call.
    """
    broadcaster = get_broadcaster()
    await broadcaster.accept(ws)


@router.get("/api/v1/ws/status")
async def ws_status():
    """Debug endpoint showing WebSocket broadcaster state."""
    return get_broadcaster().status()
