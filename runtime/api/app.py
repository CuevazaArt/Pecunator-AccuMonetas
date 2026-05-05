"""FastAPI application: credential vault, gateway lifecycle, and operations API."""

from __future__ import annotations

import asyncio
import ast
import json
import logging
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any

from binance.client import Client
from binance.exceptions import BinanceAPIException
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from runtime.api import deps
from runtime.api.schemas import (
    ActiveCredentialOut,
    BotConfigBody,
    BotConfigOut,
    BotStatusOut,
    GatewaySnapshotOut,
    GatewayStartBody,
    HubBotCreateBody,
    HubBotLogsOut,
    HubBotOut,
    HubBotsOut,
    HubBotUpdateBody,
    MashaBotCreateBody,
    MashaBotLogsOut,
    MashaBotOut,
    MashaBotsOut,
    MashaBotUpdateBody,
    TerminalExecBody,
    TerminalExecOut,
    ThusneldaBotCreateBody,
    ThusneldaBotLogsOut,
    ThusneldaBotOut,
    ThusneldaBotsOut,
    ThusneldaBotUpdateBody,
    TimeSyncBody,
    TimeSyncOut,
    VaultCredentialLabelBody,
    VaultCredentialUpsertBody,
    VaultStatusOut,
)
from runtime.app import AppContext
from runtime.connectors.binance_gateway import BinanceGateway
from runtime.core.equity import build_ticker_price_map, compute_spot_equity_in_base
from runtime.core.ops_audit_log import get_ops_audit_log
from runtime.core.security_util import sanitize_log_message
from runtime.api._helpers import resolve_pair as _resolve_pair_impl
from runtime.api._helpers import build_snapshot as _snapshot_impl
from runtime.api._helpers import audit_weight_from_client as _audit_weight_impl
from runtime.api._helpers import mask_pk, pk_last4, rest_weight_estimate_report
from runtime.api.routers import system as _system_router
from runtime.api.routers import masha as _masha_router
from runtime.api.routers import thusnelda as _thusnelda_router
from runtime.api.routers import vault as _vault_router
from runtime.api.routers import ops as _ops_router

from runtime.core.settings import (
    account_poll_interval_sec,
    api_bind_host_for_cors_regex,
    api_weight_limit_1m_display,
    binance_credentials_from_env,
    equity_poll_stride,
    my_trades_poll_stride,
)

_LOG = logging.getLogger("pecunator.api")
_SANDBOX_DB_LOCK = threading.Lock()


def _mask_pk(pk: str) -> str:
    s = pk.strip()
    return s if len(s) <= 24 else f"{s[:14]}...{s[-6:]}"


def _pk_last4(pk: str) -> str:
    s = (pk or "").strip()
    return s[-4:] if len(s) >= 4 else s


@asynccontextmanager
async def _lifespan(app: FastAPI):
    deps.init_context()
    ctx = deps.get_ctx()
    bot = deps.get_bot()
    masha = deps.get_masha()
    thusnelda = deps.get_thusnelda()
    earn = deps.get_earn()
    credential_resolver = lambda: _resolve_pair(ctx)  # noqa: E731
    bot.start_immortality(credential_resolver, interval_sec=5.0)
    masha.start_immortality(credential_resolver, interval_sec=5.0)
    thusnelda.start_immortality(credential_resolver, interval_sec=5.0)
    
    # Setup Binance Client resolver for Earn
    def _client_resolver():
        pk, sk = _resolve_pair(deps.get_ctx())
        if pk and sk:
            return Client(pk, sk)
        return None
        
    earn.start_background_sync(_client_resolver, interval_sec=28800)
    await _autostart_gateway_if_possible(ctx)
    yield
    ctx = deps.peek_ctx()
    bot = deps.get_bot()
    masha = deps.get_masha()
    thusnelda = deps.get_thusnelda()
    earn = deps.get_earn()
    await earn.stop_background_sync()
    await bot.stop_immortality()
    await masha.stop_immortality()
    await thusnelda.stop_immortality()
    await bot.stop_all()
    await masha.stop_all()
    await thusnelda.stop_all()
    if ctx and ctx.gateway:
        try:
            await ctx.gateway.stop()
        except Exception as e:
            _LOG.warning("gateway stop on shutdown: %s", e)
        ctx.gateway = None


async def _autostart_gateway_if_possible(ctx: AppContext) -> None:
    from runtime.core.settings import gateway_autostart_enabled
    if ctx.gateway is not None:
        return
    if not gateway_autostart_enabled():
        _LOG.info("Gateway auto-start DISABLED (gateway_settings.json autostart_gateway=false)")
        return
    try:
        pair = _resolve_pair(ctx)
    except HTTPException:
        pair = None
    except Exception as e:
        _LOG.warning("Gateway auto-start resolve skipped: %s", sanitize_log_message(str(e)))
        pair = None
    if not pair:
        _LOG.info("Gateway auto-start skipped: no credentials resolved")
        return
    gw = BinanceGateway(pair[0], pair[1], ctx.bus, ctx.state, ctx.log_line, ctx.config.data_dir)
    try:
        await gw.start()
        await gw.sync_time()
        await gw.fetch_account()
        await gw.refresh_equity(force_tickers=True)
        ctx.gateway = gw
        ctx.state.last_error = None
        _LOG.info("Gateway auto-started on API startup")
    except Exception as e:
        try:
            await gw.stop()
        except Exception:
            pass
        ctx.state.last_error = sanitize_log_message(str(e))
        _LOG.warning("Gateway auto-start failed: %s", ctx.state.last_error)


