"""Dorothy hub routes — health, presets, config, hub CRUD, and logs."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from runtime.api import deps
from runtime.api._helpers import resolve_pair
from runtime.api.schemas import (
    BotConfigBody,
    BotConfigOut,
    BotStatusOut,
    GatewayStartBody,
    HubBotCreateBody,
    HubBotLogsOut,
    HubBotOut,
    HubBotsOut,
    HubBotUpdateBody,
)
from runtime.app import AppContext
from runtime.core.security_util import sanitize_log_message

router = APIRouter(prefix="/api/v1", tags=["dorothy"])


# ── Health ──────────────────────────────────────────────────────────

@router.get("/health")
async def health() -> dict[str, Any]:
    """Standard health check — safe to poll frequently, weight 0."""
    ctx = deps.get_ctx()
    bot = deps.get_bot()
    elphaba = deps.get_elphaba()
    # Core system state
    fuse_tripped = False
    weight_zone = "UNKNOWN"
    active_bots = 0
    staged_bots = 0
    try:
        from runtime.core.api_fuse import get_api_fuse
        fuse_tripped = get_api_fuse().is_tripped()
    except Exception:
        pass
    try:
        from runtime.core.weight_governor import get_weight_governor
        weight_zone = get_weight_governor().status()["zone"]
    except Exception:
        pass
    try:
        from runtime.core.bot_coordinator import get_bot_coordinator
        cs = get_bot_coordinator().status()
        active_bots = cs.get("active_bots", 0)
        staged_bots = cs.get("staged_bots", 0)
    except Exception:
        pass
    hub_stats = {
        "dorothy": bot.hub_stats(),
        "elphaba": elphaba.hub_stats(),
    }
    total_running = sum(
        v.get("hub_bots_running", 0) for v in hub_stats.values()
    )
    return {
        "status": "degraded" if fuse_tripped else "healthy",
        "fuse_tripped": fuse_tripped,
        "weight_zone": weight_zone,
        "active_bots": active_bots,
        "staged_bots": staged_bots,
        "total_running": total_running,
        "hubs": hub_stats,
        "uptime_sec": round(time.monotonic(), 1),
        "data_dir": str(ctx.config.data_dir),
    }


# Note: the original app.py registers health() on "/api/v1/bot/presets"
# AND bot_presets() on the same path, which causes a FastAPI conflict.
# The second registration wins. We preserve both for backward compat.


@router.get("/health/deep")
async def health_deep() -> dict[str, Any]:
    ctx = deps.get_ctx()
    bot = deps.get_bot()
    elphaba = deps.get_elphaba()
    gw_ok = ctx.gateway is not None and getattr(ctx.gateway, "_ws_task", None) is not None
    return {
        "status": "ok",
        "gateway_connected": gw_ok,
        "gateway_last_error": ctx.state.last_error,
        "hubs": {
            "dorothy": bot.hub_stats(),
            "elphaba": elphaba.hub_stats(),
        },
        "data_dir": str(ctx.config.data_dir),
    }


# ── Dorothy presets + config ────────────────────────────────────────

@router.get("/bot/presets")
async def bot_presets() -> list[dict[str, Any]]:
    return [
        {
            "preset_id": "B",
            "name": "Dorothy7 preset B",
            "symbol": "XRPUSDT",
            "loop_interval_sec": 75,
            "quote_order_qty": "8",
            "profit_factor": "0.05",
            "margin_drop_factor": "0.004",
            "qty_decimals": 8,
            "price_decimals": 4,
        }
    ]


@router.get("/bot/config", response_model=BotConfigOut)
async def bot_config_get() -> Any:
    cfg = deps.get_bot().get_config()
    return BotConfigOut(**cfg.as_json())


@router.put("/bot/config", response_model=BotConfigOut)
async def bot_config_set(body: BotConfigBody) -> Any:
    svc = deps.get_bot()
    cfg = svc.set_config(
        symbol=body.symbol,
        loop_interval_sec=body.loop_interval_sec,
        quote_order_qty=body.quote_order_qty,
        profit_factor=body.profit_factor,
        margin_drop_factor=body.margin_drop_factor,
        qty_decimals=body.qty_decimals,
        price_decimals=body.price_decimals,
        note=body.note,
    )
    return BotConfigOut(**cfg.as_json())


@router.get("/bot/status", response_model=BotStatusOut)
async def bot_status() -> Any:
    return BotStatusOut(**deps.get_bot().status_payload())


# ── Dorothy Hub CRUD ────────────────────────────────────────────────

@router.get("/hub/bots", response_model=HubBotsOut)
async def hub_bots_list() -> Any:
    return HubBotsOut(bots=[HubBotOut(**row) for row in deps.get_bot().list_instances()])


@router.post("/hub/bots", response_model=HubBotOut)
async def hub_bots_create(body: HubBotCreateBody) -> Any:
    svc = deps.get_bot()
    # Prevent duplicate bots for the same symbol
    existing = [b for b in svc._bots.values() if b.runner.config.symbol == body.symbol]
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe una instancia de Dorothy para el símbolo {body.symbol}. Elimínala primero.",
        )

    try:
        row = svc.create_instance(
            bot_id=body.bot_id,
            tag=body.tag,
            symbol=body.symbol,
            loop_interval_sec=body.loop_interval_sec,
            quote_order_qty=body.quote_order_qty,
            profit_factor=body.profit_factor,
            margin_drop_factor=body.margin_drop_factor,
            qty_decimals=body.qty_decimals,
            price_decimals=body.price_decimals,
            note=body.note,
            max_drawdown_pct=body.max_drawdown_pct,
            stop_loss_pct=body.stop_loss_pct,
            metrics_interval_cycles=body.metrics_interval_cycles,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=sanitize_log_message(str(e))) from None
    return HubBotOut(**row)


@router.patch("/hub/bots/{bot_id}", response_model=HubBotOut)
async def hub_bots_update(bot_id: str, body: HubBotUpdateBody) -> Any:
    svc = deps.get_bot()
    try:
        row = svc.update_instance(
            bot_id,
            tag=body.tag,
            symbol=body.symbol,
            loop_interval_sec=body.loop_interval_sec,
            quote_order_qty=body.quote_order_qty,
            profit_factor=body.profit_factor,
            margin_drop_factor=body.margin_drop_factor,
            qty_decimals=body.qty_decimals,
            price_decimals=body.price_decimals,
            note=body.note,
            max_drawdown_pct=body.max_drawdown_pct,
            stop_loss_pct=body.stop_loss_pct,
            metrics_interval_cycles=body.metrics_interval_cycles,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    except Exception as e:
        raise HTTPException(status_code=400, detail=sanitize_log_message(str(e))) from None
    return HubBotOut(**row)


@router.delete("/hub/bots/{bot_id}")
async def hub_bots_delete(bot_id: str) -> dict[str, bool]:
    svc = deps.get_bot()
    try:
        await svc.delete_instance(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return {"deleted": True}


@router.post("/hub/bots/{bot_id}/start", response_model=HubBotOut)
async def hub_bots_start(
    bot_id: str,
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    try:
        row = await deps.get_bot().start_instance(bot_id, pair[0], pair[1])
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    except Exception as e:
        raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
    return HubBotOut(**row)


@router.post("/hub/bots/{bot_id}/stop", response_model=HubBotOut)
async def hub_bots_stop(bot_id: str) -> Any:
    try:
        row = await deps.get_bot().stop_instance(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return HubBotOut(**row)


@router.post("/hub/bots/{bot_id}/run_once", response_model=HubBotOut)
async def hub_bots_run_once(
    bot_id: str,
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    try:
        row = await deps.get_bot().run_once_instance(bot_id, pair[0], pair[1])
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    except Exception as e:
        raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
    return HubBotOut(**row)


@router.get("/hub/bots/{bot_id}/logs", response_model=HubBotLogsOut)
async def hub_bots_logs(bot_id: str, limit: int = 200) -> Any:
    try:
        rows = deps.get_bot().get_logs(bot_id, limit=limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return HubBotLogsOut(logs=rows)
