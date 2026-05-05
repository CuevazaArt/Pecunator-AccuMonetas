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
    from runtime.api.app import _execute_terminal_command
    output = await _execute_terminal_command(ctx, body.command)
    return TerminalExecOut(ok=True, command=body.command, output=output)


@router.post("/time/sync", response_model=TimeSyncOut)
async def time_sync(
    body: TimeSyncBody = TimeSyncBody(),
    ctx: AppContext = Depends(deps.get_ctx),
) -> Any:
    from runtime.api.app import _sync_binance_time
    payload = await _sync_binance_time(ctx, body.api_key, body.api_secret)
    return TimeSyncOut(ok=True, **payload)


# ── Account wallets ─────────────────────────────────────────────────

@router.get("/account/wallets")
async def account_wallets(
    base_asset: str = "USDT",
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.api.app import _fetch_wallet_buckets
    return await _fetch_wallet_buckets(ctx, base_asset=base_asset)
