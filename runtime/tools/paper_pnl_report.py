"""Paper P&L Report — Analyse simulated trade history.

Reads ``paper_trades.sqlite`` and produces a human-readable summary of
simulated trading performance including:

  - Total decisions by type (BUY, SELL, WAIT, STOP_LOSS, etc.)
  - Decision frequency per bot and per symbol
  - Win/loss estimation from BUY_AND_SELL decisions (where available)
  - Activity timeline (first/last decision, decisions per day)
  - Commission estimate at configurable fee rate

Usage:
    python -m runtime.tools.paper_pnl_report
    python -m runtime.tools.paper_pnl_report --bot dorothy --symbol ETHUSDT
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

# Add project root to path for direct execution
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime.bot._paper_log import get_paper_trades, paper_trade_summary


def _parse_price(report: dict[str, Any], key: str) -> Decimal | None:
    """Try to extract a decimal price from a report dict."""
    val = report.get(key)
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


def analyse_trades(
    bot_type: str = "",
    symbol: str = "",
    fee_rate: float = 0.001,
    limit: int = 10000,
) -> dict[str, Any]:
    """Analyse paper trade history and return structured report."""

    summary = paper_trade_summary(bot_type=bot_type, symbol=symbol)
    trades = get_paper_trades(bot_type=bot_type, symbol=symbol, limit=limit)

    if not trades:
        return {
            "status": "no_data",
            "message": "No paper trades found for the given filter.",
            "filter": {"bot_type": bot_type or "*", "symbol": symbol or "*"},
        }

    # Reverse to chronological order (get_paper_trades returns newest first)
    trades = list(reversed(trades))

    # ── Per-bot and per-symbol breakdown ────────────────────────
    by_bot: dict[str, int] = defaultdict(int)
    by_symbol: dict[str, int] = defaultdict(int)
    by_decision: dict[str, int] = defaultdict(int)
    by_bot_symbol: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # ── Simulated P&L estimation ────────────────────────────────
    buy_sells = 0
    estimated_profit_usdt = Decimal("0")
    estimated_commission_usdt = Decimal("0")
    wins = 0
    losses = 0

    # ── Timeline ────────────────────────────────────────────────
    first_ts = trades[0]["ts_utc"] if trades else None
    last_ts = trades[-1]["ts_utc"] if trades else None

    for t in trades:
        bot = t["bot_type"]
        sym = t["symbol"]
        dec = t["decision"]
        rep = t.get("report", {})

        by_bot[bot] += 1
        by_symbol[sym] += 1
        by_decision[dec] += 1
        by_bot_symbol[bot][sym] += 1

        # Try to extract P&L from BUY_AND_SELL decisions
        # Dorothy reports: buy_price, sell_price, qty
        buy_price = _parse_price(rep, "buy_price") or _parse_price(rep, "price")
        sell_price = _parse_price(rep, "sell_price") or _parse_price(rep, "sell_limit_price")
        qty = _parse_price(rep, "qty") or _parse_price(rep, "quantity") or _parse_price(rep, "quote_order_qty")

        if dec in ("BUY_AND_SELL", "BUY_AND_SELL_LIMIT") and buy_price and sell_price and qty:
            buy_sells += 1
            gross = (sell_price - buy_price) * qty
            comm = (buy_price * qty + sell_price * qty) * Decimal(str(fee_rate))
            net = gross - comm
            estimated_profit_usdt += net
            estimated_commission_usdt += comm
            if net > 0:
                wins += 1
            else:
                losses += 1

    # ── Activity density ────────────────────────────────────────
    days_active = 1.0
    if first_ts and last_ts:
        try:
            t0 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            delta = (t1 - t0).total_seconds() / 86400.0
            if delta > 0:
                days_active = delta
        except Exception:
            pass

    total = len(trades)
    decisions_per_day = total / days_active if days_active > 0 else total

    # ── Win rate ────────────────────────────────────────────────
    total_evaluated = wins + losses
    win_rate = (wins / total_evaluated * 100.0) if total_evaluated > 0 else None

    return {
        "status": "ok",
        "filter": {"bot_type": bot_type or "*", "symbol": symbol or "*"},
        "overview": {
            "total_decisions": total,
            "first_decision": first_ts,
            "last_decision": last_ts,
            "days_active": round(days_active, 2),
            "decisions_per_day": round(decisions_per_day, 1),
        },
        "decision_distribution": dict(by_decision),
        "by_bot": dict(by_bot),
        "by_symbol": dict(by_symbol),
        "by_bot_symbol": {k: dict(v) for k, v in by_bot_symbol.items()},
        "simulated_pnl": {
            "evaluated_trades": total_evaluated,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate, 2) if win_rate is not None else None,
            "estimated_gross_profit_usdt": str(estimated_profit_usdt),
            "estimated_commission_usdt": str(estimated_commission_usdt),
            "estimated_net_profit_usdt": str(estimated_profit_usdt - estimated_commission_usdt),
            "fee_rate_used": fee_rate,
        },
    }


def format_report(data: dict[str, Any]) -> str:
    """Format the analysis dict into a human-readable text report."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  PAPER TRADING P&L REPORT")
    lines.append("=" * 60)

    if data.get("status") == "no_data":
        lines.append(f"\n  {data['message']}")
        lines.append(f"  Filter: {data['filter']}")
        return "\n".join(lines)

    filt = data["filter"]
    lines.append(f"  Bot: {filt['bot_type']}  |  Symbol: {filt['symbol']}")
    lines.append("-" * 60)

    ov = data["overview"]
    lines.append(f"\n  Total decisions:    {ov['total_decisions']}")
    lines.append(f"  Period:            {ov['first_decision']}")
    lines.append(f"                  -> {ov['last_decision']}")
    lines.append(f"  Days active:       {ov['days_active']}")
    lines.append(f"  Decisions/day:     {ov['decisions_per_day']}")

    lines.append(f"\n  {'Decision':<25} {'Count':>8}")
    lines.append("  " + "-" * 35)
    for dec, cnt in sorted(data["decision_distribution"].items(), key=lambda x: -x[1]):
        lines.append(f"  {dec:<25} {cnt:>8}")

    lines.append(f"\n  {'Bot':<20} {'Decisions':>10}")
    lines.append("  " + "-" * 32)
    for bot, cnt in sorted(data["by_bot"].items()):
        lines.append(f"  {bot:<20} {cnt:>10}")

    lines.append(f"\n  {'Symbol':<15} {'Decisions':>10}")
    lines.append("  " + "-" * 27)
    for sym, cnt in sorted(data["by_symbol"].items(), key=lambda x: -x[1]):
        lines.append(f"  {sym:<15} {cnt:>10}")

    pnl = data["simulated_pnl"]
    lines.append("\n" + "-" * 60)
    lines.append("  SIMULATED P&L ESTIMATE")
    lines.append("-" * 60)
    if pnl["evaluated_trades"] > 0:
        lines.append(f"  Evaluated trades:  {pnl['evaluated_trades']}")
        lines.append(f"  Wins:              {pnl['wins']}")
        lines.append(f"  Losses:            {pnl['losses']}")
        lines.append(f"  Win rate:          {pnl['win_rate_pct']}%")
        lines.append(f"  Est. net profit:   {pnl['estimated_net_profit_usdt']} USDT")
        lines.append(f"  Est. commissions:  {pnl['estimated_commission_usdt']} USDT")
        lines.append(f"  Fee rate used:     {pnl['fee_rate_used']*100:.2f}%")
    else:
        lines.append("  No BUY_AND_SELL decisions with price data found.")
        lines.append("  P&L estimation requires buy_price + sell_price + qty in reports.")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper Trading P&L Report")
    parser.add_argument("--bot", default="", help="Filter by bot type (dorothy|elphaba)")
    parser.add_argument("--symbol", default="", help="Filter by symbol (e.g. ETHUSDT)")
    parser.add_argument("--fee", type=float, default=0.001, help="Fee rate (default 0.1%%)")
    parser.add_argument("--limit", type=int, default=10000, help="Max trades to analyse")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of text")
    args = parser.parse_args()

    data = analyse_trades(
        bot_type=args.bot,
        symbol=args.symbol,
        fee_rate=args.fee,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(format_report(data))


if __name__ == "__main__":
    main()
