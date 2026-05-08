"""API router for Trend Signal — Dorothy dual-gate on/off system.

Gate 1 (trend):  HA MA crossover every 2h
Gate 2 (entry):  price < regular 1h open every ≤5min

Endpoints:
  GET  /trend/signals              — All cached signals
  GET  /trend/signal/{symbol}      — Full state for one symbol
  POST /trend/refresh/{symbol}     — Force refresh both gates
  POST /trend/refresh-all          — Refresh all Dorothy symbols
  GET  /trend/history/{symbol}     — Trend signal history
  GET  /trend/entry-log/{symbol}   — Entry gate log
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends

from runtime.api import deps
from runtime.app import AppContext
from runtime.modules.trend_signal import get_trend_signal_service

_LOG = logging.getLogger("pecunator.api.routers.trend")

router = APIRouter(prefix="/api/v1/trend", tags=["trend"])


async def _fetch_klines_1h(ctx: AppContext, symbol: str, limit: int = 10) -> list:
    """Fetch 1h klines from Binance."""
    if not ctx.gateway or not ctx.gateway._client:
        raise RuntimeError("Binance gateway not running")
    client = ctx.gateway._client
    return await asyncio.to_thread(
        client.get_klines, symbol=symbol, interval="1h", limit=limit
    )


async def _fetch_ticker_price(ctx: AppContext, symbol: str) -> float:
    """Fetch current ticker price from Binance."""
    if not ctx.gateway or not ctx.gateway._client:
        raise RuntimeError("Binance gateway not running")
    client = ctx.gateway._client
    ticker = await asyncio.to_thread(client.get_symbol_ticker, symbol=symbol)
    return float(ticker.get("price", 0))


@router.get("/signals")
async def get_all_signals(
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    """Return all cached trend + entry signals."""
    svc = get_trend_signal_service(ctx.config.data_dir)
    return {"signals": svc.get_all_signals()}


@router.get("/signal/{symbol}")
async def get_signal(
    symbol: str,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    """Return full dual-gate state for a symbol."""
    svc = get_trend_signal_service(ctx.config.data_dir)
    return svc.get_full_state(symbol.upper())


@router.post("/refresh/{symbol}")
async def refresh_signal(
    symbol: str,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    """Force-refresh both gates for a symbol."""
    svc = get_trend_signal_service(ctx.config.data_dir)
    sym = symbol.upper()

    try:
        klines = await _fetch_klines_1h(ctx, sym, limit=10)
        price = await _fetch_ticker_price(ctx, sym)
        result = svc.update_both(sym, klines, price)
        return {"ok": True, **result}
    except Exception as exc:
        _LOG.error("Trend refresh failed for %s: %s", sym, exc)
        return {
            "ok": False,
            "symbol": sym,
            "error": str(exc),
            "should_run": svc.should_run(sym),
        }


@router.post("/refresh-all")
async def refresh_all(
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    """Refresh both gates for all Dorothy symbols."""
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
            klines = await _fetch_klines_1h(ctx, sym, limit=10)
            price = await _fetch_ticker_price(ctx, sym)
            result = svc.update_both(sym, klines, price)
            results[sym] = {
                "should_run": result["should_run"],
                "trend": result["trend"]["signal"],
                "entry": result["entry"]["gate"],
                "price": price,
            }
        except Exception as exc:
            results[sym] = {"error": str(exc)}
        await asyncio.sleep(0.3)

    return {"ok": True, "refreshed": len(results), "results": results}


@router.get("/history/{symbol}")
async def get_trend_history(
    symbol: str, limit: int = 50,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    """Get trend signal history."""
    svc = get_trend_signal_service(ctx.config.data_dir)
    return {"symbol": symbol.upper(), "items": svc.get_trend_history(symbol, limit)}


@router.get("/entry-log/{symbol}")
async def get_entry_log(
    symbol: str, limit: int = 100,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    """Get entry gate log."""
    svc = get_trend_signal_service(ctx.config.data_dir)
    return {"symbol": symbol.upper(), "items": svc.get_entry_history(symbol, limit)}
