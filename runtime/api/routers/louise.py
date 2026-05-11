"""Louise Bot Hub API Router — state, control, and telemetry endpoints."""

from __future__ import annotations

import copy
import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/louise", tags=["louise"])

# ─── In-memory registry ───────────────────────────────────────────────
# Mutable state for demo/development. Replace with DB-backed service in Phase 2.

_REGISTRY: dict[str, dict[str, Any]] = {
    "louise_btc_001": {
        "id": "louise_btc_001",
        "name": "louise_btc_001",
        "symbol": "BTC/USDT",
        "status": "running",
        "current_price": 42500.00,
        "position_size": 0.05,
        "cost_basis": 1200.00,
        "unrealized_pnl": 127.50,
        "unrealized_pct": 2.81,
        "free_balance": 450.00,
        "target_profit_pct": 5.0,
        "progress_percent": 56.2,
        "daily_budget": 1000.00,
        "trades_today": 3,
    },
    "louise_eth_001": {
        "id": "louise_eth_001",
        "name": "louise_eth_001",
        "symbol": "ETH/USDT",
        "status": "paused",
        "current_price": 2150.00,
        "position_size": 2.3,
        "cost_basis": 1850.00,
        "unrealized_pnl": -22.10,
        "unrealized_pct": -1.2,
        "free_balance": 320.00,
        "target_profit_pct": 5.0,
        "progress_percent": 0.0,
        "daily_budget": 800.00,
        "trades_today": 1,
    },
    "louise_sol_001": {
        "id": "louise_sol_001",
        "name": "louise_sol_001",
        "symbol": "SOL/USDT",
        "status": "shutdown",
        "current_price": 142.00,
        "position_size": 0.0,
        "cost_basis": 800.00,
        "unrealized_pnl": 85.50,
        "unrealized_pct": 10.69,
        "free_balance": 885.50,
        "target_profit_pct": 5.0,
        "progress_percent": 100.0,
        "daily_budget": 500.00,
        "trades_today": 0,
    },
}


def _hub_metrics() -> dict[str, Any]:
    bots = list(_REGISTRY.values())
    active = sum(1 for b in bots if b["status"] == "running")
    portfolio = sum(b["cost_basis"] + b["unrealized_pnl"] for b in bots)
    free = sum(b["free_balance"] for b in bots)
    pnl_abs = sum(b["unrealized_pnl"] for b in bots)
    pnl_pct = round(pnl_abs / portfolio * 100, 2) if portfolio > 0 else 0.0
    return {
        "active_bots": active,
        "total_portfolio": round(portfolio, 2),
        "total_free_balance": round(free, 2),
        "total_unrealized_pnl": round(pnl_abs, 2),
        "hub_pnl_percent": pnl_pct,
        "completed_epochs": 12,
    }


def get_louise_telemetry() -> dict[str, Any]:
    """Export Louise state for inclusion in the WS TELEMETRY_TICK payload."""
    return {
        "louise_bots": list(_REGISTRY.values()),
        "louise_metrics": _hub_metrics(),
    }


# ─── Pydantic models ──────────────────────────────────────────────────

class BotCreateRequest(BaseModel):
    symbol: str
    daily_budget: float = 500.0
    target_profit_pct: float = 5.0


class BotUpdateRequest(BaseModel):
    daily_budget: float | None = None
    target_profit_pct: float | None = None
    symbol: str | None = None


# ─── GET endpoints ────────────────────────────────────────────────────

@router.get("/bots")
async def get_louise_bots() -> list[dict[str, Any]]:
    return list(_REGISTRY.values())


@router.get("/metrics")
async def get_hub_metrics() -> dict[str, Any]:
    return _hub_metrics()


@router.get("/weight-governor/status")
async def get_weight_status() -> dict[str, Any]:
    try:
        from runtime.core.settings import api_weight_limit_1m_display
        limit = api_weight_limit_1m_display()
    except Exception:
        limit = 6000
    weight = 0
    try:
        from runtime.api import deps
        ctx = deps.get_ctx()
        weight = getattr(getattr(ctx, "state", None), "api_weight_used_1m", None) or 0
    except Exception:
        weight = 1050  # fallback demo value
    pct = round(weight / limit * 100, 1)
    if pct < 50:
        zone, msg = "GREEN", f"API weight normal. {pct}% del límite usado."
    elif pct < 80:
        zone, msg = "YELLOW", f"API weight elevado. {pct}% del límite usado."
    else:
        zone, msg = "RED", f"API weight crítico. {pct}% del límite usado."
    return {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "current_weight": weight,
        "weight_per_minute": weight,
        "weight_limit": limit,
        "weight_zone": zone,
        "status_message": msg,
    }


