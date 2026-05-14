"""Louise Bot Hub API Router — state, control, and telemetry endpoints."""

from __future__ import annotations

import datetime as dt
import uuid
import os
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from runtime.core.louise_db import LouiseDB
from runtime.core.settings import (
    louise_default_subaccount,
    louise_default_max_position_size_usdt,
    louise_default_max_purchases_per_epoch,
)

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
    has_price = False
    symbol = bot["symbol"]
    try:
        ticker = get_market_cache().get_ticker(symbol)
        if ticker is not None:
            current_price = float(ticker.last_price)
            has_price = True
    except (AttributeError, ValueError, TypeError) as e:
        logger.debug(f"Ticker lookup failed for {symbol}: {e}")

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
        "price_available": has_price,
        "position_size": position_size,
        "cost_basis": cost_basis,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pct": unrealized_pct,
        "free_balance": bot["daily_budget_usdt"],
        "target_profit_pct": bot["target_profit_pct"],
        "buy_volume": bot.get("buy_volume", 10.0),
        "max_position_size_usdt": bot.get("max_position_size_usdt", 5000.0),
        "max_purchases_per_epoch": bot.get("max_purchases_per_epoch", 20),
        "progress_percent": progress_percent,
        "daily_budget": bot["daily_budget_usdt"],
        "trades_today": trades_today,
        "subaccount": bot.get("subaccount", "bluechip"),
        "louise_enabled": bool(bot.get("louise_enabled", 1)),
        "anti_louise_enabled": bool(bot.get("anti_louise_enabled", 0)),
        "paired_bot_id": bot.get("paired_bot_id"),
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

def _default_max_position() -> float:
    return louise_default_max_position_size_usdt()


def _default_max_purchases() -> int:
    return louise_default_max_purchases_per_epoch()


def _default_subaccount() -> str:
    return louise_default_subaccount()


class BotCreateRequest(BaseModel):
    """Bot creation payload.

    Note on L0 doctrine: ``max_position_size_usdt`` and ``max_purchases_per_epoch``
    are stored on the bot record for informational/dashboard purposes but are
    NOT enforced by the runner. Under the L0 dual-hub doctrine, drawdown on one
    side is profit on the other — capping one side asymmetrically would break
    the hedge. The runner is gated only by ``daily_budget`` and the global
    ``BudgetGuard``. These fields are kept for backwards compatibility and may
    be removed once UI is fully migrated.
    """
    symbol: str
    daily_budget: float = 500.0
    target_profit_pct: float = 5.0
    buy_volume: float = 10.0
    poll_interval_seconds: int = 60
    max_position_size_usdt: float = Field(default_factory=_default_max_position)
    max_purchases_per_epoch: int = Field(default_factory=_default_max_purchases)
    subaccount: str = Field(default_factory=_default_subaccount)

class BotUpdateRequest(BaseModel):
    """Bot config update payload.

    See ``BotCreateRequest`` for the L0-doctrine note on ``max_position_size_usdt``
    and ``max_purchases_per_epoch`` — these are informational only at the runner
    level, but validation is preserved so dashboards/UI stay coherent.
    """
    daily_budget: float | None = None
    target_profit_pct: float | None = None
    symbol: str | None = None
    buy_volume: float | None = None
    poll_interval_seconds: int | None = None
    max_position_size_usdt: float | None = None
    max_purchases_per_epoch: int | None = None

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
    """Per-bot request counts derived from real OrderLedger entries (not synthetic).

    Returns:
        {bot_id: request_count, ..., "total": total, "source": "order_ledger"}
        Or {"error": "...", "ready": False} if telemetry source unavailable.
    """
    try:
        from runtime.core.order_ledger import get_order_ledger
        ledger = get_order_ledger()
        bots = db.get_all_bots()
        counts: dict[str, Any] = {}
        total = 0
        for b in bots:
            bot_id = b["bot_id"]
            try:
                stats = ledger.stats_for_bot(bot_id) if hasattr(ledger, "stats_for_bot") else {}
                n = int(stats.get("orders_today", 0) or 0)
            except Exception:
                n = 0
            counts[bot_id] = n
            total += n
        return {**counts, "total": total, "source": "order_ledger"}
    except Exception as e:
        logger.warning(f"requests telemetry unavailable: {e}")
        return {"total": 0, "ready": False, "error": str(e)}


