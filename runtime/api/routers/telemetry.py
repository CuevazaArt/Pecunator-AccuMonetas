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


# ── Equity History ──────────────────────────────────────────────────

@router.get("/api/v1/equity/history")
async def equity_history(
    minutes: int = 60,
    limit: int = 500,
    ctx: AppContext = Depends(deps.get_ctx),
) -> dict[str, Any]:
    """Return recent equity snapshots aggregated across all bots.

    The Flutter MiniEquityChart calls this on init to seed its graph
    with historical data instead of starting from zero.
    """
    import datetime as _dt
    import sqlite3
    from pathlib import Path

    points: list[dict[str, Any]] = []
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=minutes)).isoformat()
    data_dir = Path(ctx.config.data_dir)

    for db_file, pfx in [("dorothy_hub.sqlite", "dorothy"), ("elphaba_hub.sqlite", "elphaba")]:
        db_path = data_dir / db_file
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path), timeout=2)
            try:
                rows = conn.execute(
                    f"""
                    SELECT ts_utc, equity_usdt, capital_usdt
                    FROM {pfx}_equity_snapshots
                    WHERE ts_utc >= ?
                    ORDER BY ts_utc DESC
                    LIMIT ?
                    """,
                    (cutoff, limit),
                ).fetchall()
                for r in rows:
                    points.append({
                        "ts": r[0],
                        "equity": r[1],
                        "capital": r[2],
                        "source": pfx,
                    })
            finally:
                conn.close()
        except Exception:
            pass

    # Sort chronologically and deduplicate by timestamp (take max equity)
    seen: dict[str, dict[str, Any]] = {}
    for p in points:
        ts = p["ts"]
        eq = float(p.get("equity") or 0)
        if ts not in seen or eq > float(seen[ts].get("equity") or 0):
            seen[ts] = p
    result = sorted(seen.values(), key=lambda x: x["ts"])[-limit:]

    return {"points": result, "count": len(result), "minutes": minutes}


