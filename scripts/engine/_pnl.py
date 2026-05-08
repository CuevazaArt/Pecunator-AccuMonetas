"""P&L + Equity analysis from Dorothy snapshots + direct Binance."""
import sqlite3, os, sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Dorothy equity snapshots
db = Path("runtime/data/dorothy_hub.sqlite")
if db.exists():
    conn = sqlite3.connect(str(db))
    
    # Latest equity per bot
    latest = conn.execute("""
        SELECT e.bot_id, i.tag, i.symbol, e.equity_usdt, e.capital_usdt, 
               e.drawdown_pct, e.peak_equity_usdt, e.ts_utc
        FROM dorothy_equity_snapshots e
        JOIN dorothy_instances i ON e.bot_id = i.bot_id
        WHERE e.id IN (
            SELECT MAX(id) FROM dorothy_equity_snapshots GROUP BY bot_id
        )
        ORDER BY CAST(e.equity_usdt AS REAL) DESC
    """).fetchall()
    
    print("=" * 70)
    print("DOROTHY EQUITY REPORT")
    print("=" * 70)
    total_eq = 0.0
    total_cap = 0.0
    for r in latest:
        bot_id, tag, symbol, eq, cap, dd, peak, ts = r
        eq_f = float(eq or 0)
        cap_f = float(cap or 0)
        dd_f = float(dd or 0)
        peak_f = float(peak or 0)
        pnl = eq_f - cap_f if cap_f > 0 else 0
        pnl_pct = (pnl / cap_f * 100) if cap_f > 0 else 0
        total_eq += eq_f
        total_cap += cap_f
        icon = "🟢" if pnl >= 0 else "🔴"
        print(f"  {icon} {tag:20s} {symbol:12s} eq={eq_f:>10.2f} cap={cap_f:>8.2f} "
              f"P&L={pnl:+8.2f} ({pnl_pct:+.1f}%) dd={dd_f:.3f}")
    
    total_pnl = total_eq - total_cap
    total_pnl_pct = (total_pnl / total_cap * 100) if total_cap > 0 else 0
    print(f"\n  {'TOTAL':20s} {'':12s} eq={total_eq:>10.2f} cap={total_cap:>8.2f} "
          f"P&L={total_pnl:+8.2f} ({total_pnl_pct:+.1f}%)")
    
    # Equity history (first vs last for each bot)
    first_last = conn.execute("""
        SELECT bot_id,
            (SELECT equity_usdt FROM dorothy_equity_snapshots WHERE bot_id = e.bot_id ORDER BY id ASC LIMIT 1) as first_eq,
            (SELECT equity_usdt FROM dorothy_equity_snapshots WHERE bot_id = e.bot_id ORDER BY id DESC LIMIT 1) as last_eq,
            COUNT(*) as snapshots
        FROM dorothy_equity_snapshots e
        GROUP BY bot_id
    """).fetchall()
    
    print(f"\n  Snapshots per bot:")
    for r in first_last:
        bid, first, last, cnt = r
        f_f = float(first or 0)
        l_f = float(last or 0)
        delta = l_f - f_f
        print(f"    {bid[:25]:25s} {cnt:4d} snaps  first={f_f:.2f} last={l_f:.2f} delta={delta:+.2f}")
    
    conn.close()

# Direct Binance balance
print(f"\n{'='*70}")
print("BINANCE ACCOUNT BALANCE (direct)")
print("=" * 70)
try:
    from dotenv import load_dotenv
    load_dotenv()
    from binance.client import Client
    api_key = os.environ.get("PECUNATOR_BINANCE_API_KEY", "") or os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("PECUNATOR_BINANCE_API_SECRET", "") or os.environ.get("BINANCE_API_SECRET", "")
    client = Client(api_key, api_secret)
    account = client.get_account()
    
    non_zero = []
    usdt_total = 0.0
    for b in account.get("balances", []):
        free = float(b["free"])
        locked = float(b["locked"])
        total = free + locked
        if total > 0.0001:
            asset = b["asset"]
            non_zero.append((asset, total, free, locked))
            if asset == "USDT":
                usdt_total = total
    
    # Get prices to calculate total portfolio value in USDT
    tickers = {t["symbol"]: float(t["price"]) for t in client.get_all_tickers()}
    
    portfolio_usdt = 0.0
    print(f"\n  {'Asset':<10} {'Balance':>14} {'USDT Value':>14} {'Locked':>12}")
    print(f"  {'-'*10} {'-'*14} {'-'*14} {'-'*12}")
    for asset, total, free, locked in sorted(non_zero, key=lambda x: -x[1]):
        if asset == "USDT":
            usdt_val = total
        elif f"{asset}USDT" in tickers:
            usdt_val = total * tickers[f"{asset}USDT"]
        else:
            usdt_val = 0.0
        portfolio_usdt += usdt_val
        lock_str = f"{locked:.6f}" if locked > 0.0001 else "-"
        print(f"  {asset:<10} {total:>14.6f} {usdt_val:>14.4f} {lock_str:>12}")
    
    print(f"\n  TOTAL PORTFOLIO VALUE: {portfolio_usdt:.2f} USDT")
    print(f"  USDT Free:            {usdt_total:.2f}")
    print(f"  In positions:         {portfolio_usdt - usdt_total:.2f}")
    
except Exception as e:
    print(f"  Binance error: {e}")

print(f"\n{'='*70}")
