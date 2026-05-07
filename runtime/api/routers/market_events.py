"""Market Events & News aggregator — provides macro intelligence to the trading system.

Fetches and caches financial events relevant to crypto trading:
- Crypto Fear & Greed Index
- Major economic calendar events (interest rates, CPI, etc.)
- 24h activity heatmap by hour (statistical)
- Upcoming crypto events (ICOs, unlocks, etc.)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger("pecunator.market_events")

router = APIRouter(prefix="/api/v1/events", tags=["market-events"])

# ── In-memory cache ────────────────────────────────────────────────
_cache: dict[str, Any] = {}
_cache_ts: dict[str, float] = {}
_CACHE_TTL_SEC = 300  # 5 minutes


def _is_fresh(key: str) -> bool:
    ts = _cache_ts.get(key, 0)
    return (datetime.now(timezone.utc).timestamp() - ts) < _CACHE_TTL_SEC


# ── Static economic calendar (major recurring events) ──────────────
_ECONOMIC_CALENDAR: list[dict[str, Any]] = [
    {"event": "FOMC Interest Rate Decision", "frequency": "~6 weeks", "impact": "critical",
     "description": "Federal Reserve sets benchmark interest rates. Strongly moves all risk assets.",
     "typical_hours_utc": [18, 19]},
    {"event": "US CPI (Consumer Price Index)", "frequency": "monthly", "impact": "high",
     "description": "Inflation gauge. Higher-than-expected = bearish for risk assets.",
     "typical_hours_utc": [12, 13]},
    {"event": "US Non-Farm Payrolls", "frequency": "monthly (1st Friday)", "impact": "high",
     "description": "Employment data. Strong jobs = hawkish Fed = bearish crypto short-term.",
     "typical_hours_utc": [12, 13]},
    {"event": "ECB Interest Rate Decision", "frequency": "~6 weeks", "impact": "high",
     "description": "European Central Bank rates. Affects EUR pairs and global liquidity.",
     "typical_hours_utc": [12, 13]},
    {"event": "US GDP (Gross Domestic Product)", "frequency": "quarterly", "impact": "medium",
     "description": "Economic growth gauge. Surprise readings move markets.",
     "typical_hours_utc": [12, 13]},
    {"event": "China PMI (Manufacturing)", "frequency": "monthly", "impact": "medium",
     "description": "Chinese manufacturing health. Affects BTC mining narrative and Asian sessions.",
     "typical_hours_utc": [1, 2]},
    {"event": "BOJ Interest Rate Decision", "frequency": "~6 weeks", "impact": "medium",
     "description": "Bank of Japan policy. Yen carry trade unwinds can crash all risk assets.",
     "typical_hours_utc": [3, 4]},
    {"event": "US PCE Price Index", "frequency": "monthly", "impact": "high",
     "description": "Fed's preferred inflation measure. Moves rate expectations.",
     "typical_hours_utc": [12, 13]},
]

# ── 24h Activity Heatmap (statistical) ─────────────────────────────
# Based on historical crypto market volume analysis
_HOURLY_ACTIVITY: list[dict[str, Any]] = [
    {"hour_utc": h, "label": f"{h:02d}:00 UTC",
     "activity_score": score, "session": session, "notes": notes}
    for h, score, session, notes in [
        (0, 0.65, "Asia", "Tokyo open nearby"),
        (1, 0.70, "Asia", "Tokyo active, China PMI releases"),
        (2, 0.75, "Asia", "Peak Asia session"),
        (3, 0.70, "Asia", "BOJ decisions, Tokyo mid-session"),
        (4, 0.55, "Asia→EU", "Asia winding down"),
        (5, 0.50, "Asia→EU", "Quiet transition"),
        (6, 0.60, "EU", "Frankfurt pre-market"),
        (7, 0.75, "EU", "London open, high volatility"),
        (8, 0.85, "EU", "Peak EU session, FX overlap"),
        (9, 0.80, "EU", "EU macro releases"),
        (10, 0.70, "EU", "EU mid-session"),
        (11, 0.65, "EU", "Pre-US quiet"),
        (12, 0.90, "EU+US", "US pre-market, CPI/NFP releases"),
        (13, 0.95, "EU+US", "US open overlap — PEAK VOLATILITY"),
        (14, 1.00, "US", "NYSE open, maximum liquidity"),
        (15, 0.90, "US", "US mid-session"),
        (16, 0.80, "US", "EU close, reduced liquidity"),
        (17, 0.70, "US", "US afternoon"),
        (18, 0.75, "US", "FOMC decisions typically here"),
        (19, 0.65, "US", "US late afternoon"),
        (20, 0.55, "US→Asia", "US closing, after-hours"),
        (21, 0.45, "Dead zone", "Lowest global liquidity"),
        (22, 0.40, "Dead zone", "Minimum activity — ideal for maintenance"),
        (23, 0.50, "Asia early", "Asia pre-market, NZ/AU open"),
    ]
]

# ── Geopolitical risk factors (static but curated) ─────────────────
_GEO_FACTORS: list[dict[str, Any]] = [
    {"factor": "US-China Trade Relations", "impact": "high", "direction": "risk-off if tensions",
     "assets_affected": ["BTC", "ETH", "SOL"], "monitor": "Reuters, SCMP"},
    {"factor": "US Regulatory Clarity (SEC/CFTC)", "impact": "critical", "direction": "varies",
     "assets_affected": ["all crypto"], "monitor": "SEC.gov, CoinDesk"},
    {"factor": "Middle East Conflict Escalation", "impact": "medium", "direction": "risk-off → BTC bid",
     "assets_affected": ["BTC", "GOLD"], "monitor": "Reuters, AP"},
    {"factor": "EU MiCA Regulation", "impact": "medium", "direction": "long-term bullish clarity",
     "assets_affected": ["stablecoins", "exchanges"], "monitor": "EU Parliament"},
    {"factor": "Central Bank Digital Currencies (CBDCs)", "impact": "medium", "direction": "mixed",
     "assets_affected": ["stablecoins", "DeFi"], "monitor": "BIS, central bank releases"},
]


@router.get("/calendar")
async def economic_calendar() -> dict[str, Any]:
    """Return major economic events that affect crypto markets."""
    return {
        "events": _ECONOMIC_CALENDAR,
        "count": len(_ECONOMIC_CALENDAR),
        "note": "Dates are approximate; check financial calendars for exact schedule.",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/activity_heatmap")
async def activity_heatmap() -> dict[str, Any]:
    """Return 24h market activity heatmap with session labels."""
    now_utc = datetime.now(timezone.utc)
    current_hour = now_utc.hour
    current_entry = _HOURLY_ACTIVITY[current_hour]
    return {
        "hours": _HOURLY_ACTIVITY,
        "current_hour_utc": current_hour,
        "current_session": current_entry["session"],
        "current_activity_score": current_entry["activity_score"],
        "recommendation": _activity_recommendation(current_entry["activity_score"]),
        "ts_utc": now_utc.isoformat(),
    }


def _activity_recommendation(score: float) -> str:
    if score >= 0.85:
        return "Alta actividad — máxima liquidez, spreads ajustados. Buen momento para ejecutar."
    if score >= 0.65:
        return "Actividad moderada — condiciones normales de trading."
    if score >= 0.45:
        return "Baja actividad — spreads amplios posibles, evitar market orders grandes."
    return "Zona muerta — mínima liquidez. Ideal para mantenimiento, evitar operar."


@router.get("/geopolitical")
async def geopolitical_factors() -> dict[str, Any]:
    """Return curated geopolitical risk factors relevant to crypto."""
    return {
        "factors": _GEO_FACTORS,
        "count": len(_GEO_FACTORS),
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/fear_greed")
async def fear_greed_index() -> dict[str, Any]:
    """Fetch Crypto Fear & Greed Index (cached 5min)."""
    if _is_fresh("fear_greed"):
        return _cache["fear_greed"]

    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.alternative.me/fng/?limit=7&format=json",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = {
                        "entries": data.get("data", []),
                        "source": "alternative.me",
                        "ts_utc": datetime.now(timezone.utc).isoformat(),
                    }
                    _cache["fear_greed"] = result
                    _cache_ts["fear_greed"] = datetime.now(timezone.utc).timestamp()
                    return result
    except Exception as e:
        logger.warning("Fear & Greed fetch failed: %s", e)

    return {
        "entries": [],
        "source": "alternative.me",
        "error": "Unable to fetch — check network",
        "ts_utc": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/summary")
async def events_summary() -> dict[str, Any]:
    """Aggregated macro intelligence summary."""
    now_utc = datetime.now(timezone.utc)
    current_hour = now_utc.hour
    activity = _HOURLY_ACTIVITY[current_hour]

    # Try fear/greed
    fg = _cache.get("fear_greed", {}).get("entries", [])
    fg_latest = fg[0] if fg else None

    return {
        "current_hour_utc": current_hour,
        "session": activity["session"],
        "activity_score": activity["activity_score"],
        "activity_recommendation": _activity_recommendation(activity["activity_score"]),
        "fear_greed_value": int(fg_latest["value"]) if fg_latest else None,
        "fear_greed_label": fg_latest.get("value_classification") if fg_latest else None,
        "upcoming_high_impact_events": [
            e["event"] for e in _ECONOMIC_CALENDAR if e["impact"] in ("critical", "high")
        ],
        "geo_risk_count": len(_GEO_FACTORS),
        "ts_utc": now_utc.isoformat(),
    }
