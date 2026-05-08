"""API router for Trend Signal — Dorothy MA crossover on/off gate.

Endpoints:
  GET  /trend/signals          — All cached signals
  GET  /trend/signal/{symbol}  — Signal for one symbol
  POST /trend/refresh/{symbol} — Force refresh from Binance klines
  POST /trend/refresh-all      — Refresh all tracked symbols
  GET  /trend/history/{symbol} — Historical signal log
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter

from runtime.api._ctx import get_ctx
from runtime.modules.trend_signal import get_trend_signal_service

_LOG = logging.getLogger("pecunator.api.routers.trend")

router = APIRouter(prefix="/trend", tags=["trend"])


async def _fetch_klines(symbol: str, interval: str = "1h", limit: int = 10) -> list:
    """Fetch klines from Binance via the gateway client."""
    ctx = get_ctx()
    client = ctx.binance_client
    if client is None:
        raise RuntimeError("Binance client not available")
    klines = await asyncio.to_thread(
        client.get_klines, symbol=symbol, interval=interval, limit=limit
    )
    return klines


@router.get("/signals")
async def get_all_signals() -> dict[str, Any]:
    """Return all cached trend signals."""
    ctx = get_ctx()
    svc = get_trend_signal_service(ctx.config.data_dir)
    return {"signals": svc.get_all_signals()}


@router.get("/signal/{symbol}")
async def get_signal(symbol: str) -> dict[str, Any]:
    """Return current trend signal for a symbol."""
    ctx = get_ctx()
    svc = get_trend_signal_service(ctx.config.data_dir)
    sym = symbol.upper()
    sig = svc.get_signal(sym)
    state = svc._cache.get(sym)
    return {
        "symbol": sym,
        "signal": sig,
        "should_run": sig == "BULLISH",
        "ma1": state.ma1 if state else None,
        "ma2": state.ma2 if state else None,
        "last_check": state.last_ts_utc if state else None,
    }


@router.post("/refresh/{symbol}")
async def refresh_signal(symbol: str) -> dict[str, Any]:
    """Force-refresh trend signal for a symbol by fetching fresh klines."""
    ctx = get_ctx()
    svc = get_trend_signal_service(ctx.config.data_dir)
    sym = symbol.upper()

    try:
        klines = await _fetch_klines(sym, interval="1h", limit=10)
        result = svc.update_from_klines(sym, klines)
        return {
            "symbol": sym,
            "ok": True,
            "signal": result["signal"],
            "ma1": result["ma1"],
            "ma2": result["ma2"],
            "should_run": result["signal"] == "BULLISH",
            "candles_used": len(klines),
        }
    except Exception as exc:
        _LOG.error("Trend refresh failed for %s: %s", sym, exc)
        return {
            "symbol": sym,
            "ok": False,
            "error": str(exc),
            "signal": svc.get_signal(sym),
        }


@router.post("/refresh-all")
async def refresh_all() -> dict[str, Any]:
    """Refresh signals for all Dorothy symbols that need it."""
    ctx = get_ctx()
    svc = get_trend_signal_service(ctx.config.data_dir)

    # Get all unique symbols from Dorothy bots
    symbols: set[str] = set()
    try:
        from runtime.api.routers.dorothy import _get_hub
        hub = _get_hub()
        for bot in hub.list_bots():
            sym = bot.get("symbol", "")
            if sym:
                symbols.add(sym.upper())
    except Exception:
        pass

    if not symbols:
        return {"ok": True, "refreshed": 0, "message": "no_dorothy_symbols"}

    results = {}
    for sym in symbols:
        try:
            klines = await _fetch_klines(sym, interval="1h", limit=10)
            result = svc.update_from_klines(sym, klines)
            results[sym] = {
                "signal": result["signal"],
                "ma1": result["ma1"],
                "ma2": result["ma2"],
                "should_run": result["signal"] == "BULLISH",
            }
        except Exception as exc:
            results[sym] = {"error": str(exc)}
        # Small delay between symbols to respect API weight
        await asyncio.sleep(0.2)

    return {"ok": True, "refreshed": len(results), "results": results}


@router.get("/history/{symbol}")
async def get_history(symbol: str, limit: int = 50) -> dict[str, Any]:
    """Get historical signal log for a symbol."""
    ctx = get_ctx()
    svc = get_trend_signal_service(ctx.config.data_dir)
    history = svc.get_history(symbol.upper(), limit=limit)
    return {"symbol": symbol.upper(), "items": history}
