"""Simple command line for the embedded terminal (MVP)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional

from runtime.connectors.binance_gateway import BinanceGateway, normalize_binance_spot_symbol
from runtime.core.state_store import StateStore


@dataclass
class TerminalContext:
    state: StateStore
    gateway: Optional[BinanceGateway]
    logs: Deque[str]


HelpText = """
Commands:
  help              Show this message
  balances          Refresh and show non-zero balances (REST)
  open_orders       List open orders (REST)
  my_trades [SYM]   Recent fills for symbol (default: selected pair)
  price SYM         Best bid/ask via REST bookTicker
  orderbook [SYM]   Show top of book from state (symbol optional)
  symbol SYM        Set active trading pair (e.g. BTCUSDT) and reconnect WS
  logs [N]          Print last N runtime log lines (default 30)
""".strip()


def _format_orderbook(state: StateStore, symbol: str) -> str:
    ob = state.orderbook
    bids = ob.get("bids") or []
    asks = ob.get("asks") or []
    lines: List[str] = [f"Order book {symbol} (up to 10 levels)", "--- asks ---"]
    for a in reversed(asks[-10:]):
        lines.append(f"{a[0]:>16}  {a[1]}")
    lines.append("--- bids ---")
    for b in bids[:10]:
        lines.append(f"{b[0]:>16}  {b[1]}")
    return "\n".join(lines)


async def run_command(line: str, ctx: TerminalContext) -> str:
    parts = line.strip().split()
    if not parts:
        return ""
    cmd = parts[0].lower()
    rest = parts[1:]

    if cmd in ("help", "?"):
        return HelpText

    if cmd == "logs":
        n = 30
        if rest:
            try:
                n = max(1, min(200, int(rest[0])))
            except ValueError:
                return "usage: logs [N]"
        return "\n".join(list(ctx.logs)[-n:]) or "(no logs yet)"

    if ctx.gateway is None:
        return "Gateway offline. Unlock credentials and start the runtime from the dashboard."

    gw = ctx.gateway

    if cmd == "balances":
        await gw.fetch_account()
        rows = [
            f"{b['asset']:6} free={b['free']:>14} locked={b['locked']:>14}"
            for b in ctx.state.balances
        ]
        return "\n".join(rows) if rows else "(empty)"

    if cmd == "open_orders":
        await gw.fetch_open_orders()
        ods = ctx.state.open_orders
        if not ods:
            return "(no open orders)"
        lines = []
        for o in ods:
            lines.append(
                f"{o.get('symbol')} {o.get('side')} {o.get('type')} "
                f"qty={o.get('origQty')} price={o.get('price')} status={o.get('status')}"
            )
        return "\n".join(lines)

    if cmd == "my_trades":
        try:
            sym = normalize_binance_spot_symbol(rest[0]) if rest else ctx.state.selected_symbol
        except ValueError:
            return "Invalid symbol format."
        await gw.fetch_my_trades(sym)
        mt = ctx.state.my_trades
        if not mt:
            return "(no trades)"
        lines = []
        for t in mt[-20:]:
            lines.append(
                f"{t.get('time')} {sym} "
                f"{'BUY' if t.get('isBuyer') else 'SELL'} "
                f"qty={t.get('qty')} price={t.get('price')}"
            )
        return "\n".join(lines)

    if cmd == "price":
        if not rest:
            return "usage: price SYMBOL (e.g. price ETHUSDT)"
        try:
            sym = normalize_binance_spot_symbol(rest[0])
        except ValueError:
            return "Invalid symbol format."
        bk = await gw.fetch_book_ticker(sym)
        if not bk:
            return f"Could not load bookTicker for {sym}"
        return f"{sym} bid={bk.get('bidPrice')} ask={bk.get('askPrice')}"

    if cmd == "orderbook":
        try:
            sym = normalize_binance_spot_symbol(rest[0]) if rest else ctx.state.selected_symbol
        except ValueError:
            return "Invalid symbol format."
        if sym != ctx.state.selected_symbol:
            return f"State orderbook is for {ctx.state.selected_symbol}. Switch symbol or use the dashboard."
        return _format_orderbook(ctx.state, sym)

    if cmd == "symbol":
        if not rest:
            return "usage: symbol BTCUSDT"
        try:
            ctx.state.selected_symbol = normalize_binance_spot_symbol(rest[0])
        except ValueError:
            return "Invalid symbol format."
        await gw.restart_market_stream()
        return f"Active symbol set to {ctx.state.selected_symbol} (WebSocket restarted)"

    return f"Unknown command: {cmd}. Type 'help'."
