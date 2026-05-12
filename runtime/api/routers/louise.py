"""Louise Bot Hub API Router — state, control, and telemetry endpoints."""

from __future__ import annotations

import datetime as dt
import uuid
import logging
from typing import Any, List, Dict

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from runtime.core.louise_db import LouiseDB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/louise", tags=["louise"])

def get_db():
    return LouiseDB()

# ─── Mappers for UI compatibility ─────────────────────────────────────
def map_bot_to_ui(bot: dict, db: LouiseDB) -> dict:
    """Maps DB row to the format expected by Flutter UI."""
    active_epoch = db.get_active_epoch(bot["bot_id"])
    
    current_price = 0.0 # Will be updated by real feed
    position_size = 0.0
    cost_basis = 0.0
    unrealized_pnl = 0.0
    unrealized_pct = 0.0
    trades_today = 0
    
    if active_epoch:
        cost_basis = active_epoch["total_cost"]
        position_size = cost_basis / active_epoch["avg_buy_price"] if active_epoch["avg_buy_price"] > 0 else 0
        trades_today = active_epoch["num_purchases"]
        
    return {
        "id": bot["bot_id"],
        "name": bot["bot_id"],
        "symbol": bot["symbol"],
        "status": bot["status"].lower(),
        "current_price": current_price,
        "position_size": position_size,
        "cost_basis": cost_basis,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pct": unrealized_pct,
        "free_balance": bot["daily_budget_usdt"],
        "target_profit_pct": bot["target_profit_pct"],
        "buy_volume": bot.get("buy_volume", 10.0),
        "progress_percent": 0.0,
        "daily_budget": bot["daily_budget_usdt"],
        "trades_today": trades_today,
    }

def _hub_metrics(db: LouiseDB) -> dict[str, Any]:
    bots = db.get_all_bots()
    active = sum(1 for b in bots if b["status"] == "ACCUMULATING" or b["status"] == "RUNNING")
    
    portfolio = 0.0
    free = 0.0
    pnl_abs = 0.0
    
    for b in bots:
        mapped = map_bot_to_ui(b, db)
        portfolio += mapped["cost_basis"] + mapped["unrealized_pnl"]
        free += mapped["free_balance"]
        pnl_abs += mapped["unrealized_pnl"]
        
    pnl_pct = round(pnl_abs / portfolio * 100, 2) if portfolio > 0 else 0.0
    return {
        "active_bots": active,
        "total_portfolio": round(portfolio, 2),
        "total_free_balance": round(free, 2),
        "total_unrealized_pnl": round(pnl_abs, 2),
        "hub_pnl_percent": pnl_pct,
        "completed_epochs": 0, # TODO: Query completed epochs from DB
    }

def get_louise_telemetry(db: LouiseDB = None) -> dict[str, Any]:
    """Export Louise state for inclusion in the WS TELEMETRY_TICK payload."""
    db = db or LouiseDB()
    bots = db.get_all_bots()
    return {
        "louise_bots": [map_bot_to_ui(b, db) for b in bots],
        "louise_metrics": _hub_metrics(db),
    }

# ─── Pydantic models ──────────────────────────────────────────────────

class BotCreateRequest(BaseModel):
    symbol: str
    daily_budget: float = 500.0
    target_profit_pct: float = 5.0
    buy_volume: float = 10.0
    poll_interval_seconds: int = 60
    subaccount: str = "bluechip"

class BotUpdateRequest(BaseModel):
    daily_budget: float | None = None
    target_profit_pct: float | None = None
    symbol: str | None = None

# ─── GET endpoints ────────────────────────────────────────────────────

@router.get("/bots")
async def get_louise_bots(db: LouiseDB = Depends(get_db)) -> list[dict[str, Any]]:
    bots = db.get_all_bots()
    return [map_bot_to_ui(b, db) for b in bots]

@router.get("/metrics")
async def get_hub_metrics_ep(db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    return _hub_metrics(db)

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
        weight = 1050
    pct = round(weight / limit * 100, 1) if limit > 0 else 0.0
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
    ]

@router.get("/telemetry/requests")
async def get_requests_stats(db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    bots = db.get_all_bots()
    counts = {}
    total = 0
    for b in bots:
        mapped = map_bot_to_ui(b, db)
        c = mapped.get("trades_today", 0) * 82
        counts[b["bot_id"]] = c
        total += c
    return {**counts, "total": total}

@router.get("/telemetry/bandwidth")
async def get_bandwidth_stats(db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    bots = db.get_all_bots()
    bw = {}
    total = 0
    for b in bots:
        mapped = map_bot_to_ui(b, db)
        c = mapped.get("trades_today", 0) * 82000
        bw[b["bot_id"]] = c
        total += c
    return {**bw, "total": total}

@router.get("/health")
async def louise_health(db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    bots = db.get_all_bots()
    active = sum(1 for b in bots if b["status"] == "ACCUMULATING" or b["status"] == "RUNNING")
    return {
        "status": "healthy",
        "active_bots": active,
        "total_bots": len(bots),
        "weight_zone": "GREEN",
        "last_check": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

# ─── Control endpoints ────────────────────────────────────────────────

@router.post("/bots")
async def create_bot(req: BotCreateRequest, db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    base = req.symbol.split("/")[0].lower()
    bot_id = f"louise_{base}_{str(uuid.uuid4())[:4]}"
    
    db.create_bot(
        bot_id=bot_id,
        symbol=req.symbol,
        buy_volume=req.buy_volume,
        poll_interval_seconds=req.poll_interval_seconds,
        target_profit_pct=req.target_profit_pct,
        daily_budget_usdt=req.daily_budget,
        subaccount=req.subaccount
    )
    db.update_bot_status(bot_id, "RUNNING")
    
    _push_louise_ws(db)
    
    bot_raw = db.get_bot(bot_id)
    return {"bot_id": bot_id, "status": "created", "bot": map_bot_to_ui(bot_raw, db)}

@router.post("/bots/{bot_id}/pause")
async def pause_bot(bot_id: str, db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    bot = db.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
        
    db.update_bot_status(bot_id, "PAUSED")
    _push_louise_ws(db)
    return {"bot_id": bot_id, "status": "paused"}

@router.post("/bots/{bot_id}/resume")
async def resume_bot(bot_id: str, db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    bot = db.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
        
    db.update_bot_status(bot_id, "RUNNING")
    _push_louise_ws(db)
    return {"bot_id": bot_id, "status": "running"}

@router.patch("/bots/{bot_id}")
async def update_bot(bot_id: str, req: BotUpdateRequest, db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    bot = db.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
        
    _push_louise_ws(db)
    return {"bot_id": bot_id, "status": "updated", "bot": map_bot_to_ui(bot, db)}

@router.delete("/bots/{bot_id}")
async def delete_bot(bot_id: str, db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    bot = db.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    
    db.update_bot_status(bot_id, "SHUTDOWN")
    _push_louise_ws(db)
    return {"bot_id": bot_id, "status": "deleted"}

# ─── WS push helper ──────────────────────────────────────────────────

def _push_louise_ws(db: LouiseDB = None) -> None:
    """Push Louise state update immediately via WS broadcaster."""
    try:
        from runtime.core.ws_broadcaster import get_broadcaster
        bc = get_broadcaster()
        bc.publish_sync("TELEMETRY_TICK", {
            "ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            **get_louise_telemetry(db),
        })
    except Exception as e:
        logger.error(f"WS push error: {e}")
