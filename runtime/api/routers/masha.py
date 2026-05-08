"""Masha hub bot CRUD router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from runtime.api import deps
from runtime.api._helpers import resolve_pair
from runtime.api.schemas import (
    GatewayStartBody,
    MashaBotCreateBody,
    MashaBotLogsOut,
    MashaBotOut,
    MashaBotsOut,
    MashaBotUpdateBody,
)
from runtime.app import AppContext
from runtime.core.security_util import sanitize_log_message

router = APIRouter(prefix="/api/v1/masha", tags=["masha"])


@router.get("/bots", response_model=MashaBotsOut)
async def masha_bots_list() -> Any:
    return MashaBotsOut(bots=[MashaBotOut(**row) for row in deps.get_masha().list_instances()])


@router.post("/bots", response_model=MashaBotOut)
async def masha_bots_create(body: MashaBotCreateBody) -> Any:
    svc = deps.get_masha()
    try:
        row = svc.create_instance(
            bot_id=body.bot_id,
            tag=body.tag,
            symbols_csv=body.symbols_csv,
            loop_interval_sec=body.loop_interval_sec,
            quote_min_free_to_operate=body.quote_min_free_to_operate,
            buy_qty_base=body.buy_qty_base,
            profit_factor=body.profit_factor,
            timeframe_w=body.timeframe_w,
            periods_w=body.periods_w,
            mm_periods_w=body.mm_periods_w,
            margin_low_w=body.margin_low_w,
            timeframe_h=body.timeframe_h,
            periods_h=body.periods_h,
            mm_periods_h=body.mm_periods_h,
            margin_low_h=body.margin_low_h,
            note=body.note,
            max_drawdown_pct=body.max_drawdown_pct,
            stop_loss_pct=body.stop_loss_pct,
            metrics_interval_cycles=body.metrics_interval_cycles,
            simulated=body.simulated,
            trading_enabled=body.trading_enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=sanitize_log_message(str(e))) from None
    return MashaBotOut(**row)


@router.patch("/bots/{bot_id}", response_model=MashaBotOut)
async def masha_bots_update(bot_id: str, body: MashaBotUpdateBody) -> Any:
    svc = deps.get_masha()
    try:
        row = svc.update_instance(
            bot_id,
            tag=body.tag,
            symbols_csv=body.symbols_csv,
            loop_interval_sec=body.loop_interval_sec,
            quote_min_free_to_operate=body.quote_min_free_to_operate,
            buy_qty_base=body.buy_qty_base,
            profit_factor=body.profit_factor,
            timeframe_w=body.timeframe_w,
            periods_w=body.periods_w,
            mm_periods_w=body.mm_periods_w,
            margin_low_w=body.margin_low_w,
            timeframe_h=body.timeframe_h,
            periods_h=body.periods_h,
            mm_periods_h=body.mm_periods_h,
            margin_low_h=body.margin_low_h,
            note=body.note,
            max_drawdown_pct=body.max_drawdown_pct,
            stop_loss_pct=body.stop_loss_pct,
            metrics_interval_cycles=body.metrics_interval_cycles,
            simulated=body.simulated,
            trading_enabled=body.trading_enabled,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    except Exception as e:
        raise HTTPException(status_code=400, detail=sanitize_log_message(str(e))) from None
    return MashaBotOut(**row)


@router.delete("/bots/{bot_id}")
async def masha_bots_delete(bot_id: str) -> dict[str, bool]:
    svc = deps.get_masha()
    try:
        await svc.delete_instance(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return {"deleted": True}


@router.post("/bots/{bot_id}/start", response_model=MashaBotOut)
async def masha_bots_start(
    bot_id: str,
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    try:
        row = await deps.get_masha().start_instance(bot_id, pair[0], pair[1])
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    except Exception as e:
        raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
    return MashaBotOut(**row)


@router.post("/bots/{bot_id}/stop", response_model=MashaBotOut)
async def masha_bots_stop(bot_id: str) -> Any:
    try:
        row = await deps.get_masha().stop_instance(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return MashaBotOut(**row)


@router.post("/bots/{bot_id}/run_once", response_model=MashaBotOut)
async def masha_bots_run_once(
    bot_id: str,
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    try:
        row = await deps.get_masha().run_once_instance(bot_id, pair[0], pair[1])
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    except Exception as e:
        raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
    return MashaBotOut(**row)


@router.get("/bots/{bot_id}/logs", response_model=MashaBotLogsOut)
async def masha_bots_logs(bot_id: str, limit: int = 200) -> Any:
    try:
        rows = deps.get_masha().get_logs(bot_id, limit=limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return MashaBotLogsOut(logs=rows)
