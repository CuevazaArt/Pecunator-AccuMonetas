"""Thusnelda hub bot CRUD router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from runtime.api import deps
from runtime.api._helpers import resolve_pair
from runtime.api.schemas import (
    GatewayStartBody,
    ThusneldaBotCreateBody,
    ThusneldaBotLogsOut,
    ThusneldaBotOut,
    ThusneldaBotsOut,
    ThusneldaBotUpdateBody,
)
from runtime.app import AppContext
from runtime.core.security_util import sanitize_log_message

router = APIRouter(prefix="/api/v1/thusnelda", tags=["thusnelda"])


@router.get("/bots", response_model=ThusneldaBotsOut)
async def thusnelda_bots_list() -> Any:
    svc = deps.get_thusnelda()
    bots = svc.list_instances()
    return ThusneldaBotsOut(bots=[ThusneldaBotOut(**row) for row in bots])


@router.post("/bots", response_model=ThusneldaBotOut)
async def thusnelda_bots_create(body: ThusneldaBotCreateBody) -> Any:
    svc = deps.get_thusnelda()
    try:
        row = svc.create_instance(
            bot_id=body.bot_id,
            tag=body.tag,
            symbols_csv=body.symbols_csv,
            loop_interval_sec=body.loop_interval_sec,
            between_symbol_sec=body.between_symbol_sec,
            quote_order_qty_modulo=body.quote_order_qty_modulo,
            factor_multiplication=body.factor_multiplication,
            profit_target_pct=body.profit_target_pct,
            meta_equity_usdt=body.meta_equity_usdt,
            reference_ts_iso=body.reference_ts_iso,
            qty_decimals=body.qty_decimals,
            price_decimals=body.price_decimals,
            note=body.note,
            max_drawdown_pct=body.max_drawdown_pct,
            stop_loss_pct=body.stop_loss_pct,
            metrics_interval_cycles=body.metrics_interval_cycles,
            simulated=body.simulated,
            trading_enabled=body.trading_enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=sanitize_log_message(str(e))) from None
    return ThusneldaBotOut(**row)


@router.patch("/bots/{bot_id}", response_model=ThusneldaBotOut)
async def thusnelda_bots_update(bot_id: str, body: ThusneldaBotUpdateBody) -> Any:
    svc = deps.get_thusnelda()
    try:
        row = svc.update_instance(
            bot_id,
            tag=body.tag,
            symbols_csv=body.symbols_csv,
            loop_interval_sec=body.loop_interval_sec,
            between_symbol_sec=body.between_symbol_sec,
            quote_order_qty_modulo=body.quote_order_qty_modulo,
            factor_multiplication=body.factor_multiplication,
            profit_target_pct=body.profit_target_pct,
            meta_equity_usdt=body.meta_equity_usdt,
            reference_ts_iso=body.reference_ts_iso,
            qty_decimals=body.qty_decimals,
            price_decimals=body.price_decimals,
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
    return ThusneldaBotOut(**row)


@router.delete("/bots/{bot_id}")
async def thusnelda_bots_delete(bot_id: str) -> dict[str, bool]:
    svc = deps.get_thusnelda()
    try:
        await svc.delete_instance(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return {"deleted": True}


@router.post("/bots/{bot_id}/start", response_model=ThusneldaBotOut)
async def thusnelda_bots_start(
    bot_id: str,
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    try:
        row = await deps.get_thusnelda().start_instance(bot_id, pair[0], pair[1])
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    except Exception as e:
        raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
    return ThusneldaBotOut(**row)


@router.post("/bots/{bot_id}/stop", response_model=ThusneldaBotOut)
async def thusnelda_bots_stop(bot_id: str) -> Any:
    try:
        row = await deps.get_thusnelda().stop_instance(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return ThusneldaBotOut(**row)


@router.post("/bots/{bot_id}/run_once", response_model=ThusneldaBotOut)
async def thusnelda_bots_run_once(
    bot_id: str,
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    try:
        row = await deps.get_thusnelda().run_once_instance(bot_id, pair[0], pair[1])
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    except Exception as e:
        raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
    return ThusneldaBotOut(**row)


@router.get("/bots/{bot_id}/logs", response_model=ThusneldaBotLogsOut)
async def thusnelda_bots_logs(bot_id: str, limit: int = 200) -> Any:
    try:
        rows = deps.get_thusnelda().get_logs(bot_id, limit=limit)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found") from None
    return ThusneldaBotLogsOut(logs=rows)
