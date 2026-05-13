"""Louise Bot Hub API Router — state, control, and telemetry endpoints."""

from __future__ import annotations

import datetime as dt
import uuid
import os
import logging
from typing import Any

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

    from runtime.core.market_cache import get_market_cache

    current_price = 0.0
    symbol = bot["symbol"]
    ticker = get_market_cache().get_ticker(symbol)
    if ticker:
        current_price = float(ticker.last_price)

    position_size = 0.0
    cost_basis = 0.0
    unrealized_pnl = 0.0
    unrealized_pct = 0.0
    trades_today = 0
    progress_percent = 0.0

    if active_epoch:
        cost_basis = active_epoch["total_cost"]
        avg_buy_price = active_epoch["avg_buy_price"]
        position_size = cost_basis / avg_buy_price if avg_buy_price > 0 else 0
        trades_today = active_epoch["num_purchases"]

        if current_price > 0 and cost_basis > 0:
            current_value = position_size * current_price
            unrealized_pnl = current_value - cost_basis
            unrealized_pct = (unrealized_pnl / cost_basis) * 100.0
            target = bot.get("target_profit_pct", 5.0)
            if target > 0:
                progress_percent = (unrealized_pct / target) * 100.0

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
        "progress_percent": progress_percent,
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
        "completed_epochs": db.get_completed_epochs_count(),
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
    max_position_size_usdt: float = 5000.0
    max_purchases_per_epoch: int = 20
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
        return {
            "error": "api_governor_unavailable",
            "message": "Failed to load API governor settings",
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

    weight = None
    try:
        from runtime.api import deps
        ctx = deps.get_ctx()
        weight = getattr(getattr(ctx, "state", None), "api_weight_used_1m", None)
    except Exception:
        pass

    if weight is None:
        return {
            "error": "governor_state_unavailable",
            "message": "API governor state not available (context not loaded)",
            "weight_limit": limit,
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        }

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
async def get_weight_history() -> dict[str, Any]:
    try:
        from runtime.core.telemetry_vault import get_telemetry_vault
        vault = get_telemetry_vault()
        snapshots = vault.get_weight_snapshots()
        if snapshots:
            return {
                "ready": True,
                "data": snapshots,
                "message": f"{len(snapshots)} snapshots available",
            }
        else:
            return {
                "ready": False,
                "data": [],
                "message": "No weight history snapshots recorded yet",
            }
    except Exception as e:
        logger.warning(f"Failed to fetch weight history: {e}")
        return {
            "ready": False,
            "data": [],
            "error": str(e),
            "message": "Could not load weight history from vault",
        }

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
    paused = sum(1 for b in bots if b["status"] == "PAUSED")

    # Determine real health status
    if len(bots) == 0:
        status = "healthy"
    elif active == 0 and paused == len(bots):
        status = "healthy"  # All paused is OK
    elif active > 0:
        status = "healthy"  # Active bots = running
    else:
        status = "unknown"

    # Get actual weight zone (not hardcoded)
    weight_zone = "UNKNOWN"
    try:
        weight_response = await get_weight_status()
        if "error" not in weight_response:
            weight_zone = weight_response.get("weight_zone", "UNKNOWN")
    except Exception:
        pass

    return {
        "status": status,
        "active_bots": active,
        "paused_bots": paused,
        "total_bots": len(bots),
        "weight_zone": weight_zone,
        "last_check": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

# ─── Control endpoints ────────────────────────────────────────────────

@router.post("/bots")
async def create_bot(req: BotCreateRequest, db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    from runtime.api import deps
    from runtime.api._helpers import resolve_pair_for_bot
    from runtime.core.exchange_filters import get_exchange_filters

    # Validate request parameters
    if req.daily_budget <= 0:
        raise HTTPException(status_code=400, detail="daily_budget must be > 0")
    if req.target_profit_pct == 0:
        raise HTTPException(status_code=400, detail="target_profit_pct cannot be 0")
    if req.target_profit_pct < -50 or req.target_profit_pct > 100:
        raise HTTPException(status_code=400, detail="target_profit_pct must be between -50% and 100%")
    if req.buy_volume <= 0:
        raise HTTPException(status_code=400, detail="buy_volume must be > 0")
    if req.poll_interval_seconds < 10:
        raise HTTPException(status_code=400, detail="poll_interval_seconds must be >= 10")
    if req.max_position_size_usdt <= 0:
        raise HTTPException(status_code=400, detail="max_position_size_usdt must be > 0")
    if req.max_purchases_per_epoch <= 0:
        raise HTTPException(status_code=400, detail="max_purchases_per_epoch must be > 0")

    # Validate symbol exists in exchange filters
    filters = get_exchange_filters().get(req.symbol)
    if not filters:
        raise HTTPException(status_code=400, detail=f"Symbol {req.symbol} not found in exchange filters")

    # Validate credentials exist (unless paper trading)
    ctx = deps.get_ctx()
    pair = resolve_pair_for_bot(ctx, req.subaccount)
    if not pair and os.environ.get("LOUISE_PAPER_TRADE", "true").lower() != "true":
        raise HTTPException(status_code=400, detail=f"No credentials found for subaccount {req.subaccount}")

    base = req.symbol.split("/")[0].lower()
    bot_id = f"louise_{base}_{str(uuid.uuid4())[:4]}"

    # Create bot in PAUSED state initially
    db.create_bot(
        bot_id=bot_id,
        symbol=req.symbol,
        buy_volume=req.buy_volume,
        poll_interval_seconds=req.poll_interval_seconds,
        target_profit_pct=req.target_profit_pct,
        daily_budget_usdt=req.daily_budget,
        max_position_size_usdt=req.max_position_size_usdt,
        max_purchases_per_epoch=req.max_purchases_per_epoch,
        subaccount=req.subaccount
    )
    db.update_bot_status(bot_id, "PAUSED")

    # Try to initialize bot to validate config loads correctly
    try:
        from runtime.bot.louise import LouiseBotRunner
        from runtime.core.event_bus import get_event_bus

        bot_runner = LouiseBotRunner(bot_id, db, get_event_bus(), None)
        if not bot_runner.initialize():
            raise RuntimeError("Bot initialization failed")

        # Only now transition to RUNNING after successful init
        db.update_bot_status(bot_id, "RUNNING")
        logger.info(f"Bot {bot_id} created and validated, status=RUNNING")
    except Exception as e:
        logger.error(f"Bot {bot_id} initialization failed: {e}")
        db.update_bot_status(bot_id, "ERROR")
        raise HTTPException(status_code=400, detail=f"Bot initialization failed: {e}")

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
    from runtime.core.exchange_filters import get_exchange_filters

    bot = db.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    # Validate new values before updating
    new_budget = req.daily_budget if req.daily_budget is not None else bot.get("daily_budget_usdt", 500.0)
    new_target = req.target_profit_pct if req.target_profit_pct is not None else bot.get("target_profit_pct", 5.0)
    new_symbol = req.symbol if req.symbol is not None else bot.get("symbol")

    if new_budget is not None and new_budget <= 0:
        raise HTTPException(status_code=400, detail="daily_budget must be > 0")
    if new_target is not None and new_target == 0:
        raise HTTPException(status_code=400, detail="target_profit_pct cannot be 0")
    if new_target is not None and (new_target < -50 or new_target > 100):
        raise HTTPException(status_code=400, detail="target_profit_pct must be between -50% and 100%")
    if new_symbol is not None and new_symbol != bot.get("symbol"):
        filters = get_exchange_filters().get(new_symbol)
        if not filters:
            raise HTTPException(status_code=400, detail=f"Symbol {new_symbol} not found in exchange filters")

    # Warn if bot is running and config changes
    if bot.get("status") == "RUNNING":
        logger.warning(f"Bot {bot_id} config updated while RUNNING: budget {new_budget}, target {new_target}")

    db.update_bot_config(bot_id, new_budget, new_target)

    # Reload bot
    bot = db.get_bot(bot_id)
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
