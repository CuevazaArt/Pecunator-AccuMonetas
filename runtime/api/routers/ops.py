"""Operations protocol routes — red button, close, order cleanup."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from runtime.api import deps
from runtime.app import AppContext
from runtime.core.ops_audit_log import get_ops_audit_log

router = APIRouter(prefix="/api/v1", tags=["ops"])


@router.get("/ops/protocol/status")
async def ops_protocol_status(ctx: AppContext = Depends(deps.get_ctx)) -> dict[str, Any]:
    audit = get_ops_audit_log(ctx.config.data_dir)
    return {
        "close_protocol": audit.last("close_protocol"),
        "red_button": audit.last("red_button"),
        "cancel_limit_orders_cleanup": audit.last("cancel_limit_orders_cleanup"),
        "cancel_stop_orders_cleanup": audit.last("cancel_stop_orders_cleanup"),
        "cancel_all_orders_cleanup": audit.last("cancel_all_orders_cleanup"),
        "hub_stats": deps.get_bot().hub_stats(),
    }


@router.post("/ops/protocol/close")
async def ops_protocol_close(
    base_asset: str = "USDT",
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    # Import the heavy helper lazily to avoid circular deps
    from runtime.api.app import _execute_close_protocol
    summary = await _execute_close_protocol(ctx, base_asset=base_asset)
    rec = get_ops_audit_log(ctx.config.data_dir).record(
        op_name="close_protocol",
        status=str(summary.get("status", "unknown")),
        summary=summary,
        error=str(summary.get("error", "")).strip() or None,
    )
    return {"record": rec, "summary": summary}


@router.post("/ops/red_button")
async def ops_red_button(
    base_asset: str = "USDT",
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.api.app import _execute_red_button
    summary = await _execute_red_button(ctx, base_asset=base_asset)
    rec = get_ops_audit_log(ctx.config.data_dir).record(
        op_name="red_button",
        status=str(summary.get("status", "unknown")),
        summary=summary,
        error=str(summary.get("error", "")).strip() or None,
    )
    return {"record": rec, "summary": summary}


@router.post("/ops/orders/cleanup/limit")
async def ops_cleanup_limit_orders(
    base_asset: str = "USDT",
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.api.app import _execute_order_cleanup
    summary = await _execute_order_cleanup(ctx, base_asset=base_asset, mode="limit")
    rec = get_ops_audit_log(ctx.config.data_dir).record(
        op_name="cancel_limit_orders_cleanup",
        status=str(summary.get("status", "unknown")),
        summary=summary,
        error=str(summary.get("error", "")).strip() or None,
    )
    return {"record": rec, "summary": summary}


@router.post("/ops/orders/cleanup/stop")
async def ops_cleanup_stop_orders(
    base_asset: str = "USDT",
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.api.app import _execute_order_cleanup
    summary = await _execute_order_cleanup(ctx, base_asset=base_asset, mode="stop")
    rec = get_ops_audit_log(ctx.config.data_dir).record(
        op_name="cancel_stop_orders_cleanup",
        status=str(summary.get("status", "unknown")),
        summary=summary,
        error=str(summary.get("error", "")).strip() or None,
    )
    return {"record": rec, "summary": summary}


@router.post("/ops/orders/cleanup/all")
async def ops_cleanup_all_orders(
    base_asset: str = "USDT",
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.api.app import _execute_order_cleanup
    summary = await _execute_order_cleanup(ctx, base_asset=base_asset, mode="all")
    rec = get_ops_audit_log(ctx.config.data_dir).record(
        op_name="cancel_all_orders_cleanup",
        status=str(summary.get("status", "unknown")),
        summary=summary,
        error=str(summary.get("error", "")).strip() or None,
    )
    return {"record": rec, "summary": summary}
