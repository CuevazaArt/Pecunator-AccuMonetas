"""Prospector API router — symbol scanning and ranking for Dorothy hub."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from runtime.api import deps

_LOG = logging.getLogger("pecunator.api.prospector")

router = APIRouter(prefix="/prospector", tags=["prospector"])


@router.get("/scan")
async def scan_symbols(top_n: int = 15, min_volume: float = 500_000.0) -> dict[str, Any]:
    """Run full prospecting scan across all Binance USDT pairs.

    Returns the top N symbols ranked by Oscillation Score.
    Requires active gateway (authenticated Binance client).
    """
    from runtime.modules.prospector import get_prospector

    ctx = deps.get_ctx()
    if not ctx.gateway or not ctx.gateway.client:
        raise HTTPException(status_code=400, detail="Gateway not connected")

    client = ctx.gateway.client
    prospector = get_prospector()

    try:
        results = await prospector.scan(
            client,
            top_n=top_n,
            min_volume=min_volume,
            _to_thread=lambda fn: asyncio.to_thread(fn),
        )
    except Exception as e:
        _LOG.error("Prospector scan failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")

    return {
        "status": "ok",
        "results": [r.as_json() for r in results],
        "total_scanned": len(results),
        "recommendation": prospector.get_recommendation().as_json()
        if prospector.get_recommendation()
        else None,
    }


@router.get("/last")
async def get_last_scan() -> dict[str, Any]:
    """Return results from the most recent scan without re-scanning."""
    from runtime.modules.prospector import get_prospector

    prospector = get_prospector()
    last = prospector.get_last_scan()

    if not last:
        return {"status": "no_scan", "results": [], "recommendation": None}

    return {
        "status": "ok",
        "results": [r.as_json() for r in last],
        "total_scanned": len(last),
        "recommendation": prospector.get_recommendation().as_json()
        if prospector.get_recommendation()
        else None,
    }


@router.get("/score/{symbol}")
async def score_single_symbol(symbol: str) -> dict[str, Any]:
    """Compute oscillation score for a single symbol.

    Does NOT require a full scan — just fetches klines for the given symbol.
    """
    from runtime.modules.prospector import compute_oscillation_score

    ctx = deps.get_ctx()
    if not ctx.gateway or not ctx.gateway.client:
        raise HTTPException(status_code=400, detail="Gateway not connected")

    client = ctx.gateway.client
    sym = symbol.upper().strip()

    try:
        klines = await asyncio.to_thread(
            lambda: client.get_klines(symbol=sym, interval="1h", limit=100)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch klines: {e}")

    if not klines or len(klines) < 20:
        raise HTTPException(status_code=400, detail="Insufficient kline data")

    scores = compute_oscillation_score(klines)

    # Check margin eligibility
    margin_eligible = False
    try:
        iso_pairs = await asyncio.to_thread(
            lambda: client.get_all_isolated_margin_symbols()
        )
        margin_eligible = any(
            p.get("symbol") == sym and p.get("isMarginTrade")
            for p in (iso_pairs if isinstance(iso_pairs, list) else [])
        )
    except Exception:
        pass

    # Grade
    s = scores["oscillation_score"]
    if s >= 3.0:
        grade = "S"
    elif s >= 2.0:
        grade = "A"
    elif s >= 1.5:
        grade = "B"
    elif s >= 1.0:
        grade = "C"
    elif s >= 0.5:
        grade = "D"
    else:
        grade = "F"

    return {
        "symbol": sym,
        "oscillation_score": round(scores["oscillation_score"], 4),
        "atr_pct": round(scores["atr_pct"], 4),
        "adx": round(scores["adx"], 2),
        "choppiness": round(scores["choppiness"], 2),
        "current_price": scores["current_price"],
        "margin_eligible": margin_eligible,
        "grade": grade,
        "klines_analyzed": len(klines),
    }
