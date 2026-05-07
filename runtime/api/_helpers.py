"""Shared helpers for API routers.

These were previously inline in app.py.  Extracted so routers can import them
without circular dependencies.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from runtime.api import deps
from runtime.api.schemas import GatewaySnapshotOut
from runtime.app import AppContext
from runtime.core.settings import (
    account_poll_interval_sec,
    api_weight_limit_1m_display,
    binance_credentials_from_env,
    equity_poll_stride,
    my_trades_poll_stride,
)

_LOG = logging.getLogger("pecunator.api.helpers")


# ── Credential helpers ──────────────────────────────────────────────

def mask_pk(pk: str) -> str:
    s = pk.strip()
    return s if len(s) <= 24 else f"{s[:14]}...{s[-6:]}"


def pk_last4(pk: str) -> str:
    s = (pk or "").strip()
    return s[-4:] if len(s) >= 4 else s


def resolve_pair(
    ctx: AppContext,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> tuple[str, str] | None:
    ak = (api_key or "").strip()
    sec = (api_secret or "").strip()
    if ak and sec:
        ctx.active_api_key_hint = mask_pk(ak)
        ctx.active_api_key_last4 = pk_last4(ak)
        ctx.active_api_key_source = "inline"
        return ak, sec
    pair = binance_credentials_from_env()
    if pair:
        ctx.active_api_key_hint = mask_pk(pair[0])
        ctx.active_api_key_last4 = pk_last4(pair[0])
        ctx.active_api_key_source = "env"
        return pair
    try:
        pair = ctx.config.get_pair_for_active()
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from None
    if pair:
        ctx.active_api_key_hint = mask_pk(pair[0])
        ctx.active_api_key_last4 = pk_last4(pair[0])
        ctx.active_api_key_source = "vault"
    return pair


# ── Snapshot builder ────────────────────────────────────────────────

def build_snapshot(ctx: AppContext) -> GatewaySnapshotOut:
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
    except Exception as exc:
        _LOG.debug("rest_usage_log recording skipped: %s", exc)
    return out


# ── Weight audit ────────────────────────────────────────────────────

def audit_weight_from_client(
    ctx: AppContext,
    client: Any,
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
        except Exception as exc:
            _LOG.debug("WeightGovernor feed skipped: %s", exc)
        # Feed real-time weight to the Coordinator for launch decisions
        try:
            from runtime.core.bot_coordinator import get_bot_coordinator
            get_bot_coordinator().update_weight(used)
        except Exception as exc:
            _LOG.debug("BotCoordinator feed skipped: %s", exc)
    except Exception as exc:
        _LOG.warning("audit_weight_from_client failed: %s", exc)


# ── REST weight estimate ────────────────────────────────────────────

def rest_weight_estimate_report() -> dict[str, Any]:
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
