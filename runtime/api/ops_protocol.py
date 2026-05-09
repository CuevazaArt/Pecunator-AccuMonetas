"""Operations protocols — close, red button, order cleanup.

Extracted from the app.py monolith.  All functions retain their original
underscore-prefixed names so that lazy ``from runtime.api.app import _X``
imports still work through the re-export shim in ``app.py``.
"""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any

from binance.client import Client
from binance.exceptions import BinanceAPIException
from fastapi import HTTPException

from runtime.api import deps
from runtime.api._helpers import audit_weight_from_client, resolve_pair
from runtime.app import AppContext
from runtime.core.equity import build_ticker_price_map, compute_spot_equity_in_base
from runtime.core.security_util import sanitize_log_message


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
    pair = resolve_pair(ctx)
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
        audit_weight_from_client(ctx, client, source="ops", action="close_protocol:get_open_orders")
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
                audit_weight_from_client(
                    ctx, client, source="ops",
                    action=f"close_protocol:cancel_order:{sym}",
                )
                summary["limit_orders_canceled"] += 1
            except Exception as e:
                summary["cancel_errors"].append(f"{sym}#{oid}: {sanitize_log_message(str(e))}")

        account = await asyncio.to_thread(client.get_account)
        audit_weight_from_client(ctx, client, source="ops", action="close_protocol:get_account")
        balances = account.get("balances", []) if isinstance(account, dict) else []
        tickers = await asyncio.to_thread(client.get_all_tickers)
        audit_weight_from_client(ctx, client, source="ops", action="close_protocol:get_all_tickers")
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
    pair = resolve_pair(ctx)
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
        audit_weight_from_client(ctx, client, source="ops", action="red_button:get_account")
        balances = account.get("balances", []) if isinstance(account, dict) else []
        if not isinstance(balances, list):
            balances = []

        exch = await asyncio.to_thread(client.get_exchange_info)
        audit_weight_from_client(ctx, client, source="ops", action="red_button:get_exchange_info")
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
                audit_weight_from_client(
                    ctx, client, source="ops",
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
                        audit_weight_from_client(
                            ctx, client, source="ops",
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
                audit_weight_from_client(
                    ctx, client, source="ops",
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
        "STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT",
        "STOP", "STOP_MARKET", "TAKE_PROFIT_MARKET",
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
    pair = resolve_pair(ctx)
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
            audit_weight_from_client(ctx, client, source="ops", action="cleanup:get_open_orders")
            if isinstance(account_orders, list):
                orders_to_eval = [o for o in account_orders if isinstance(o, dict)]
        else:
            account = await asyncio.to_thread(client.get_account)
            audit_weight_from_client(ctx, client, source="ops", action="cleanup:get_account")
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
                    audit_weight_from_client(
                        ctx, client, source="ops",
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
                audit_weight_from_client(
                    ctx, client, source="ops",
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
