"""Prospector API router — symbol scanning and ranking for Dorothy hub."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from binance.client import Client
from fastapi import APIRouter, HTTPException

from runtime.api import deps

_LOG = logging.getLogger("pecunator.api.prospector")

router = APIRouter(prefix="/prospector", tags=["prospector"])


def _get_client() -> Client:
    """Get a Binance client — authenticated if gateway is up, public otherwise.

    The prospector only needs public market data (tickers, exchange info, klines).
    Margin eligibility check requires auth but is optional and has a fallback.
    """
    ctx = deps.get_ctx()
    if ctx.gateway and ctx.gateway.client:
        return ctx.gateway.client
    # Public client — no auth needed for market data endpoints
    return Client("", "", requests_params={"timeout": 15})


@router.get("/scan")
async def scan_symbols(top_n: int = 15, min_volume: float = 500_000.0) -> dict[str, Any]:
    """Run full prospecting scan across all Binance USDT pairs.

    Returns the top N symbols ranked by EVI (Electric Volatility Index).
    Works without gateway — public market data endpoints are sufficient.
    Margin eligibility will be unknown without authenticated gateway.
    """
    try:
        from runtime.modules.prospector import get_prospector

        client = _get_client()
        prospector = get_prospector()

        try:
            results = await asyncio.wait_for(
                prospector.scan(
                    client,
                    top_n=top_n,
                    min_volume=min_volume,
                    _to_thread=lambda fn: asyncio.to_thread(fn),
                ),
                timeout=120.0,
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Prospector scan timed out after 120s")

        return {
            "status": "ok",
            "results": [r.as_json() for r in results],
            "total_scanned": len(results),
            "recommendation": prospector.get_recommendation().as_json()
            if prospector.get_recommendation()
            else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        _LOG.error("Unhandled error in scan: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")



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
    """Compute EVI score for a single symbol.

    Does NOT require a full scan — just fetches klines for the given symbol.
    Works without gateway using public Binance API.
    """
    from runtime.modules.prospector import compute_oscillation_score

    client = _get_client()
    sym = symbol.upper().strip()

    try:
        klines = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: client.get_klines(symbol=sym, interval="1h", limit=100)
            ),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=f"Kline fetch timed out for {sym}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch klines: {e}")

    if not klines or len(klines) < 20:
        raise HTTPException(status_code=400, detail="Insufficient kline data")

    scores = compute_oscillation_score(klines)

    # Check margin eligibility (requires auth — graceful fallback)
    margin_eligible = False
    ctx = deps.get_ctx()
    if ctx.gateway and ctx.gateway.client:
        try:
            iso_pairs = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: ctx.gateway.client.get_all_isolated_margin_symbols()
                ),
                timeout=10.0,
            )
            margin_eligible = any(
                p.get("symbol") == sym and p.get("isMarginTrade")
                for p in (iso_pairs if isinstance(iso_pairs, list) else [])
            )
        except Exception:
            pass

    # EVI-based grade
    evi = scores.get("evi_score", 0)
    if evi >= 0.5:
        grade = "S"
    elif evi >= 0.2:
        grade = "A"
    elif evi >= 0.1:
        grade = "B"
    elif evi >= 0.05:
        grade = "C"
    elif evi >= 0.01:
        grade = "D"
    else:
        grade = "F"

    return {
        "symbol": sym,
        "evi_score": round(evi, 4),
        "oscillation_score": round(scores["oscillation_score"], 4),
        "atr_pct": round(scores["atr_pct"], 4),
        "adx": round(scores["adx"], 2),
        "choppiness": round(scores["choppiness"], 2),
        "avg_speed": round(scores.get("avg_speed", 0), 4),
        "freq_extreme": round(scores.get("freq_extreme", 0), 4),
        "kurtosis": round(scores.get("kurtosis", 0), 2),
        "current_price": scores["current_price"],
        "margin_eligible": margin_eligible,
        "grade": grade,
        "klines_analyzed": len(klines),
    }
