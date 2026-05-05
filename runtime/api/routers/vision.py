"""Vision Router — API exposure for the Visual Market Observer (VMO).

Provides access to the local regime library (SQLite) and VMO status.
"""

from fastapi import APIRouter, HTTPException
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
