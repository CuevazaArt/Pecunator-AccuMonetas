"""Vision Router — API exposure for the Visual Market Observer (VMO).

Provides access to the local regime library (SQLite) and VMO status.
"""

import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Any, Dict, List

from runtime.modules.vision.config import get_vmo_config
from runtime.modules.vision.observer import VMObserver
from runtime.modules.vision.regime_cache import RegimeCache

router = APIRouter(prefix="/api/v1/vision", tags=["vision"])

# We instantiate a stateless cache reader for the API
_cache = RegimeCache(get_vmo_config().db_path)

# And a stub observer just to get config/status without running the loop
_observer = VMObserver()

@router.get("/status", response_model=Dict[str, Any])
async def get_vision_status():
    """Get the current configuration and operational status of the VMO."""
    return _observer.status()

@router.get("/regimes/latest", response_model=Dict[str, Dict[str, Any]])
async def get_latest_regimes():
    """Get the most recent regime classification for every symbol and timeframe."""
    raw = _cache.get_latest_per_symbol()
    # Serialize dataclasses to dicts
    return {
        sym: {tf: r.to_dict() for tf, r in tfs.items()}
        for sym, tfs in raw.items()
    }

@router.get("/regimes/{symbol}", response_model=List[Dict[str, Any]])
async def get_regime_history(symbol: str, timeframe: str = "", limit: int = 50):
    """Get the historical regime classifications for a specific symbol."""
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")
    
    regimes = _cache.get_latest(symbol=symbol.upper(), timeframe=timeframe, limit=limit)
    return [r.to_dict() for r in regimes]

@router.websocket("/stream")
async def vision_stream(websocket: WebSocket):
    """Event Bus Bridge: Stream VMO regime updates to connected clients (e.g., Ethos Mesh)."""
    await websocket.accept()
    last_seen_ts = {}
    
    try:
        # Initialize last_seen_ts with current state
        initial_raw = _cache.get_latest_per_symbol()
        for sym, tfs in initial_raw.items():
            if sym not in last_seen_ts:
                last_seen_ts[sym] = {}
            for tf, regime in tfs.items():
                last_seen_ts[sym][tf] = regime.analyzed_at
        
        while True:
            # Poll every 3 seconds for changes
            await asyncio.sleep(3.0)
            
            current_raw = _cache.get_latest_per_symbol()
            updates = []
            
            for sym, tfs in current_raw.items():
                if sym not in last_seen_ts:
                    last_seen_ts[sym] = {}
                for tf, regime in tfs.items():
                    prev_ts = last_seen_ts[sym].get(tf)
                    if prev_ts != regime.analyzed_at:
                        # State changed!
                        updates.append(regime.to_dict())
                        last_seen_ts[sym][tf] = regime.analyzed_at
            
            if updates:
                payload = {
                    "type": "vmo_telemetry",
                    "timestamp": asyncio.get_event_loop().time(),
                    "updates": updates
                }
                await websocket.send_json(payload)
                
    except WebSocketDisconnect:
        pass
    except Exception:
        # Log exception silently to prevent server crash on client disconnect
        pass
