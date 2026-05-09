"""Terminal commands execution engine for the Flutter UI."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from runtime.api._helpers import resolve_pair
from runtime.app import AppContext
from runtime.core.ops_audit_log import get_ops_audit_log
from runtime.core.security_util import sanitize_log_message
from runtime.api.ops_protocol import (
    _execute_close_protocol,
    _execute_red_button,
    _execute_order_cleanup,
)


async def _execute_terminal_command(ctx: AppContext, command: str) -> str:
    if not command or not command.strip():
        return ""
    parts = command.strip().split()
    key = parts[0].lower()
    rest = parts[1:]

    if key in ["ping", "hello"]:
        return "pong"

    if key == "ops":
        if not rest:
            return "usage: ops status|close|red_button|cleanup_limit|cleanup_stop|cleanup_all"
        sub = rest[0].lower()
        if sub == "status":
            try:
                pair = resolve_pair(ctx)
            except HTTPException:
                pair = None
            return f"api ready: {'yes' if pair else 'no'}"
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
