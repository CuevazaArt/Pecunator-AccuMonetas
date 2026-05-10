"""Gateway lifecycle, bot start/stop, time sync, terminal, and wallets routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from runtime.api import deps
from runtime.api._helpers import build_snapshot, resolve_pair
from runtime.api.schemas import (
    BotStatusOut,
    GatewaySnapshotOut,
    GatewayStartBody,
    TerminalExecBody,
    TerminalExecOut,
    TimeSyncBody,
    TimeSyncOut,
)
from runtime.app import AppContext
from runtime.connectors.binance_gateway import BinanceGateway
from runtime.core.security_util import sanitize_log_message

router = APIRouter(prefix="/api/v1", tags=["gateway"])


# ── Gateway lifecycle ───────────────────────────────────────────────

@router.post("/gateway/start")
async def gateway_start(
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> GatewaySnapshotOut:
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    if ctx.gateway:
        await ctx.gateway.stop()
        ctx.gateway = None
    ak, sec = pair
    gw = BinanceGateway(ak, sec, ctx.bus, ctx.state, ctx.log_line, ctx.config.data_dir)
    try:
        await gw.start()
        await gw.sync_time()
        await gw.fetch_account()
    except Exception as e:
        try:
            await gw.stop()
        except Exception:
            pass
        ctx.state.last_error = sanitize_log_message(str(e))
        raise HTTPException(status_code=502, detail=ctx.state.last_error) from None
    ctx.gateway = gw
    ctx.state.last_error = None
    return build_snapshot(ctx)


@router.post("/gateway/stop")
async def gateway_stop(ctx: AppContext = Depends(deps.get_ctx)) -> dict[str, bool]:
    if ctx.gateway:
        await ctx.gateway.stop()
        ctx.gateway = None
        ctx.state.connected = False
    return {"stopped": True}


@router.post("/gateway/fetch_account")
async def gateway_fetch(ctx: AppContext = Depends(deps.get_ctx)) -> GatewaySnapshotOut:
    if not ctx.gateway:
        raise HTTPException(status_code=400, detail="Gateway not running")
    await ctx.gateway.fetch_account()
    return build_snapshot(ctx)


@router.get("/gateway/snapshot", response_model=GatewaySnapshotOut)
async def gateway_snapshot(ctx: AppContext = Depends(deps.get_ctx)) -> Any:
    return build_snapshot(ctx)


# ── Bot (Dorothy legacy singleton) start/stop/run_once ──────────────

@router.post("/bot/start", response_model=BotStatusOut)
async def bot_start(
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    svc = deps.get_bot()
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    svc.runner.set_credentials(pair[0], pair[1])
    try:
        await svc.runner.sync_time()
        await svc.runner.start()
    except Exception as e:
        raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
    return BotStatusOut(**svc.status_payload())


@router.post("/bot/stop", response_model=BotStatusOut)
async def bot_stop() -> Any:
    svc = deps.get_bot()
    await svc.runner.stop()
    return BotStatusOut(**svc.status_payload())


@router.post("/bot/run_once", response_model=BotStatusOut)
async def bot_run_once(
    body: GatewayStartBody = GatewayStartBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    svc = deps.get_bot()
    pair = resolve_pair(ctx, body.api_key, body.api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")
    svc.runner.set_credentials(pair[0], pair[1])
    try:
        await svc.runner.sync_time()
        rep = await svc.runner.run_once()
        svc.mark_run_once(rep, error=None)
    except Exception as e:
        msg = sanitize_log_message(str(e))
        svc.mark_run_once({}, error=msg)
        raise HTTPException(status_code=502, detail=msg) from None
    return BotStatusOut(**svc.status_payload())


# ── Terminal + time sync ────────────────────────────────────────────

@router.post("/terminal/execute", response_model=TerminalExecOut)
async def terminal_execute(
    body: TerminalExecBody,
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    from runtime.api.terminal import _execute_terminal_command
    output = await _execute_terminal_command(ctx, body.command)
    return TerminalExecOut(ok=True, command=body.command, output=output)


@router.post("/time/sync", response_model=TimeSyncOut)
async def time_sync(
    body: TimeSyncBody = TimeSyncBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    from runtime.api._helpers import _sync_binance_time
    payload = await _sync_binance_time(ctx, body.api_key, body.api_secret)
    return TimeSyncOut(ok=True, **payload)


# ── Account wallets ─────────────────────────────────────────────────

@router.get("/account/wallets")
async def account_wallets(
    base_asset: str = "USDT",
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    # _fetch_wallet_buckets was removed; return raw balances to avoid 500 crashes
    return {"buckets": [{"asset": b["asset"], "free": b["free"]} for b in ctx.state.balances if float(b["free"]) > 0]}
# ── Symbol precision auto-resolver ──────────────────────────────────

@router.get("/gateway/symbol_precision")
async def symbol_precision(
    symbol: str,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    """Auto-resolve qty_decimals and price_decimals from Binance exchangeInfo.

    Reads LOT_SIZE.stepSize → qty_decimals and PRICE_FILTER.tickSize → price_decimals.
    This makes manual qDec/pDec fields unnecessary.
    """
    import asyncio
    from decimal import Decimal

    if not ctx.gateway or not ctx.gateway._client:
        raise HTTPException(status_code=400, detail="Gateway not running — start it first")

    client = ctx.gateway._client
    sym = symbol.upper().strip()

    try:
        info = await asyncio.to_thread(client.get_symbol_info, sym)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot fetch symbol info for {sym}: {e}") from None

    if not info:
        raise HTTPException(status_code=404, detail=f"Symbol {sym} not found on Binance")

    qty_dec = 8  # safe default
    price_dec = 8

    for f in info.get("filters", []):
        ft = str(f.get("filterType", "")).upper()
        if ft == "LOT_SIZE":
            step = f.get("stepSize", "1")
            try:
                d = Decimal(str(step)).normalize()
                # Count decimals: 0.001 → 3, 0.01 → 2, 1 → 0
                qty_dec = max(0, -d.as_tuple().exponent)
            except Exception:
                pass
        elif ft == "PRICE_FILTER":
            tick = f.get("tickSize", "0.01")
            try:
                d = Decimal(str(tick)).normalize()
                price_dec = max(0, -d.as_tuple().exponent)
            except Exception:
                pass

    return {
        "symbol": sym,
        "qty_decimals": qty_dec,
        "price_decimals": price_dec,
        "source": "exchangeInfo",
    }