def create_app() -> FastAPI:
    app = FastAPI(
        title="PecunatorCore Engine API",
        description="Local HTTP API for the Flutter shell. Bind loopback only unless you know the risk.",
        version="0.3.0",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=api_bind_host_for_cors_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers (extracted from monolith) ────────────────────────────
    app.include_router(_system_router.router)
    app.include_router(_masha_router.router)
    app.include_router(_thusnelda_router.router)
    app.include_router(_vault_router.router)
    app.include_router(_ops_router.router)

    # ── NOTE: The routes below remain here temporarily.
    # ── They will be extracted to routers in future iterations.

    # ── Dorothy Hub routes (kept inline for now) ──────────────────

    @app.get("/api/v1/bot/presets")
    async def health() -> dict[str, Any]:
        """Standard health check — safe to poll frequently, weight 0."""
        ctx = deps.get_ctx()
        bot = deps.get_bot()
        masha = deps.get_masha()
        thusnelda = deps.get_thusnelda()
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
            "masha": masha.hub_stats(),
            "thusnelda": thusnelda.hub_stats(),
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

    @app.get("/health/deep")
    async def health_deep() -> dict[str, Any]:
        ctx = deps.get_ctx()
        bot = deps.get_bot()
        masha = deps.get_masha()
        thusnelda = deps.get_thusnelda()
        gw_ok = ctx.gateway is not None and getattr(ctx.gateway, "_ws_task", None) is not None
        return {
            "status": "ok",
            "gateway_connected": gw_ok,
            "gateway_last_error": ctx.state.last_error,
            "hubs": {
                "dorothy": bot.hub_stats(),
                "masha": masha.hub_stats(),
                "thusnelda": thusnelda.hub_stats(),
            },
            "data_dir": str(ctx.config.data_dir),
        }

    # ── Vault routes moved to routers/vault.py ──

    @app.get("/api/v1/bot/presets")
    async def bot_presets() -> list[dict[str, Any]]:
        return [
            {
                "preset_id": "B",
                "name": "Dorothy7 preset B",
                "symbol": "XRPUSDT",
                "loop_interval_sec": 450,
                "quote_order_qty": "8",
                "profit_factor": "0.05",
                "margin_drop_factor": "0.004",
                "qty_decimals": 8,
                "price_decimals": 4,
                "simulated": True,
                "trading_enabled": False,
            }
        ]

    @app.get("/api/v1/bot/config", response_model=BotConfigOut)
    async def bot_config_get() -> Any:
        cfg = deps.get_bot().get_config()
        return BotConfigOut(**cfg.as_json())

    @app.put("/api/v1/bot/config", response_model=BotConfigOut)
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
            simulated=body.simulated,
            trading_enabled=body.trading_enabled,
        )
        return BotConfigOut(**cfg.as_json())

    @app.get("/api/v1/bot/status", response_model=BotStatusOut)
    async def bot_status() -> Any:
        return BotStatusOut(**deps.get_bot().status_payload())

    @app.get("/api/v1/hub/bots", response_model=HubBotsOut)
    async def hub_bots_list() -> Any:
        return HubBotsOut(bots=[HubBotOut(**row) for row in deps.get_bot().list_instances()])

    @app.post("/api/v1/hub/bots", response_model=HubBotOut)
    async def hub_bots_create(body: HubBotCreateBody) -> Any:
        svc = deps.get_bot()
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
                simulated=body.simulated,
                trading_enabled=body.trading_enabled,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=sanitize_log_message(str(e))) from None
        return HubBotOut(**row)

    @app.patch("/api/v1/hub/bots/{bot_id}", response_model=HubBotOut)
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
                simulated=body.simulated,
                trading_enabled=body.trading_enabled,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="Bot not found") from None
        except Exception as e:
            raise HTTPException(status_code=400, detail=sanitize_log_message(str(e))) from None
        return HubBotOut(**row)

    @app.delete("/api/v1/hub/bots/{bot_id}")
    async def hub_bots_delete(bot_id: str) -> dict[str, bool]:
        svc = deps.get_bot()
        try:
            await svc.delete_instance(bot_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Bot not found") from None
        return {"deleted": True}

    @app.post("/api/v1/hub/bots/{bot_id}/start", response_model=HubBotOut)
    async def hub_bots_start(
        bot_id: str,
        body: GatewayStartBody = GatewayStartBody(),
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> Any:
        pair = _resolve_pair(ctx, body.api_key, body.api_secret)
        if not pair:
            raise HTTPException(status_code=400, detail="No API credentials available")
        try:
            row = await deps.get_bot().start_instance(bot_id, pair[0], pair[1])
        except KeyError:
            raise HTTPException(status_code=404, detail="Bot not found") from None
        except Exception as e:
            raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
        return HubBotOut(**row)

    @app.post("/api/v1/hub/bots/{bot_id}/stop", response_model=HubBotOut)
    async def hub_bots_stop(bot_id: str) -> Any:
        try:
            row = await deps.get_bot().stop_instance(bot_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Bot not found") from None
        return HubBotOut(**row)

    @app.post("/api/v1/hub/bots/{bot_id}/run_once", response_model=HubBotOut)
    async def hub_bots_run_once(
        bot_id: str,
        body: GatewayStartBody = GatewayStartBody(),
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> Any:
        pair = _resolve_pair(ctx, body.api_key, body.api_secret)
        if not pair:
            raise HTTPException(status_code=400, detail="No API credentials available")
        try:
            row = await deps.get_bot().run_once_instance(bot_id, pair[0], pair[1])
        except KeyError:
            raise HTTPException(status_code=404, detail="Bot not found") from None
        except Exception as e:
            raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
        return HubBotOut(**row)

    @app.get("/api/v1/hub/bots/{bot_id}/logs", response_model=HubBotLogsOut)
    async def hub_bots_logs(bot_id: str, limit: int = 200) -> Any:
        try:
            rows = deps.get_bot().get_logs(bot_id, limit=limit)
        except KeyError:
            raise HTTPException(status_code=404, detail="Bot not found") from None
        return HubBotLogsOut(logs=rows)

    # ── Masha & Thusnelda routes moved to routers/masha.py and routers/thusnelda.py ──


    @app.post("/api/v1/terminal/execute", response_model=TerminalExecOut)
    async def terminal_execute(
        body: TerminalExecBody,
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> Any:
        output = await _execute_terminal_command(ctx, body.command)
        return TerminalExecOut(ok=True, command=body.command, output=output)

    @app.post("/api/v1/time/sync", response_model=TimeSyncOut)
    async def time_sync(
        body: TimeSyncBody = TimeSyncBody(),
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> Any:
        payload = await _sync_binance_time(ctx, body.api_key, body.api_secret)
        return TimeSyncOut(ok=True, **payload)

    @app.post("/api/v1/gateway/start")
    async def gateway_start(
        body: GatewayStartBody = GatewayStartBody(),
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> GatewaySnapshotOut:
        pair = _resolve_pair(ctx, body.api_key, body.api_secret)
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
        return _snapshot(ctx)

    @app.post("/api/v1/bot/start", response_model=BotStatusOut)
    async def bot_start(
        body: GatewayStartBody = GatewayStartBody(),
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> Any:
        svc = deps.get_bot()
        pair = _resolve_pair(ctx, body.api_key, body.api_secret)
        if not pair:
            raise HTTPException(status_code=400, detail="No API credentials available")
        svc.runner.set_credentials(pair[0], pair[1])
        try:
            await svc.runner.sync_time()
            await svc.runner.start()
        except Exception as e:
            raise HTTPException(status_code=502, detail=sanitize_log_message(str(e))) from None
        return BotStatusOut(**svc.status_payload())

    @app.post("/api/v1/bot/stop", response_model=BotStatusOut)
    async def bot_stop() -> Any:
        svc = deps.get_bot()
        await svc.runner.stop()
        return BotStatusOut(**svc.status_payload())

    @app.post("/api/v1/bot/run_once", response_model=BotStatusOut)
    async def bot_run_once(
        body: GatewayStartBody = GatewayStartBody(),
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> Any:
        svc = deps.get_bot()
        pair = _resolve_pair(ctx, body.api_key, body.api_secret)
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

    @app.post("/api/v1/gateway/stop")
    async def gateway_stop(ctx: AppContext = Depends(deps.get_ctx)) -> dict[str, bool]:
        if ctx.gateway:
            await ctx.gateway.stop()
            ctx.gateway = None
            ctx.state.connected = False
        return {"stopped": True}

    @app.post("/api/v1/gateway/fetch_account")
    async def gateway_fetch(ctx: AppContext = Depends(deps.get_ctx)) -> GatewaySnapshotOut:
        if not ctx.gateway:
            raise HTTPException(status_code=400, detail="Gateway not running")
        await ctx.gateway.fetch_account()
        return _snapshot(ctx)

    @app.get("/api/v1/gateway/snapshot", response_model=GatewaySnapshotOut)
    async def gateway_snapshot(ctx: AppContext = Depends(deps.get_ctx)) -> Any:
        return _snapshot(ctx)

    # ── Usage routes moved to routers/system.py ──

    @app.get("/api/v1/account/wallets")
    async def account_wallets(
        base_asset: str = "USDT",
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> dict[str, Any]:
        return await _fetch_wallet_buckets(ctx, base_asset=base_asset)

    # ── Ops routes moved to routers/ops.py ──

    @app.post("/api/v1/sandbox/curated/save")
    async def sandbox_curated_save(
        payload: dict[str, Any],
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> dict[str, Any]:
        rec = _sandbox_curated_save(ctx, payload)
        return {"saved": True, "record": rec}

    @app.get("/api/v1/sandbox/curated/list")
    async def sandbox_curated_list(
        limit: int = 50,
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> dict[str, Any]:
        rows = _sandbox_curated_list(ctx, limit=limit)
        return {"items": rows}

    @app.get("/api/v1/sandbox/rest/catalog")
    async def sandbox_rest_catalog() -> dict[str, Any]:
        return {"items": _sandbox_rest_catalog()}

    @app.post("/api/v1/sandbox/rest/query")
    async def sandbox_rest_query(
        body: dict[str, Any],
        ctx: AppContext = Depends(deps.get_ctx),
    ) -> dict[str, Any]:
        return await _sandbox_rest_query(ctx, body)

    @app.get("/api/v1/earn/history/{symbol}")
    async def get_earn_history(symbol: str) -> dict[str, Any]:
        earn = deps.get_earn()
        return {"items": earn.get_history(symbol)}

    @app.post("/api/v1/earn/sync")
    async def force_earn_sync() -> dict[str, Any]:
        earn = deps.get_earn()
        def _client_resolver():
            pk, sk = _resolve_pair(deps.get_ctx())
            if pk and sk:
                return Client(pk, sk)
            return None
        res = await earn.force_sync(_client_resolver)
        return res

    # ── Gateway Settings (persistent JSON) ───────────────────────────

    # ── System routes moved to routers/system.py ──

    return app


def _snapshot(ctx: AppContext) -> GatewaySnapshotOut:
    out = GatewaySnapshotOut(
        gateway_running=ctx.gateway is not None,
        last_error=ctx.state.last_error,
        account_summary=dict(ctx.state.account_summary or {}),
        account_equity=dict(ctx.state.account_equity or {}),
        balances=list(ctx.state.balances),
        balances_total_assets_in_response=int(getattr(ctx.state, "balances_total_assets_in_response", 0) or 0),
        ws_connected=bool(ctx.state.connected),
        selected_symbol=ctx.state.selected_symbol,
        used_weight_1m=getattr(ctx.state, "api_weight_used_1m", None),
        weight_limit_1m=api_weight_limit_1m_display(),
        binance_server_time_ms=getattr(ctx.state, "binance_server_time_ms", None),
        binance_local_time_ms_at_sync=getattr(
            ctx.state, "binance_local_time_ms_at_sync", None
        ),
        binance_offset_ms=getattr(ctx.state, "binance_offset_ms", None),
        binance_time_synced_at_utc=getattr(
            ctx.state, "binance_time_synced_at_utc", None
        ),
    )
    try:
        from runtime.core.rest_usage_log import get_rest_usage_log

        st = deps.get_bot().hub_stats()
        get_rest_usage_log(ctx.config.data_dir).maybe_record(
            used=getattr(ctx.state, "api_weight_used_1m", None),
            limit=api_weight_limit_1m_display(),
            hub_bots_total=int(st.get("hub_bots_total", 0)),
            hub_bots_running=int(st.get("hub_bots_running", 0)),
            poll_sec=account_poll_interval_sec(),
            gateway_running=ctx.gateway is not None,
            last_error=ctx.state.last_error,
        )
    except Exception:
        pass
    return out


def _rest_weight_estimate_report() -> dict[str, Any]:
    poll_sec = account_poll_interval_sec()
    cycles_per_min = 0.0
    if poll_sec > 0:
        cycles_per_min = 60.0 / poll_sec
    trades_stride = max(1, my_trades_poll_stride())
    eq_stride = max(1, equity_poll_stride())
    return {
        "cycles_per_min": round(cycles_per_min, 3),
        "gateway_actions": [
            {
                "action": "fetch_account:get_account",
                "frequency_per_min": round(cycles_per_min, 3),
                "notes": "executed once every poll cycle",
            },
            {
                "action": "fetch_open_orders:get_open_orders",
                "frequency_per_min": round(cycles_per_min, 3),
                "notes": "executed once every poll cycle",
            },
            {
                "action": "fetch_my_trades:get_my_trades:*",
                "frequency_per_min": round(cycles_per_min / trades_stride, 3),
                "notes": "controlled by PECUNATOR_MY_TRADES_POLL_STRIDE",
            },
            {
                "action": "refresh_equity:get_all_tickers",
                "frequency_per_min": round(cycles_per_min / eq_stride, 3),
                "notes": "controlled by PECUNATOR_EQUITY_POLL_STRIDE",
            },
            {
                "action": "sync_time:get_server_time",
                "frequency_per_min": "event-driven",
                "notes": "manual sync, startup, or retry paths",
            },
        ],
    }


def _audit_weight_from_client(
    ctx: AppContext,
    client: Client,
    *,
    source: str,
    action: str,
    note: str | None = None,
) -> None:
    try:
        resp = getattr(client, "response", None)
        headers = getattr(resp, "headers", None) or {}
        raw = None
        for k, v in headers.items():
            if str(k).upper() == "X-MBX-USED-WEIGHT-1M":
                raw = v
                break
        if raw is None:
            return
        used = int(float(raw))
        ctx.state.api_weight_used_1m = used
        from runtime.core.rest_usage_log import get_rest_usage_log

        get_rest_usage_log(ctx.config.data_dir).record_event(
            source=source,
            action=action,
            used_weight_1m=used,
            note=note,
        )
        # Feed real-time weight to the Governor for dynamic throttling
        try:
            from runtime.core.weight_governor import get_weight_governor
            get_weight_governor().update_weight(used)
        except Exception:
            pass
        # Feed real-time weight to the Coordinator for launch decisions
        try:
            from runtime.core.bot_coordinator import get_bot_coordinator
            get_bot_coordinator().update_weight(used)
        except Exception:
            pass
    except Exception:
        pass


def _to_decimal_str(value: Any) -> str:
    try:
        dec = Decimal(str(value or "0"))
        text = format(dec, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        if text in ("", "-0"):
            return "0"
        return text
    except (InvalidOperation, ValueError, TypeError):
        return "0"


def _is_non_zero(value: str) -> bool:
    try:
        return Decimal(value) != 0
    except (InvalidOperation, ValueError, TypeError):
        return False


def _bucket_sum(rows: list[dict[str, Any]], key: str) -> str:
    total = Decimal("0")
    for row in rows:
        try:
            total += Decimal(str(row.get(key, "0")))
        except (InvalidOperation, ValueError, TypeError):
            pass
    return str(total)


async def _fetch_wallet_buckets(ctx: AppContext, base_asset: str = "USDT") -> dict[str, Any]:
    pair = _resolve_pair(ctx)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")

    client = Client(pair[0], pair[1], requests_params={"timeout": 15})
    base = (base_asset or "USDT").strip().upper() or "USDT"
    warnings: list[str] = []
    spot_rows: list[dict[str, Any]] = []
    futures_rows: list[dict[str, Any]] = []
    earn_rows: list[dict[str, Any]] = []
    external_rows: list[dict[str, Any]] = []
    try:
        try:
            await _sandbox_sync_timestamp(
                client,
                ctx=ctx,
                source="wallets",
                action="sync_time:get_server_time",
            )
        except Exception:
            pass
        account = await _sandbox_signed_call_with_time_retry(
            client,
            client.get_account,
            ctx=ctx,
            source="wallets",
            action="wallets:get_account",
        )
        raw_balances = account.get("balances", []) if isinstance(account, dict) else []
        if not isinstance(raw_balances, list):
            raw_balances = []
        for b in raw_balances:
            asset = str((b or {}).get("asset", "")).upper()
            free = _to_decimal_str((b or {}).get("free", "0"))
            locked = _to_decimal_str((b or {}).get("locked", "0"))
            total = _to_decimal_str(Decimal(free) + Decimal(locked))
            if not _is_non_zero(total):
                continue
            row = {"asset": asset, "free": free, "locked": locked, "total": total}
            if asset.startswith("LD"):
                earn_rows.append(row)
            else:
                spot_rows.append(row)

        if hasattr(client, "futures_account_balance"):
            try:
                fut = await _sandbox_signed_call_with_time_retry(
                    client,
                    client.futures_account_balance,
                    ctx=ctx,
                    source="wallets",
                    action="wallets:futures_account_balance",
                )
                if isinstance(fut, list):
                    for r in fut:
                        asset = str((r or {}).get("asset", "")).upper()
                        wb = _to_decimal_str((r or {}).get("balance", "0"))
                        cw = _to_decimal_str((r or {}).get("crossWalletBalance", "0"))
                        if not (_is_non_zero(wb) or _is_non_zero(cw)):
                            continue
                        futures_rows.append(
                            {
                                "asset": asset,
                                "wallet_balance": wb,
                                "cross_wallet_balance": cw,
                                "total": wb,
                            }
                        )
            except Exception as e:
                warnings.append(f"futures unavailable: {sanitize_log_message(str(e))}")
        else:
            warnings.append("futures endpoint not available in this client build")

        if hasattr(client, "get_funding_wallet"):
            try:
                ext = await _sandbox_signed_call_with_time_retry(
                    client,
                    client.get_funding_wallet,
                    ctx=ctx,
                    source="wallets",
                    action="wallets:get_funding_wallet",
                )
                if isinstance(ext, list):
                    for r in ext:
                        asset = str((r or {}).get("asset", "")).upper()
                        free = _to_decimal_str((r or {}).get("free", "0"))
                        locked = _to_decimal_str((r or {}).get("locked", "0"))
                        freeze = _to_decimal_str((r or {}).get("freeze", "0"))
                        total = _to_decimal_str(Decimal(free) + Decimal(locked) + Decimal(freeze))
                        if not _is_non_zero(total):
                            continue
                        external_rows.append(
                            {
                                "asset": asset,
                                "free": free,
                                "locked": locked,
                                "freeze": freeze,
                                "total": total,
                            }
                        )
            except Exception as e:
                warnings.append(f"external wallet unavailable: {sanitize_log_message(str(e))}")
        else:
            warnings.append("external wallet endpoint not available in this client build")

        equity: dict[str, Any] = {}
        try:
            tickers = await asyncio.to_thread(client.get_all_tickers)
            _audit_weight_from_client(
                ctx,
                client,
                source="wallets",
                action="wallets:get_all_tickers",
            )
            px = build_ticker_price_map(tickers)
            equity = compute_spot_equity_in_base(spot_rows, px, base_asset=base)
        except Exception as e:
            warnings.append(f"equity unavailable: {sanitize_log_message(str(e))}")

        spot_rows.sort(key=lambda r: r.get("asset", ""))
        futures_rows.sort(key=lambda r: r.get("asset", ""))
        earn_rows.sort(key=lambda r: r.get("asset", ""))
        external_rows.sort(key=lambda r: r.get("asset", ""))

        return {
            "base_asset": base,
            "spot": spot_rows,
            "futures": futures_rows,
            "stake_earn": earn_rows,
            "external": external_rows,
            "base_asset_totals": {
                "spot": next((r for r in spot_rows if r.get("asset") == base), {"total": "0"}),
                "futures": next((r for r in futures_rows if r.get("asset") == base), {"total": "0"}),
                "stake_earn": next((r for r in earn_rows if r.get("asset") == f"LD{base}"), {"total": "0"}),
                "external": next((r for r in external_rows if r.get("asset") == base), {"total": "0"}),
            },
            "summary": {
                "spot_assets": len(spot_rows),
                "futures_assets": len(futures_rows),
                "stake_earn_assets": len(earn_rows),
                "external_assets": len(external_rows),
                "spot_total_sum": _bucket_sum(spot_rows, "total"),
                "futures_total_sum": _bucket_sum(futures_rows, "total"),
                "stake_earn_total_sum": _bucket_sum(earn_rows, "total"),
                "external_total_sum": _bucket_sum(external_rows, "total"),
            },
            "equity": equity,
            "warnings": warnings,
        }
    finally:
        try:
            await asyncio.to_thread(client.close_connection)
        except Exception:
            pass


async def _stop_dorothy_for_protocol() -> tuple[int, list[str]]:
    svc = deps.get_bot()
    stopped = 0
    errors: list[str] = []
    for row in svc.list_instances():
        bot_id = str(row.get("bot_id", "")).strip()
        if not bot_id:
            continue
        should_stop = bool(row.get("running")) or bool(row.get("desired_running"))
        if not should_stop:
            continue
        try:
            await svc.stop_instance(bot_id)
            stopped += 1
        except Exception as e:
            errors.append(f"{bot_id}: {sanitize_log_message(str(e))}")
    return stopped, errors


def _format_lot_quantity(symbol_info: dict[str, Any] | None, raw_qty: Decimal) -> Decimal | None:
    if not symbol_info or raw_qty <= 0:
        return None
    filters = symbol_info.get("filters") if isinstance(symbol_info, dict) else None
    if not isinstance(filters, list):
        return None
    min_qty = Decimal("0")
    step = Decimal("0")
    for f in filters:
        if not isinstance(f, dict):
            continue
        if str(f.get("filterType")) == "LOT_SIZE":
            try:
                min_qty = Decimal(str(f.get("minQty", "0")))
                step = Decimal(str(f.get("stepSize", "0")))
            except (InvalidOperation, TypeError, ValueError):
                return None
            break
    if step <= 0:
        return None
    qty = (raw_qty / step).to_integral_value(rounding=ROUND_DOWN) * step
    if qty < min_qty or qty <= 0:
        return None
    return qty


async def _execute_close_protocol(ctx: AppContext, base_asset: str = "USDT") -> dict[str, Any]:
    started_at = time.time()
    base = (base_asset or "USDT").strip().upper() or "USDT"
    summary: dict[str, Any] = {
        "protocol": "close_protocol",
        "base_asset": base,
        "status": "ok",
        "stopped_dorothy_instances": 0,
        "stop_errors": [],
        "open_orders_seen": 0,
        "limit_orders_canceled": 0,
        "cancel_errors": [],
        "equity_snapshot": {},
        "log_lines": [],
    }
    pair = _resolve_pair(ctx)
    if not pair:
        summary["status"] = "failed"
        summary["error"] = "No API credentials available"
        summary["log_lines"].append("No API credentials available.")
        return summary

    stopped, stop_errors = await _stop_dorothy_for_protocol()
    summary["stopped_dorothy_instances"] = stopped
    summary["stop_errors"] = stop_errors
    summary["log_lines"].append(f"Dorothy instances stopped before protocol: {stopped}.")
    if stop_errors:
        summary["log_lines"].append(f"Dorothy stop errors: {len(stop_errors)}.")

    client = Client(pair[0], pair[1], requests_params={"timeout": 20})
    try:
        orders = await asyncio.to_thread(client.get_open_orders)
        _audit_weight_from_client(ctx, client, source="ops", action="close_protocol:get_open_orders")
        if not isinstance(orders, list):
            orders = []
        summary["open_orders_seen"] = len(orders)
        for order in orders:
            if not isinstance(order, dict):
                continue
            if str(order.get("type", "")).upper() != "LIMIT":
                continue
            sym = str(order.get("symbol", "")).upper()
            oid = order.get("orderId")
            if not sym or oid is None:
                continue
            try:
                await asyncio.to_thread(client.cancel_order, symbol=sym, orderId=oid)
                _audit_weight_from_client(
                    ctx,
                    client,
                    source="ops",
                    action=f"close_protocol:cancel_order:{sym}",
                )
                summary["limit_orders_canceled"] += 1
            except Exception as e:
                summary["cancel_errors"].append(f"{sym}#{oid}: {sanitize_log_message(str(e))}")

        account = await asyncio.to_thread(client.get_account)
        _audit_weight_from_client(ctx, client, source="ops", action="close_protocol:get_account")
        balances = account.get("balances", []) if isinstance(account, dict) else []
        tickers = await asyncio.to_thread(client.get_all_tickers)
        _audit_weight_from_client(ctx, client, source="ops", action="close_protocol:get_all_tickers")
        px_map = build_ticker_price_map(tickers if isinstance(tickers, list) else [])
        summary["equity_snapshot"] = compute_spot_equity_in_base(
            balances if isinstance(balances, list) else [],
            px_map,
            base_asset=base,
        )

        if summary["stop_errors"] or summary["cancel_errors"]:
            summary["status"] = "partial"
        summary["log_lines"].append(
            f"Open orders seen={summary['open_orders_seen']}, limit canceled={summary['limit_orders_canceled']}."
        )
        summary["log_lines"].append(
            f"Equity snapshot in {base}: {summary['equity_snapshot'].get('current', '0')}."
        )
    except BinanceAPIException as e:
        summary["status"] = "failed"
        summary["error"] = sanitize_log_message(str(e))
        summary["log_lines"].append(f"Binance API error: {summary['error']}")
    except Exception as e:
        summary["status"] = "failed"
        summary["error"] = sanitize_log_message(str(e))
        summary["log_lines"].append(f"Unexpected error: {summary['error']}")
    finally:
        try:
            await asyncio.to_thread(client.close_connection)
        except Exception:
            pass

    summary["elapsed_sec"] = round(time.time() - started_at, 3)
    return summary


async def _execute_red_button(ctx: AppContext, base_asset: str = "USDT") -> dict[str, Any]:
    started_at = time.time()
    base = (base_asset or "USDT").strip().upper() or "USDT"
    summary: dict[str, Any] = {
        "protocol": "red_button",
        "base_asset": base,
        "status": "ok",
        "stopped_dorothy_instances": 0,
        "stop_errors": [],
        "assets_evaluated": 0,
        "assets_sold": 0,
        "orders_canceled": 0,
        "skipped_assets": [],
        "sell_errors": [],
        "log_lines": [],
    }
    pair = _resolve_pair(ctx)
    if not pair:
        summary["status"] = "failed"
        summary["error"] = "No API credentials available"
        summary["log_lines"].append("No API credentials available.")
        return summary

    stopped, stop_errors = await _stop_dorothy_for_protocol()
    summary["stopped_dorothy_instances"] = stopped
    summary["stop_errors"] = stop_errors
    summary["log_lines"].append(f"Dorothy instances stopped before RED BUTTON: {stopped}.")
    if stop_errors:
        summary["log_lines"].append(f"Dorothy stop errors: {len(stop_errors)}.")

    client = Client(pair[0], pair[1], requests_params={"timeout": 20})
    try:
        account = await asyncio.to_thread(client.get_account)
        _audit_weight_from_client(ctx, client, source="ops", action="red_button:get_account")
        balances = account.get("balances", []) if isinstance(account, dict) else []
        if not isinstance(balances, list):
            balances = []

        exch = await asyncio.to_thread(client.get_exchange_info)
        _audit_weight_from_client(ctx, client, source="ops", action="red_button:get_exchange_info")
        symbols = {}
        if isinstance(exch, dict):
            raw_symbols = exch.get("symbols", [])
            if isinstance(raw_symbols, list):
                symbols = {
                    str(s.get("symbol", "")).upper(): s
                    for s in raw_symbols
                    if isinstance(s, dict) and str(s.get("symbol", "")).strip()
                }

        for row in balances:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("asset", "")).upper()
            try:
                free_qty = Decimal(str(row.get("free", "0") or "0"))
            except (InvalidOperation, TypeError, ValueError):
                summary["skipped_assets"].append(f"{asset or '?'}: invalid free quantity")
                continue
            if asset == base or free_qty <= 0:
                continue
            summary["assets_evaluated"] += 1
            symbol = f"{asset}{base}"
            symbol_info = symbols.get(symbol)
            if not symbol_info or str(symbol_info.get("status", "")).upper() != "TRADING":
                summary["skipped_assets"].append(f"{asset}: no direct {symbol} trading pair")
                continue

            try:
                open_orders = await asyncio.to_thread(client.get_open_orders, symbol=symbol)
                _audit_weight_from_client(
                    ctx,
                    client,
                    source="ops",
                    action=f"red_button:get_open_orders:{symbol}",
                )
                if isinstance(open_orders, list):
                    for order in open_orders:
                        if not isinstance(order, dict):
                            continue
                        oid = order.get("orderId")
                        if oid is None:
                            continue
                        await asyncio.to_thread(client.cancel_order, symbol=symbol, orderId=oid)
                        _audit_weight_from_client(
                            ctx,
                            client,
                            source="ops",
                            action=f"red_button:cancel_order:{symbol}",
                        )
                        summary["orders_canceled"] += 1
            except Exception as e:
                summary["sell_errors"].append(f"{asset}: cancel orders {sanitize_log_message(str(e))}")
                continue

            qty = _format_lot_quantity(symbol_info, free_qty)
            if qty is None:
                summary["skipped_assets"].append(f"{asset}: quantity below LOT_SIZE/minQty")
                continue

            try:
                await asyncio.to_thread(client.order_market_sell, symbol=symbol, quantity=str(qty))
                _audit_weight_from_client(
                    ctx,
                    client,
                    source="ops",
                    action=f"red_button:order_market_sell:{symbol}",
                )
                summary["assets_sold"] += 1
                summary["log_lines"].append(f"Sold {qty} {asset} -> {base} using {symbol}.")
            except Exception as e:
                summary["sell_errors"].append(f"{asset}: market sell {sanitize_log_message(str(e))}")

        if summary["stop_errors"] or summary["sell_errors"]:
            summary["status"] = "partial"
    except BinanceAPIException as e:
        summary["status"] = "failed"
        summary["error"] = sanitize_log_message(str(e))
        summary["log_lines"].append(f"Binance API error: {summary['error']}")
    except Exception as e:
        summary["status"] = "failed"
        summary["error"] = sanitize_log_message(str(e))
        summary["log_lines"].append(f"Unexpected error: {summary['error']}")
    finally:
        try:
            await asyncio.to_thread(client.close_connection)
        except Exception:
            pass

    summary["elapsed_sec"] = round(time.time() - started_at, 3)
    return summary


def _is_stop_order_type(order_type: str) -> bool:
    t = (order_type or "").strip().upper()
    return t in {
        "STOP_LOSS",
        "STOP_LOSS_LIMIT",
        "TAKE_PROFIT",
        "TAKE_PROFIT_LIMIT",
        "STOP",
        "STOP_MARKET",
        "TAKE_PROFIT_MARKET",
    }


def _matches_cleanup_mode(order_type: str, mode: str) -> bool:
    m = (mode or "").strip().lower()
    t = (order_type or "").strip().upper()
    if m == "all":
        return True
    if m == "limit":
        return t == "LIMIT"
    if m == "stop":
        return _is_stop_order_type(t)
    return False


async def _execute_order_cleanup(
    ctx: AppContext,
    base_asset: str = "USDT",
    mode: str = "all",
) -> dict[str, Any]:
    started_at = time.time()
    base = (base_asset or "USDT").strip().upper() or "USDT"
    mode_norm = (mode or "all").strip().lower()
    if mode_norm not in {"limit", "stop", "all"}:
        mode_norm = "all"
    summary: dict[str, Any] = {
        "protocol": f"cancel_{mode_norm}_orders_cleanup",
        "base_asset": base,
        "mode": mode_norm,
        "status": "ok",
        "stopped_dorothy_instances": 0,
        "stop_errors": [],
        "symbols_scanned": 0,
        "open_orders_seen": 0,
        "orders_canceled": 0,
        "cancel_errors": [],
        "scan_errors": [],
        "log_lines": [],
    }
    pair = _resolve_pair(ctx)
    if not pair:
        summary["status"] = "failed"
        summary["error"] = "No API credentials available"
        summary["log_lines"].append("No API credentials available.")
        return summary

    stopped, stop_errors = await _stop_dorothy_for_protocol()
    summary["stopped_dorothy_instances"] = stopped
    summary["stop_errors"] = stop_errors
    summary["log_lines"].append(f"Dorothy instances stopped before cleanup: {stopped}.")
    if stop_errors:
        summary["log_lines"].append(f"Dorothy stop errors: {len(stop_errors)}.")

    client = Client(pair[0], pair[1], requests_params={"timeout": 20})
    try:
        orders_to_eval: list[dict[str, Any]] = []
        if mode_norm == "all":
            account_orders = await asyncio.to_thread(client.get_open_orders)
            _audit_weight_from_client(ctx, client, source="ops", action="cleanup:get_open_orders")
            if isinstance(account_orders, list):
                orders_to_eval = [o for o in account_orders if isinstance(o, dict)]
        else:
            # deleteAllOrdersLimit semantics: iterate funded spot assets and inspect ASSET+BASE symbol.
            account = await asyncio.to_thread(client.get_account)
            _audit_weight_from_client(ctx, client, source="ops", action="cleanup:get_account")
            balances = account.get("balances", []) if isinstance(account, dict) else []
            if not isinstance(balances, list):
                balances = []
            symbols: list[str] = []
            for row in balances:
                if not isinstance(row, dict):
                    continue
                asset = str(row.get("asset", "")).upper()
                if not asset or asset == base:
                    continue
                try:
                    free = Decimal(str(row.get("free", "0") or "0"))
                    locked = Decimal(str(row.get("locked", "0") or "0"))
                except (InvalidOperation, ValueError, TypeError):
                    continue
                if (free + locked) <= 0:
                    continue
                symbols.append(f"{asset}{base}")
            dedup = sorted(set(symbols))
            summary["symbols_scanned"] = len(dedup)
            for sym in dedup:
                try:
                    sym_orders = await asyncio.to_thread(client.get_open_orders, symbol=sym)
                    _audit_weight_from_client(
                        ctx,
                        client,
                        source="ops",
                        action=f"cleanup:get_open_orders:{sym}",
                    )
                except Exception as e:
                    summary["scan_errors"].append(f"{sym}: {sanitize_log_message(str(e))}")
                    continue
                if not isinstance(sym_orders, list):
                    continue
                for o in sym_orders:
                    if isinstance(o, dict):
                        orders_to_eval.append(o)

        summary["open_orders_seen"] = len(orders_to_eval)
        for order in orders_to_eval:
            order_type = str(order.get("type", "")).upper()
            if not _matches_cleanup_mode(order_type, mode_norm):
                continue
            sym = str(order.get("symbol", "")).upper()
            oid = order.get("orderId")
            if not sym or oid is None:
                continue
            try:
                await asyncio.to_thread(client.cancel_order, symbol=sym, orderId=oid)
                _audit_weight_from_client(
                    ctx,
                    client,
                    source="ops",
                    action=f"cleanup:cancel_order:{sym}",
                )
                summary["orders_canceled"] += 1
            except Exception as e:
                summary["cancel_errors"].append(f"{sym}#{oid}: {sanitize_log_message(str(e))}")

        if summary["stop_errors"] or summary["scan_errors"] or summary["cancel_errors"]:
            summary["status"] = "partial"
        summary["log_lines"].append(
            f"Cleanup mode={mode_norm}: seen={summary['open_orders_seen']}, canceled={summary['orders_canceled']}."
        )
    except BinanceAPIException as e:
        summary["status"] = "failed"
        summary["error"] = sanitize_log_message(str(e))
        summary["log_lines"].append(f"Binance API error: {summary['error']}")
    except Exception as e:
        summary["status"] = "failed"
        summary["error"] = sanitize_log_message(str(e))
        summary["log_lines"].append(f"Unexpected error: {summary['error']}")
    finally:
        try:
            await asyncio.to_thread(client.close_connection)
        except Exception:
            pass

    summary["elapsed_sec"] = round(time.time() - started_at, 3)
    return summary


def _sandbox_db_path(ctx: AppContext):
    return ctx.config.data_dir / "sandbox_curated.sqlite"


def _sandbox_db_init(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sandbox_curated_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc TEXT NOT NULL,
            method TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            request_json TEXT NOT NULL,
            response_json TEXT NOT NULL,
            curated_json TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _sandbox_curated_save(ctx: AppContext, payload: dict[str, Any]) -> dict[str, Any]:
    method = str(payload.get("method", "GET")).strip().upper() or "GET"
    endpoint = str(payload.get("endpoint", "")).strip()
    if not endpoint.startswith("/"):
        raise HTTPException(status_code=400, detail="endpoint must start with '/'")
    request_obj = payload.get("request", {})
    response_obj = payload.get("response", {})
    curated_obj = payload.get("curated", {})
    ts_utc = datetime.now(timezone.utc).isoformat()
    db_path = _sandbox_db_path(ctx)
    with _SANDBOX_DB_LOCK:
        conn = sqlite3.connect(db_path)
        try:
            _sandbox_db_init(conn)
            cur = conn.execute(
                """
                INSERT INTO sandbox_curated_records
                (ts_utc, method, endpoint, request_json, response_json, curated_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    ts_utc,
                    method,
                    endpoint,
                    json.dumps(request_obj, ensure_ascii=True),
                    json.dumps(response_obj, ensure_ascii=True),
                    json.dumps(curated_obj, ensure_ascii=True),
                ),
            )
            conn.commit()
            row_id = int(cur.lastrowid or 0)
        finally:
            conn.close()
    return {
        "id": row_id,
        "ts_utc": ts_utc,
        "method": method,
        "endpoint": endpoint,
        "db_path": str(db_path),
    }


def _sandbox_curated_list(ctx: AppContext, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 500))
    db_path = _sandbox_db_path(ctx)
    with _SANDBOX_DB_LOCK:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            _sandbox_db_init(conn)
            rows = conn.execute(
                """
                SELECT id, ts_utc, method, endpoint, request_json, response_json, curated_json
                FROM sandbox_curated_records
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            conn.close()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": int(row["id"]),
                "ts_utc": str(row["ts_utc"]),
                "method": str(row["method"]),
                "endpoint": str(row["endpoint"]),
                "request": json.loads(str(row["request_json"]) or "{}"),
                "response": json.loads(str(row["response_json"]) or "{}"),
                "curated": json.loads(str(row["curated_json"]) or "{}"),
            }
        )
    return out


def _sandbox_rest_catalog() -> list[dict[str, Any]]:
    return [
        {
            "query_id": "historical_klines",
            "title": "Historical Klines",
            "description": "Datos historicos de velas",
            "requires_credentials": False,
            "args": ["symbol (required)", "interval (required)", "start_str (required)"],
            "category": "Market Data",
        },
        {
            "query_id": "symbol_info",
            "title": "Symbol Info",
            "description": "Informacion detallada de un simbolo",
            "requires_credentials": False,
            "args": ["symbol (required)"],
            "category": "Market Data",
        },
        {
            "query_id": "all_tickers",
            "title": "All Tickers",
            "description": "Ultimo precio de todos los simbolos",
            "requires_credentials": False,
            "args": [],
            "category": "Market Data",
        },
        {
            "query_id": "recent_trades",
            "title": "Recent Trades",
            "description": "Trades recientes en el mercado para un simbolo",
            "requires_credentials": False,
            "args": ["symbol (required)"],
            "category": "Market Data",
        },
        {
            "query_id": "asset_balance",
            "title": "Asset Balance",
            "description": "Balance de un activo especifico",
            "requires_credentials": True,
            "args": ["asset (required)"],
            "category": "Account & Trades",
        },
        {
            "query_id": "trade_fee",
            "title": "Trade Fee",
            "description": "Tarifas de trading de un simbolo",
            "requires_credentials": True,
            "args": ["symbol (optional)"],
            "category": "Account & Trades",
        },
        {
            "query_id": "exchange_info",
            "title": "Exchange Info",
            "description": "Retorna reglas de trading y símbolos de Binance",
            "requires_credentials": False,
            "args": ["symbol (optional)"],
            "category": "Market Data",
        },
        {
            "query_id": "server_time",
            "title": "Server Time",
            "description": "Retorna la hora actual del servidor de Binance",
            "requires_credentials": False,
            "args": [],
            "category": "Market Data",
        },
        {
            "query_id": "orderbook_ticker",
            "title": "Orderbook Ticker",
            "description": "Mejor precio bid/ask para un símbolo",
            "requires_credentials": False,
            "args": ["symbol (required)"],
            "category": "Market Data",
        },
        {
            "query_id": "ticker_price",
            "title": "Ticker Price",
            "description": "Último precio transaccionado",
            "requires_credentials": False,
            "args": ["symbol (optional)"],
            "category": "Market Data",
        },
        {
            "query_id": "ticker_24hr",
            "title": "24hr Ticker",
            "description": "Estadísticas de cambio de precio en 24h",
            "requires_credentials": False,
            "args": ["symbol (optional)"],
            "category": "Market Data",
        },
        {
            "query_id": "klines",
            "title": "Klines / Candlesticks",
            "description": "Datos de velas para un símbolo e intervalo",
            "requires_credentials": False,
            "args": ["symbol (required)", "interval (required)"],
            "category": "Market Data",
        },
        {
            "query_id": "account",
            "title": "Spot Account",
            "description": "Balances y estado general de la cuenta Spot",
            "requires_credentials": True,
            "args": [],
            "category": "Account & Trades",
        },
        {
            "query_id": "open_orders",
            "title": "Open Orders",
            "description": "Todas las órdenes abiertas (LIMIT, STOP)",
            "requires_credentials": True,
            "args": ["symbol (optional)"],
            "category": "Account & Trades",
        },
        {
            "query_id": "all_orders",
            "title": "All Orders",
            "description": "Historial de órdenes (abiertas, cerradas, canceladas)",
            "requires_credentials": True,
            "args": ["symbol (required)", "limit (optional)"],
            "category": "Account & Trades",
        },
        {
            "query_id": "my_trades",
            "title": "My Trades",
            "description": "Historial de ejecuciones reales (trades)",
            "requires_credentials": True,
            "args": ["symbol (required)", "limit (optional)"],
            "category": "Account & Trades",
        },
        {
            "query_id": "deposit_history",
            "title": "Deposit History",
            "description": "Historial de depósitos entrantes a la cuenta",
            "requires_credentials": True,
            "args": ["coin (optional)", "status (optional)"],
            "category": "Wallet",
        },
        {
            "query_id": "withdraw_history",
            "title": "Withdraw History",
            "description": "Historial de retiros salientes",
            "requires_credentials": True,
            "args": ["coin (optional)", "status (optional)"],
            "category": "Wallet",
        },
        {
            "query_id": "trade_fee",
            "title": "Trade Fee",
            "description": "Comisiones de trading actuales (VIP, BNB discount)",
            "requires_credentials": True,
            "args": ["symbol (optional)"],
            "category": "Account & Trades",
        },
    ]




def _sandbox_curate_json(response: Any) -> dict[str, Any]:
    def _preview(v: Any) -> str:
        t = str(v)
        return t if len(t) <= 140 else f"{t[:137]}..."

    def _kv_rows(obj: Any, max_items: int = 30) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        if isinstance(obj, dict):
            for i, (k, v) in enumerate(obj.items()):
                if i >= max_items:
                    break
                rows.append(
                    {
                        "key": str(k),
                        "type": type(v).__name__,
                        "value_preview": _preview(v),
                    }
                )
        return rows

    if isinstance(response, dict):
        keys = [str(k) for k in response.keys()]
        list_fields = [k for k, v in response.items() if isinstance(v, list)]
        map_fields = [k for k, v in response.items() if isinstance(v, dict)]
        return {
            "response_type": "dict",
            "top_level_keys": keys,
            "top_level_key_count": len(keys),
            "list_fields": list_fields,
            "map_fields": map_fields,
            "key_value_preview": _kv_rows(response),
        }
    if isinstance(response, list):
        first_type = type(response[0]).__name__ if response else "none"
        first_preview = _kv_rows(response[0]) if response and isinstance(response[0], dict) else []
        return {
            "response_type": "list",
            "list_size": len(response),
            "first_item_type": first_type,
            "first_item_key_value_preview": first_preview,
        }
    return {"response_type": type(response).__name__}


def _sandbox_requires_credentials(query_id: str) -> bool:
    return query_id in {"account", "open_orders", "my_trades"}


async def _sandbox_sync_timestamp(
    client: Client,
    *,
    ctx: AppContext | None = None,
    source: str = "sandbox",
    action: str = "sync_time:get_server_time",
) -> None:
    data = await asyncio.to_thread(client.get_server_time)
    if ctx is not None:
        _audit_weight_from_client(ctx, client, source=source, action=action)
    server_ms = int((data or {}).get("serverTime", 0) or 0)
    local_ms = int(time.time() * 1000)
    try:
        client.timestamp_offset = server_ms - local_ms
    except Exception:
        pass


async def _sandbox_signed_call_with_time_retry(
    client: Client,
    fn,
    *,
    ctx: AppContext | None = None,
    source: str = "sandbox",
    action: str = "signed_call",
) -> Any:
    try:
        out = await asyncio.to_thread(fn)
        if ctx is not None:
            _audit_weight_from_client(ctx, client, source=source, action=action)
        return out
    except BinanceAPIException as e:
        if getattr(e, "code", None) != -1021:
            raise
        await _sandbox_sync_timestamp(client, ctx=ctx, source=source, action="retry_sync:get_server_time")
        out = await asyncio.to_thread(fn)
        if ctx is not None:
            _audit_weight_from_client(ctx, client, source=source, action=f"{action}:retry_after_sync")
        return out


async def _sandbox_rest_query(ctx: AppContext, body: dict[str, Any]) -> dict[str, Any]:
    def _parse_call_expr(call_expr: str) -> dict[str, Any]:
        expr = (call_expr or "").strip().rstrip(";")
        if not expr:
            raise HTTPException(status_code=400, detail="call is required")
        try:
            tree = ast.parse(expr, mode="eval")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid call syntax: {sanitize_log_message(str(e))}") from None
        call = tree.body
        if not isinstance(call, ast.Call):
            raise HTTPException(status_code=400, detail="call must be a function call expression")
        fn = call.func
        method = ""
        if isinstance(fn, ast.Attribute):
            method = str(fn.attr)
        elif isinstance(fn, ast.Name):
            method = str(fn.id)
        method = method.strip()
        method_map = {
            "get_exchange_info": "exchange_info",
            "get_server_time": "server_time",
            "get_account": "account",
            "get_open_orders": "open_orders",
            "get_my_trades": "my_trades",
            "get_orderbook_ticker": "orderbook_ticker",
            "get_symbol_info": "symbol_info",
            "get_all_tickers": "all_tickers",
            "get_historical_klines": "historical_klines",
            "get_klines": "klines",
            "get_recent_trades": "recent_trades",
            "get_asset_balance": "asset_balance",
            "get_trade_fee": "trade_fee",
        }
        query_id = method_map.get(method)
        if not query_id:
            raise HTTPException(status_code=400, detail=f"Unsupported python-binance method: {method}")

        def _literal(node: ast.AST) -> Any:
            if isinstance(node, ast.Constant):
                return node.value
            raise HTTPException(status_code=400, detail="Only literal args are supported in call expression")

        kwargs: dict[str, Any] = {}
        for kw in call.keywords:
            if kw.arg is None:
                raise HTTPException(status_code=400, detail="Unsupported **kwargs in call expression")
            kwargs[str(kw.arg)] = _literal(kw.value)
        args = [_literal(a) for a in call.args]

        out: dict[str, Any] = {"query_id": query_id, "parsed_method": method}
        symbol = kwargs.get("symbol")
        if symbol is None and args:
            if query_id in {"open_orders", "my_trades", "orderbook_ticker"}:
                symbol = args[0]
        if symbol is not None:
            out["symbol"] = str(symbol).strip().upper()
        if "limit" in kwargs:
            out["limit"] = kwargs["limit"]
        out["kwargs"] = kwargs
        out["args"] = args
        return out

    query_id = str((body or {}).get("query_id", "")).strip().lower()
    call_expr = str((body or {}).get("call", "")).strip()
    parsed_call: dict[str, Any] = {}
    if call_expr:
        parsed_call = _parse_call_expr(call_expr)
        if not query_id:
            query_id = str(parsed_call.get("query_id", "")).strip().lower()
    if not query_id:
        raise HTTPException(status_code=400, detail="query_id or call is required")
    catalog_ids = {row["query_id"] for row in _sandbox_rest_catalog()}
    if query_id not in catalog_ids:
        raise HTTPException(status_code=400, detail=f"Unsupported query_id: {query_id}")

    query_id = query_id or str(parsed_call.get("query_id", ""))
    
    # Extraer kwargs y args parseados (si existen) o desde el body
    p_kwargs = parsed_call.get("kwargs", {})
    p_args = parsed_call.get("args", [])
    
    symbol = str((body or {}).get("symbol", parsed_call.get("symbol", ""))).strip().upper()
    limit_raw = (body or {}).get("limit", parsed_call.get("limit", 50))
    try:
        limit = max(1, min(int(limit_raw), 1000))
    except Exception:
        limit = 50

    requires_credentials = _sandbox_requires_credentials(query_id)
    pair = _resolve_pair(ctx) if requires_credentials else None
    if requires_credentials and not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")

    client = Client(
        pair[0] if pair else "",
        pair[1] if pair else "",
        requests_params={"timeout": 20},
    )
    try:
        if requires_credentials:
            await _sandbox_sync_timestamp(
                client,
                ctx=ctx,
                source="sandbox",
                action="sandbox:sync_time:get_server_time",
            )

        if query_id == "exchange_info":
            response = await asyncio.to_thread(client.get_exchange_info)
            _audit_weight_from_client(
                ctx,
                client,
                source="sandbox",
                action="sandbox:get_exchange_info",
            )
            if symbol and isinstance(response, dict):
                rows = response.get("symbols", [])
                if isinstance(rows, list):
                    response = {
                        **response,
                        "symbols": [r for r in rows if str((r or {}).get("symbol", "")).upper() == symbol],
                    }
        elif query_id == "server_time":
            response = await asyncio.to_thread(client.get_server_time)
            _audit_weight_from_client(
                ctx,
                client,
                source="sandbox",
                action="sandbox:get_server_time",
            )
        elif query_id == "account":
            response = await _sandbox_signed_call_with_time_retry(
                client,
                client.get_account,
                ctx=ctx,
                source="sandbox",
                action="sandbox:get_account",
            )
        elif query_id == "symbol_info":
            if not symbol:
                raise HTTPException(status_code=400, detail="symbol is required")
            response = await asyncio.to_thread(client.get_symbol_info, symbol=symbol)
            _audit_weight_from_client(ctx, client, source="sandbox", action="sandbox:get_symbol_info")
        elif query_id == "all_tickers":
            response = await asyncio.to_thread(client.get_all_tickers)
            _audit_weight_from_client(ctx, client, source="sandbox", action="sandbox:get_all_tickers")
        elif query_id == "historical_klines":
            interval = p_kwargs.get("interval") or (body or {}).get("interval")
            start_str = p_kwargs.get("start_str") or (body or {}).get("start_str")
            if not symbol or not interval or not start_str:
                raise HTTPException(status_code=400, detail="symbol, interval, and start_str are required")
            response = await asyncio.to_thread(client.get_historical_klines, symbol=symbol, interval=interval, start_str=start_str)
            _audit_weight_from_client(ctx, client, source="sandbox", action="sandbox:get_historical_klines")
        elif query_id == "klines":
            interval = p_kwargs.get("interval") or (body or {}).get("interval")
            start_time = p_kwargs.get("startTime") or p_kwargs.get("startTime")
            end_time = p_kwargs.get("endTime") or p_kwargs.get("endTime")
            if not symbol or not interval:
                raise HTTPException(status_code=400, detail="symbol and interval are required")
            # Build kw args dynamically
            k_kwargs = {"symbol": symbol, "interval": interval, "limit": limit}
            if start_time: k_kwargs["startTime"] = start_time
            if end_time: k_kwargs["endTime"] = end_time
            response = await asyncio.to_thread(client.get_klines, **k_kwargs)
            _audit_weight_from_client(ctx, client, source="sandbox", action="sandbox:get_klines")
        elif query_id == "recent_trades":
            if not symbol:
                raise HTTPException(status_code=400, detail="symbol is required")
            response = await asyncio.to_thread(client.get_recent_trades, symbol=symbol, limit=limit)
            _audit_weight_from_client(ctx, client, source="sandbox", action="sandbox:get_recent_trades")
        elif query_id == "asset_balance":
            asset = p_kwargs.get("asset") or (body or {}).get("asset")
            if not asset and p_args:
                asset = p_args[0]
            if not asset:
                raise HTTPException(status_code=400, detail="asset is required")
            response = await _sandbox_signed_call_with_time_retry(
                client,
                lambda: client.get_asset_balance(asset=asset),
                ctx=ctx,
                source="sandbox",
                action="sandbox:get_asset_balance",
            )
        elif query_id == "trade_fee":
            response = await _sandbox_signed_call_with_time_retry(
                client,
                lambda: client.get_trade_fee(symbol=symbol) if symbol else client.get_trade_fee(),
                ctx=ctx,
                source="sandbox",
                action="sandbox:get_trade_fee",
            )
        elif query_id == "open_orders":
            if symbol:
                response = await _sandbox_signed_call_with_time_retry(
                    client,
                    lambda: client.get_open_orders(symbol=symbol),
                    ctx=ctx,
                    source="sandbox",
                    action=f"sandbox:get_open_orders:{symbol}",
                )
            else:
                response = await _sandbox_signed_call_with_time_retry(
                    client,
                    client.get_open_orders,
                    ctx=ctx,
                    source="sandbox",
                    action="sandbox:get_open_orders",
                )
        elif query_id == "my_trades":
            if not symbol:
                raise HTTPException(status_code=400, detail="symbol is required for my_trades")
            response = await _sandbox_signed_call_with_time_retry(
                client,
                lambda: client.get_my_trades(symbol=symbol, limit=limit),
                ctx=ctx,
                source="sandbox",
                action=f"sandbox:get_my_trades:{symbol}",
            )
        elif query_id == "orderbook_ticker":
            if not symbol:
                raise HTTPException(status_code=400, detail="symbol is required for orderbook_ticker")
            response = await asyncio.to_thread(client.get_orderbook_ticker, symbol=symbol)
            _audit_weight_from_client(
                ctx,
                client,
                source="sandbox",
                action=f"sandbox:get_orderbook_ticker:{symbol}",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported query_id: {query_id}")

        curated = _sandbox_curate_json(response)
        return {
            "query_id": query_id,
            "call": call_expr or None,
            "used_credentials": requires_credentials,
            "args": {"symbol": symbol or None, "limit": limit},
            "response": response,
            "curated": curated,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except BinanceAPIException as e:
        raise HTTPException(
            status_code=502,
            detail=sanitize_log_message(str(e)),
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=sanitize_log_message(str(e)),
        ) from None
    finally:
        try:
            await asyncio.to_thread(client.close_connection)
        except Exception:
            pass


def _resolve_pair(
    ctx: AppContext,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> tuple[str, str] | None:
    ak = (api_key or "").strip()
    sec = (api_secret or "").strip()
    if ak and sec:
        ctx.active_api_key_hint = _mask_pk(ak)
        ctx.active_api_key_last4 = _pk_last4(ak)
        ctx.active_api_key_source = "inline"
        return ak, sec
    pair = binance_credentials_from_env()
    if pair:
        ctx.active_api_key_hint = _mask_pk(pair[0])
        ctx.active_api_key_last4 = _pk_last4(pair[0])
        ctx.active_api_key_source = "env"
        return pair
    try:
        pair = ctx.config.get_pair_for_active()
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    if pair:
        ctx.active_api_key_hint = _mask_pk(pair[0])
        ctx.active_api_key_last4 = _pk_last4(pair[0])
        ctx.active_api_key_source = "vault"
    return pair


async def _execute_terminal_command(
    ctx: AppContext,
    command: str,
) -> str:
    cmd = " ".join((command or "").strip().split())
    if not cmd:
        return ""
    parts = cmd.split()
    key = parts[0].lower()
    rest = parts[1:]
    bot = deps.get_bot()

    if key in ("help", "?"):
        return (
            "Commands:\n"
            "  help\n"
            "  health\n"
            "  time sync\n"
            "  vault status\n"
            "  gateway start|stop|snapshot|fetch\n"
            "  bot status|start|stop|run_once\n"
            "  ops status|close|red_button|cleanup_limit|cleanup_stop|cleanup_all\n"
            "  account\n"
            "  balances\n"
            "  open_orders\n"
            "  my_trades [SYMBOL]\n"
            "  price SYMBOL"
        )

    if key == "health":
        return "ok"

    if key == "time":
        if not rest or rest[0].lower() != "sync":
            return "usage: time sync"
        payload = await _sync_binance_time(ctx)
        return (
            f"time synced ({payload['source']}): local={payload['local_time_ms']} "
            f"server={payload['server_time_ms']} offset_ms={payload['offset_ms']}"
        )

    if key == "vault":
        if not rest:
            return "usage: vault status"
        sub = rest[0].lower()
        if sub == "status":
            pubs = ctx.config.list_public_credentials()
            return (
                f"vault_exists={ctx.config.exists()} rows={len(pubs)} "
                f"active={ctx.config.get_active_credential_id() or '-'}"
            )
        return "usage: vault status"

    if key == "gateway":
        if not rest:
            return "usage: gateway start|stop|snapshot|fetch"
        sub = rest[0].lower()
        if sub == "start":
            pair = _resolve_pair(ctx)
            if not pair:
                return "no credentials available"
            if ctx.gateway:
                await ctx.gateway.stop()
                ctx.gateway = None
            gw = BinanceGateway(pair[0], pair[1], ctx.bus, ctx.state, ctx.log_line, ctx.config.data_dir)
            try:
                await gw.start()
                await gw.sync_time()
                await gw.fetch_account()
            except Exception as e:
                try:
                    await gw.stop()
                except Exception:
                    pass
                return sanitize_log_message(str(e))
            ctx.gateway = gw
            return "gateway started"
        if sub == "stop":
            if ctx.gateway:
                await ctx.gateway.stop()
                ctx.gateway = None
            return "gateway stopped"
        if sub == "snapshot":
            s = _snapshot(ctx)
            return (
                f"running={s.gateway_running} ws={s.ws_connected} "
                f"balances={len(s.balances)} last_error={s.last_error or '-'}"
            )
        if sub == "fetch":
            if not ctx.gateway:
                return "gateway not running"
            await ctx.gateway.fetch_account()
            return f"account refreshed; balances={len(ctx.state.balances)}"
        return "usage: gateway start|stop|snapshot|fetch"

    if key == "bot":
        if not rest:
            return "usage: bot status|start|stop|run_once"
        sub = rest[0].lower()
        if sub == "status":
            st = bot.status_payload()
            return (
                f"running={st['running']} simulated={st['simulated']} "
                f"trading_enabled={st['trading_enabled']} symbol={st['symbol']}"
            )
        if sub in ("start", "run_once"):
            pair = _resolve_pair(ctx)
            if not pair:
                return "no credentials available"
            bot.runner.set_credentials(pair[0], pair[1])
            try:
                if sub == "start":
                    await bot.runner.sync_time()
                    await bot.runner.start()
                    return "bot loop started"
                await bot.runner.sync_time()
                rep = await bot.runner.run_once()
                bot.mark_run_once(rep, error=None)
                return f"run_once: {rep.get('decision', '-')}"
            except Exception as e:
                msg = sanitize_log_message(str(e))
                bot.mark_run_once({}, error=msg)
                return msg
        if sub == "stop":
            await bot.runner.stop()
            return "bot loop stopped"
        return "usage: bot status|start|stop|run_once"

    if key == "ops":
        if not rest:
            return "usage: ops status|close|red_button|cleanup_limit|cleanup_stop|cleanup_all"
        sub = rest[0].lower()
        if sub == "status":
            audit = get_ops_audit_log(ctx.config.data_dir)
            close_state = audit.last("close_protocol")
            red_state = audit.last("red_button")
            return (
                f"close={close_state.get('status') if close_state else '-'} "
                f"red_button={red_state.get('status') if red_state else '-'}"
            )
        if sub == "close":
            rep = await _execute_close_protocol(ctx)
            get_ops_audit_log(ctx.config.data_dir).record(
                op_name="close_protocol",
                status=str(rep.get("status", "unknown")),
                summary=rep,
                error=str(rep.get("error", "")).strip() or None,
            )
            return f"close protocol: {rep.get('status', '-')}"
        if sub == "red_button":
            rep = await _execute_red_button(ctx)
            get_ops_audit_log(ctx.config.data_dir).record(
                op_name="red_button",
                status=str(rep.get("status", "unknown")),
                summary=rep,
                error=str(rep.get("error", "")).strip() or None,
            )
            return f"red button: {rep.get('status', '-')}"
        if sub == "cleanup_limit":
            rep = await _execute_order_cleanup(ctx, mode="limit")
            get_ops_audit_log(ctx.config.data_dir).record(
                op_name="cancel_limit_orders_cleanup",
                status=str(rep.get("status", "unknown")),
                summary=rep,
                error=str(rep.get("error", "")).strip() or None,
            )
            return f"cleanup limit: {rep.get('status', '-')}"
        if sub == "cleanup_stop":
            rep = await _execute_order_cleanup(ctx, mode="stop")
            get_ops_audit_log(ctx.config.data_dir).record(
                op_name="cancel_stop_orders_cleanup",
                status=str(rep.get("status", "unknown")),
                summary=rep,
                error=str(rep.get("error", "")).strip() or None,
            )
            return f"cleanup stop: {rep.get('status', '-')}"
        if sub == "cleanup_all":
            rep = await _execute_order_cleanup(ctx, mode="all")
            get_ops_audit_log(ctx.config.data_dir).record(
                op_name="cancel_all_orders_cleanup",
                status=str(rep.get("status", "unknown")),
                summary=rep,
                error=str(rep.get("error", "")).strip() or None,
            )
            return f"cleanup all: {rep.get('status', '-')}"
        return "usage: ops status|close|red_button|cleanup_limit|cleanup_stop|cleanup_all"

    if key == "account":
        if not ctx.gateway:
            return "gateway not running"
        await ctx.gateway.fetch_account()
        s = ctx.state.account_summary or {}
        return (
            f"accountType={s.get('accountType', '-')} "
            f"canTrade={s.get('canTrade', '-')} "
            f"balances_non_zero={len(ctx.state.balances)}"
        )

    if key == "balances":
        if not ctx.gateway:
            return "gateway not running"
        await ctx.gateway.fetch_account()
        if not ctx.state.balances:
            return "(empty)"
        lines = [
            f"{b.get('asset','?'):6} free={b.get('free','0'):>14} locked={b.get('locked','0'):>14}"
            for b in ctx.state.balances
        ]
        return "\n".join(lines)

    if key == "open_orders":
        if not ctx.gateway:
            return "gateway not running"
        await ctx.gateway.fetch_open_orders()
        ods = ctx.state.open_orders
        if not ods:
            return "(no open orders)"
        return "\n".join(
            f"{o.get('symbol')} {o.get('side')} {o.get('type')} qty={o.get('origQty')} price={o.get('price')}"
            for o in ods
        )

    if key == "my_trades":
        if not ctx.gateway:
            return "gateway not running"
        sym = rest[0] if rest else ctx.state.selected_symbol
        try:
            await ctx.gateway.fetch_my_trades(sym)
        except Exception as e:
            return sanitize_log_message(str(e))
        mts = ctx.state.my_trades
        if not mts:
            return "(no trades)"
        lines = [
            f"{t.get('time')} {'BUY' if t.get('isBuyer') else 'SELL'} qty={t.get('qty')} price={t.get('price')}"
            for t in mts[-20:]
        ]
        return "\n".join(lines)

    if key == "price":
        if len(rest) < 1:
            return "usage: price SYMBOL"
        if not ctx.gateway:
            return "gateway not running"
        bk = await ctx.gateway.fetch_book_ticker(rest[0])
        if not bk:
            return "could not fetch bookTicker"
        return f"{rest[0].upper()} bid={bk.get('bidPrice')} ask={bk.get('askPrice')}"

    return f"unknown command: {key}. type 'help'."


async def _sync_binance_time(
    ctx: AppContext,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> dict[str, Any]:
    bot = deps.get_bot()
    if ctx.gateway:
        payload = await ctx.gateway.sync_time()
        ctx.state.binance_server_time_ms = int(payload.get("server_time_ms", 0) or 0)
        ctx.state.binance_local_time_ms_at_sync = int(
            payload.get("local_time_ms", 0) or 0
        )
        ctx.state.binance_offset_ms = int(payload.get("offset_ms", 0) or 0)
        ctx.state.binance_time_synced_at_utc = datetime.now(
            timezone.utc
        ).isoformat()
        if bot.runner.running:
            try:
                await bot.runner.sync_time()
            except Exception:
                pass
        return payload

    pair = _resolve_pair(ctx, api_key, api_secret)
    if not pair:
        raise HTTPException(status_code=400, detail="No API credentials available")

    client = Client(pair[0], pair[1], requests_params={"timeout": 10})
    try:
        data = await asyncio.to_thread(client.get_server_time)
        _audit_weight_from_client(ctx, client, source="time_sync", action="time_sync:get_server_time")
        server_ms = int(data.get("serverTime", 0) or 0)
        local_ms = int(time.time() * 1000)
        offset_ms = server_ms - local_ms
        try:
            client.timestamp_offset = offset_ms
        except Exception:
            pass
        if bot.runner.running:
            try:
                await bot.runner.sync_time()
            except Exception:
                pass
        ctx.state.binance_server_time_ms = server_ms
        ctx.state.binance_local_time_ms_at_sync = local_ms
        ctx.state.binance_offset_ms = offset_ms
        ctx.state.binance_time_synced_at_utc = datetime.now(
            timezone.utc
        ).isoformat()
        return {
            "source": "one_shot",
            "local_time_ms": local_ms,
            "server_time_ms": server_ms,
            "offset_ms": offset_ms,
        }
    except Exception as e:
        msg = sanitize_log_message(str(e))
        raise HTTPException(status_code=502, detail=msg) from None
    finally:
        try:
            await asyncio.to_thread(client.close_connection)
        except Exception:
            pass

