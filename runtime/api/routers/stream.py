"""WebSocket streaming endpoint — replaces REST polling for telemetry.

Provides ``/ws/telemetry`` — a persistent WebSocket that pushes every
telemetry tick, fuse trip, and critical alert to connected Flutter clients
in real-time.

WebSocket auth is required via token query param or x-api-token header
unless PECUNATOR_API_AUTH_DISABLED is explicitly set to 1/true.
"""

from __future__ import annotations

import os
import logging
from fastapi import APIRouter, WebSocket, Depends
from runtime.api.auth import get_api_token, verify_token
from runtime.core.ws_broadcaster import get_broadcaster

_LOG = logging.getLogger("pecunator.api.stream")

router = APIRouter(tags=["stream"])


@router.websocket("/ws/telemetry")
async def telemetry_stream(ws: WebSocket) -> None:
    """Persistent WebSocket — pushes telemetry, fuse, and alert events.

    Requires valid API token via:
    - Query param: ?token=<api_token>
    - Header: X-API-Token: <api_token>
    """
    token = ws.query_params.get("token") or ws.headers.get("x-api-token")
    if token != get_api_token() and os.environ.get("PECUNATOR_API_AUTH_DISABLED", "").strip() not in ("1", "true"):
        _LOG.warning("WebSocket connection rejected: invalid or missing token")
        await ws.close(code=1008, reason="Unauthorized")
        return

    broadcaster = get_broadcaster()
    await broadcaster.accept(ws)


@router.get("/api/v1/ws/status")
async def ws_status(token: str = Depends(verify_token)):
    """Debug endpoint showing WebSocket broadcaster state (requires auth)."""
    return get_broadcaster().status()