@router.get("/weight-governor/history")
async def get_weight_history() -> list[dict[str, Any]]:
    return [
        {"time": "00:00", "louise_btc_001": 150, "louise_eth_001": 100, "louise_sol_001": 80},
        {"time": "04:00", "louise_btc_001": 280, "louise_eth_001": 200, "louise_sol_001": 150},
        {"time": "08:00", "louise_btc_001": 450, "louise_eth_001": 320, "louise_sol_001": 280},
        {"time": "12:00", "louise_btc_001": 520, "louise_eth_001": 420, "louise_sol_001": 380},
        {"time": "16:00", "louise_btc_001": 680, "louise_eth_001": 550, "louise_sol_001": 490},
        {"time": "20:00", "louise_btc_001": 890, "louise_eth_001": 720, "louise_sol_001": 620},
        {"time": "24:00", "louise_btc_001": 1050, "louise_eth_001": 850, "louise_sol_001": 750},
    ]


@router.get("/telemetry/requests")
async def get_requests_stats() -> dict[str, Any]:
    bots = list(_REGISTRY.values())
    counts = {b["id"]: b.get("trades_today", 0) * 82 for b in bots}
    return {**counts, "total": sum(counts.values())}


@router.get("/telemetry/bandwidth")
async def get_bandwidth_stats() -> dict[str, Any]:
    bots = list(_REGISTRY.values())
    bw = {b["id"]: b.get("trades_today", 0) * 82000 for b in bots}
    return {**bw, "total": sum(bw.values())}


@router.get("/health")
async def louise_health() -> dict[str, Any]:
    active = sum(1 for b in _REGISTRY.values() if b["status"] == "running")
    return {
        "status": "healthy",
        "active_bots": active,
        "total_bots": len(_REGISTRY),
        "weight_zone": "GREEN",
        "last_check": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


# ─── Control endpoints ────────────────────────────────────────────────

@router.post("/bots")
async def create_bot(req: BotCreateRequest) -> dict[str, Any]:
    base = req.symbol.split("/")[0].lower()
    bot_id = f"louise_{base}_{str(uuid.uuid4())[:4]}"
    _REGISTRY[bot_id] = {
        "id": bot_id,
        "name": bot_id,
        "symbol": req.symbol,
        "status": "running",
        "current_price": 0.0,
        "position_size": 0.0,
        "cost_basis": 0.0,
        "unrealized_pnl": 0.0,
        "unrealized_pct": 0.0,
        "free_balance": req.daily_budget,
        "target_profit_pct": req.target_profit_pct,
        "progress_percent": 0.0,
        "daily_budget": req.daily_budget,
        "trades_today": 0,
    }
    _push_louise_ws()
    return {"bot_id": bot_id, "status": "created", "bot": _REGISTRY[bot_id]}


@router.post("/bots/{bot_id}/pause")
async def pause_bot(bot_id: str) -> dict[str, Any]:
    if bot_id not in _REGISTRY:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    _REGISTRY[bot_id]["status"] = "paused"
    _push_louise_ws()
    return {"bot_id": bot_id, "status": "paused"}


@router.post("/bots/{bot_id}/resume")
async def resume_bot(bot_id: str) -> dict[str, Any]:
    if bot_id not in _REGISTRY:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    _REGISTRY[bot_id]["status"] = "running"
    _push_louise_ws()
    return {"bot_id": bot_id, "status": "running"}


@router.patch("/bots/{bot_id}")
async def update_bot(bot_id: str, req: BotUpdateRequest) -> dict[str, Any]:
    if bot_id not in _REGISTRY:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    bot = _REGISTRY[bot_id]
    if req.daily_budget is not None:
        bot["daily_budget"] = req.daily_budget
    if req.target_profit_pct is not None:
        bot["target_profit_pct"] = req.target_profit_pct
    if req.symbol is not None:
        bot["symbol"] = req.symbol
    _push_louise_ws()
    return {"bot_id": bot_id, "status": "updated", "bot": bot}


@router.delete("/bots/{bot_id}")
async def delete_bot(bot_id: str) -> dict[str, Any]:
    if bot_id not in _REGISTRY:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    del _REGISTRY[bot_id]
    _push_louise_ws()
    return {"bot_id": bot_id, "status": "deleted"}


# ─── WS push helper ──────────────────────────────────────────────────

def _push_louise_ws() -> None:
    """Push Louise state update immediately via WS broadcaster."""
    try:
        from runtime.core.ws_broadcaster import get_broadcaster
        bc = get_broadcaster()
        bc.publish_sync("TELEMETRY_TICK", {
            "ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            **get_louise_telemetry(),
        })
    except Exception:
        pass