@router.get("/telemetry/bandwidth")
async def get_bandwidth_stats(db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    """Network bandwidth metric.

    Not currently tracked at the bot level — exposed as 'not_implemented'
    so the UI shows a placeholder instead of fabricated numbers.
    """
    return {
        "total": 0,
        "ready": False,
        "message": "bandwidth tracking not implemented",
        "status": "not_implemented",
    }

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

    # Create bot in PAUSED state initially (single DB operation)
    db.create_bot(
        bot_id=bot_id,
        symbol=req.symbol,
        buy_volume=req.buy_volume,
        poll_interval_seconds=req.poll_interval_seconds,
        target_profit_pct=req.target_profit_pct,
        daily_budget_usdt=req.daily_budget,
        max_position_size_usdt=req.max_position_size_usdt,
        max_purchases_per_epoch=req.max_purchases_per_epoch,
        subaccount=req.subaccount,
        status="PAUSED"
    )

    # Validate that the runner can initialize against this config + DB row.
    # We use the ctx bus when available (production) or create a fresh EventBus (tests).
    # Pass subscribe=False to avoid registering event bus callbacks on this temporary runner.
    try:
        from runtime.bot.louise import LouiseBotRunner
        from runtime.core.event_bus import EventBus

        bus = getattr(ctx, "bus", None) or EventBus()
        bot_runner = LouiseBotRunner(bot_id, db, bus, None)
        if not bot_runner.initialize(subscribe=False):
            raise RuntimeError("Bot initialization failed (config could not be loaded)")

        # Only now transition to RUNNING after successful init.
        # The louise immortality loop will pick it up within ~10s and start the runner.
        db.update_bot_status(bot_id, "RUNNING")
        logger.info(f"Bot {bot_id} created and validated, status=RUNNING")
    except HTTPException:
        raise
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

    # Validate each provided field
    if req.daily_budget is not None and req.daily_budget <= 0:
        raise HTTPException(status_code=400, detail="daily_budget must be > 0")
    if req.target_profit_pct is not None:
        if req.target_profit_pct == 0:
            raise HTTPException(status_code=400, detail="target_profit_pct cannot be 0")
        if req.target_profit_pct < -50 or req.target_profit_pct > 100:
            raise HTTPException(status_code=400, detail="target_profit_pct must be between -50% and 100%")
    if req.buy_volume is not None and req.buy_volume <= 0:
        raise HTTPException(status_code=400, detail="buy_volume must be > 0")
    if req.poll_interval_seconds is not None and req.poll_interval_seconds < 10:
        raise HTTPException(status_code=400, detail="poll_interval_seconds must be >= 10")
    if req.max_position_size_usdt is not None and req.max_position_size_usdt <= 0:
        raise HTTPException(status_code=400, detail="max_position_size_usdt must be > 0")
    if req.max_purchases_per_epoch is not None and req.max_purchases_per_epoch <= 0:
        raise HTTPException(status_code=400, detail="max_purchases_per_epoch must be > 0")
    if req.symbol is not None and req.symbol != bot.get("symbol"):
        filters = get_exchange_filters().get(req.symbol)
        if not filters:
            raise HTTPException(status_code=400, detail=f"Symbol {req.symbol} not found in exchange filters")

    # Warn if bot is running and config changes
    if bot.get("status") == "RUNNING":
        logger.warning(f"Bot {bot_id} config updated while RUNNING")

    db.update_bot_config(
        bot_id,
        daily_budget_usdt=req.daily_budget,
        target_profit_pct=req.target_profit_pct,
        symbol=req.symbol,
        buy_volume=req.buy_volume,
        poll_interval_seconds=req.poll_interval_seconds,
        max_position_size_usdt=req.max_position_size_usdt,
        max_purchases_per_epoch=req.max_purchases_per_epoch,
    )

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


# ─── Hemisphere switch endpoints ──────────────────────────────────────

class HemisphereUpdateRequest(BaseModel):
    louise_enabled: bool | None = None
    anti_louise_enabled: bool | None = None


@router.get("/bots/{bot_id}/hemispheres")
async def get_hemispheres(bot_id: str, db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    """Return the current hemisphere enable/disable state for a bot."""
    bot = db.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    return {
        "bot_id": bot_id,
        "louise_enabled": bool(bot.get("louise_enabled", 1)),
        "anti_louise_enabled": bool(bot.get("anti_louise_enabled", 0)),
        "paired_bot_id": bot.get("paired_bot_id"),
    }


@router.patch("/bots/{bot_id}/hemispheres")
async def update_hemispheres(
    bot_id: str, req: HemisphereUpdateRequest, db: LouiseDB = Depends(get_db)
) -> dict[str, Any]:
    """Enable or disable Louise/AntiLouise hemispheres independently.

    Setting ``louise_enabled=false`` stops the LONG DCA side.
    Setting ``anti_louise_enabled=true`` activates the SHORT DCA side.
    Changes take effect within the next immortality loop tick (~10s).
    """
    bot = db.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    if req.louise_enabled is None and req.anti_louise_enabled is None:
        raise HTTPException(status_code=400, detail="Provide at least one of louise_enabled or anti_louise_enabled")

    db.update_bot_hemispheres(
        bot_id,
        louise_enabled=req.louise_enabled,
        anti_louise_enabled=req.anti_louise_enabled,
    )

    # If disabling a hemisphere while RUNNING, set to PAUSED so immortality stops it
    updated = db.get_bot(bot_id)
    if updated and updated.get("status") in ("RUNNING", "ACCUMULATING"):
        bot_type = updated.get("bot_type", "louise")
        if bot_type == "louise" and req.louise_enabled is False:
            db.update_bot_status(bot_id, "PAUSED")
            logger.info(f"Bot {bot_id}: Louise hemisphere disabled → PAUSED")
        elif bot_type == "anti_louise" and req.anti_louise_enabled is False:
            db.update_bot_status(bot_id, "PAUSED")
            logger.info(f"Bot {bot_id}: AntiLouise hemisphere disabled → PAUSED")

    _push_louise_ws(db)
    updated = db.get_bot(bot_id)
    return {
        "bot_id": bot_id,
        "status": "updated",
        "louise_enabled": bool(updated.get("louise_enabled", 1)),
        "anti_louise_enabled": bool(updated.get("anti_louise_enabled", 0)),
    }


@router.patch("/bots/{bot_id}/pair")
async def pair_bots(
    bot_id: str,
    db: LouiseDB = Depends(get_db),
    pair_with_bot_id: str | None = None,
) -> dict[str, Any]:
    """Link a Louise bot with its AntiLouise counterpart (or clear the link)."""
    if not db.get_bot(bot_id):
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    if pair_with_bot_id and not db.get_bot(pair_with_bot_id):
        raise HTTPException(status_code=404, detail=f"Pair target {pair_with_bot_id} not found")

    db.update_bot_pair(bot_id, pair_with_bot_id)
    if pair_with_bot_id:
        db.update_bot_pair(pair_with_bot_id, bot_id)

    return {"bot_id": bot_id, "paired_with": pair_with_bot_id}


# ─── Console/Telemetry endpoints ─────────────────────────────────────

@router.get("/bots/{bot_id}/pnl-history")
async def get_bot_pnl_history(
    bot_id: str,
    since: int | None = None,
    limit: int = 2000,
    db: LouiseDB = Depends(get_db),
) -> dict[str, Any]:
    """Time-series of P&L snapshots for charting (oldest first)."""
    if not db.get_bot(bot_id):
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    snapshots = db.get_pnl_history(bot_id, since=since, limit=limit)
    return {"bot_id": bot_id, "snapshots": snapshots, "count": len(snapshots)}


@router.get("/bots/{bot_id}/purchases")
async def get_bot_purchases(
    bot_id: str,
    since: int | None = None,
    limit: int = 1000,
    db: LouiseDB = Depends(get_db),
) -> dict[str, Any]:
    """Every entry point (BUY/SHORT) made by a bot, oldest first.
    Used to overlay buys on the price chart."""
    if not db.get_bot(bot_id):
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    purchases = db.get_purchases_by_bot(bot_id, since=since, limit=limit)
    return {"bot_id": bot_id, "purchases": purchases, "count": len(purchases)}


@router.get("/hub/combined-pnl")
async def get_hub_combined_pnl(
    since: int | None = None,
    limit: int = 4000,
    db: LouiseDB = Depends(get_db),
) -> dict[str, Any]:
    """P&L snapshots across ALL bots in the hub, grouped per bot."""
    all_snapshots = db.get_combined_pnl_history(since=since, limit=limit)
    by_bot: dict[str, list[dict[str, Any]]] = {}
    for s in all_snapshots:
        by_bot.setdefault(s["bot_id"], []).append(s)

    # Aggregate latest per-bot for totals
    realized_sum = 0.0
    unrealized_sum = 0.0
    for bot_id, series in by_bot.items():
        if not series:
            continue
        latest = series[-1]
        realized_sum += float(latest.get("cumulative_realized_pnl_usdt") or 0.0)
        unrealized_sum += float(latest.get("unrealized_pnl_usdt") or 0.0)

    return {
        "snapshots": all_snapshots,
        "by_bot_id": by_bot,
        "totals": {
            "cumulative_realized_pnl_usdt": realized_sum,
            "unrealized_pnl_usdt": unrealized_sum,
            "net_position_usdt": realized_sum + unrealized_sum,
        },
        "count": len(all_snapshots),
    }


@router.get("/hub/dual-state")
async def get_hub_dual_state(db: LouiseDB = Depends(get_db)) -> dict[str, Any]:
    """Snapshot of all bots' current state for the console header.
    Pulls from louise_bots (config), latest pnl_snapshots (P&L), and the in-memory
    LouiseService.runners dict for `last_purchase_price` / `last_short_price`."""
    from runtime.api.louise_service import get_louise_service
    svc = get_louise_service()
    bots_data: list[dict[str, Any]] = []
    realized_sum = 0.0
    unrealized_sum = 0.0

    for bot in db.get_all_bots():
        bot_id = bot["bot_id"]
        latest = db.get_latest_pnl_snapshot(bot_id) or {}
        epoch = db.get_active_epoch(bot_id)
        runner = svc.runners.get(bot_id)

        runtime_last_entry = None
        runtime_current_price = None
        if runner is not None:
            # Louise has last_purchase_price; AntiLouise has last_short_price
            runtime_last_entry = float(
                getattr(runner, "last_purchase_price", None)
                or getattr(runner, "last_short_price", 0)
            )
            runtime_current_price = float(getattr(runner, "current_price", 0))

        realized_sum += float(latest.get("cumulative_realized_pnl_usdt") or 0.0)
        unrealized_sum += float(latest.get("unrealized_pnl_usdt") or 0.0)

        bots_data.append({
            "bot_id": bot_id,
            "bot_type": bot.get("bot_type", "louise"),
            "symbol": bot["symbol"],
            "subaccount": bot.get("subaccount", "bluechip"),
            "status": bot["status"],
            "buy_volume": bot["buy_volume"],
            "target_profit_pct": bot["target_profit_pct"],
            "active_epoch": epoch,
            "last_entry_price": runtime_last_entry,
            "current_price": runtime_current_price,
            "latest_snapshot": latest,
        })

    return {
        "ts_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "bots": bots_data,
        "totals": {
            "cumulative_realized_pnl_usdt": realized_sum,
            "unrealized_pnl_usdt": unrealized_sum,
            "net_position_usdt": realized_sum + unrealized_sum,
        },
    }


@router.get("/klines/{symbol}")
async def get_klines_with_ha(
    symbol: str,
    interval: str = "1d",
    limit: int = 500,
) -> dict[str, Any]:
    """OHLC + Heikin-Ashi candles from kline_history (newest first).

    Returns both raw OHLC and HA-derived values. The HA values are stored
    pre-computed in the same row → operator sees identical HA construction
    as TradingView/source charts (recursive chain preserved on every ingest)."""
    from runtime.core.telemetry_vault import get_telemetry_vault
    from runtime.api import deps as _deps
    ctx = _deps.peek_ctx()
    data_dir = ctx.config.data_dir if ctx is not None else None
    vault = get_telemetry_vault(data_dir)
    rows = vault.get_klines(symbol.upper(), interval, limit=limit)
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "candles": rows,
        "count": len(rows),
    }


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
