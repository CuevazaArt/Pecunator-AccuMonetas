"""Telemetry & API usage observability router.

Extracted from the system.py monolith to improve navigability.
Covers: api-log, REST weight usage, rest-weight samples/events/report.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from runtime.api import deps
from runtime.api._helpers import rest_weight_estimate_report
from runtime.app import AppContext
from runtime.core.settings import api_weight_limit_1m_display, account_poll_interval_sec

router = APIRouter(tags=["telemetry"])


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
