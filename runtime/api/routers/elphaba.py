"""Elphaba hub routes — CRUD, start/stop, logs for Anti-Dorothy bots."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from runtime.api import deps
from runtime.api._helpers import resolve_pair
from runtime.api.schemas import (
    GatewayStartBody,
    HubBotCreateBody,
    HubBotLogsOut,
    HubBotOut,
    HubBotsOut,
)
from runtime.app import AppContext
from runtime.core.security_util import sanitize_log_message

router = APIRouter(prefix="/api/v1/elphaba", tags=["elphaba"])


# ── Hub CRUD ────────────────────────────────────────────────────────

@router.get("/bots", response_model=HubBotsOut)
async def elphaba_bots_list() -> Any:
    return HubBotsOut(bots=[HubBotOut(**row) for row in deps.get_elphaba().list_instances()])


@router.post("/bots", response_model=HubBotOut)
async def elphaba_bots_create(body: HubBotCreateBody) -> Any:
    svc = deps.get_elphaba()
    try:
        row = svc.create_instance(
            bot_id=body.bot_id,
            tag=body.tag,
            symbol=body.symbol,
            loop_interval_sec=body.loop_interval_sec,
            quote_order_qty=body.quote_order_qty,
            profit_factor=body.profit_factor,
            # Elphaba-specific: margin_rise_factor mapped from margin_drop_factor field
            margin_rise_factor=body.margin_drop_factor,
            qty_decimals=body.qty_decimals,
            price_decimals=body.price_decimals,
            note=body.note,
            max_drawdown_pct=body.max_drawdown_pct,
            metrics_interval_cycles=body.metrics_interval_cycles,
            trading_enabled=body.trading_enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=sanitize_log_message(str(e))) from None
    return HubBotOut(**row)


@router.delete("/bots/{bot_id}")
async def elphaba_bots_delete(bot_id: str) -> dict[str, bool]:
    svc = deps.get_elphaba()
    try:
        await svc.delete_instance(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return {"deleted": True}


@router.post("/bots/{bot_id}/start", response_model=HubBotOut)
async def elphaba_bots_start(
    bot_id: str,
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    try:
        row = await deps.get_elphaba().start_instance(bot_id, pair[0], pair[1])
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    except Exception as e:
        raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
    return HubBotOut(**row)


@router.post("/bots/{bot_id}/stop", response_model=HubBotOut)
async def elphaba_bots_stop(bot_id: str) -> Any:
    try:
        row = await deps.get_elphaba().stop_instance(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return HubBotOut(**row)


@router.get("/bots/{bot_id}/logs", response_model=HubBotLogsOut)
async def elphaba_bots_logs(bot_id: str, limit: int = 200) -> Any:
    try:
        rows = deps.get_elphaba().get_logs(bot_id, limit=limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return HubBotLogsOut(logs=rows)
