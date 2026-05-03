"""System observability router: health, fuse, governor, coordinator, api-log."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends

from runtime.api import deps
from runtime.api._helpers import rest_weight_estimate_report
from runtime.api.schemas import GatewaySnapshotOut
from runtime.app import AppContext
from runtime.core.settings import api_weight_limit_1m_display, account_poll_interval_sec

router = APIRouter(tags=["system"])


# ── Health ──────────────────────────────────────────────────────────

@router.get("/health")
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


@router.get("/health/deep")
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


# ── Gateway Settings ────────────────────────────────────────────────

@router.get("/gateway/settings")
async def get_gateway_settings() -> dict[str, Any]:
    """Return current gateway settings from persistent JSON."""
    from runtime.core.settings import load_gateway_settings
    return load_gateway_settings()


@router.post("/gateway/settings")
async def update_gateway_settings(body: dict[str, Any]) -> dict[str, Any]:
    """Update gateway settings and persist to JSON."""
    from runtime.core.settings import load_gateway_settings, save_gateway_settings
    current = load_gateway_settings()
    current.update(body)
    save_gateway_settings(current)
    return {"ok": True, "settings": load_gateway_settings()}


# ── API Fuse ────────────────────────────────────────────────────────

@router.get("/api-fuse/status")
async def api_fuse_status() -> dict[str, Any]:
    from runtime.core.api_fuse import get_api_fuse
    fuse = get_api_fuse()
    return {
        "tripped": fuse.is_tripped(),
        "remaining_cooldown_sec": round(fuse.remaining_cooldown_sec(), 1),
        "status": fuse.status(),
    }


@router.post("/api-fuse/reset")
async def api_fuse_reset() -> dict[str, Any]:
    from runtime.core.api_fuse import get_api_fuse
    fuse = get_api_fuse()
    fuse.manual_reset()
    return {
        "reset": True,
        "tripped": fuse.is_tripped(),
        "status": fuse.status(),
    }


# ── Weight Governor ─────────────────────────────────────────────────

@router.get("/api/v1/weight-governor/status")
async def weight_governor_status() -> dict[str, Any]:
    from runtime.core.weight_governor import get_weight_governor
    gov = get_weight_governor()
    return gov.status()


# ── Market Cache ────────────────────────────────────────────────────

@router.get("/api/v1/market-cache/status")
async def market_cache_status() -> dict[str, Any]:
    from runtime.core.market_cache import get_market_cache
    cache = get_market_cache()
    return cache.status()


# ── Bot Coordinator ─────────────────────────────────────────────────

@router.get("/api/v1/bot-coordinator/status")
async def bot_coordinator_status() -> dict[str, Any]:
    from runtime.core.bot_coordinator import get_bot_coordinator
    coord = get_bot_coordinator()
    return coord.status()


# ── API Log ─────────────────────────────────────────────────────────

@router.get("/api-log/recent")
async def api_log_recent(
    limit: int = 200,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.core.binance_api_log import get_binance_api_log
    log = get_binance_api_log(ctx.config.data_dir)
    return {"items": log.recent(limit=limit)}


@router.get("/api-log/weight-summary")
async def api_log_weight_summary(ctx: AppContext = Depends(deps.get_ctx)) -> dict[str, Any]:
    from runtime.core.binance_api_log import get_binance_api_log
    log = get_binance_api_log(ctx.config.data_dir)
    return log.weight_summary()


@router.get("/api-log/db-stats")
async def get_api_log_db_stats(ctx: AppContext = Depends(deps.get_ctx)) -> dict[str, Any]:
    """Return API log database statistics."""
    from runtime.core.binance_api_log import get_binance_api_log
    log = get_binance_api_log(ctx.config.data_dir)
    return log.db_stats()


# ── Usage REST weight ───────────────────────────────────────────────

@router.get("/api/v1/usage/rest-weight/samples")
async def usage_rest_weight_samples(
    limit: int = 200,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.core.rest_usage_log import get_rest_usage_log
    rows = get_rest_usage_log(ctx.config.data_dir).list_samples(limit=limit)
    return {"items": rows}


@router.get("/api/v1/usage/rest-weight/events")
async def usage_rest_weight_events(
    limit: int = 300,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    from runtime.core.rest_usage_log import get_rest_usage_log
    rows = get_rest_usage_log(ctx.config.data_dir).list_events(limit=limit)
    return {"items": rows}


@router.get("/api/v1/usage/rest-weight/report")
async def usage_rest_weight_report(ctx: AppContext = Depends(deps.get_ctx)) -> dict[str, Any]:
    from runtime.core.rest_usage_log import get_rest_usage_log
    usage = get_rest_usage_log(ctx.config.data_dir)
    return {
        "now": {
            "used_weight_1m": getattr(ctx.state, "api_weight_used_1m", None),
            "weight_limit_1m": api_weight_limit_1m_display(),
        },
        "polling_config": {
            "account_poll_sec": account_poll_interval_sec(),
            "my_trades_stride": rest_weight_estimate_report().get("cycles_per_min", 0),
            "equity_stride": rest_weight_estimate_report().get("cycles_per_min", 0),
        },
        "estimated_calls_per_min": rest_weight_estimate_report(),
        "top_actions": usage.summary_by_action(limit=5000)[:25],
        "notes": [
            "X-MBX-USED-WEIGHT-1M is IP-scoped and cumulative in a rolling 1-minute window.",
            "Totals include calls from this engine and any other process sharing the same outbound IP.",
            "A window reset can make per-call deltas unavailable for a sample.",
        ],
    }
