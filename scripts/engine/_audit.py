"""Full system audit: health, P&L, coherence check."""
import httpx
import json
import sqlite3
from pathlib import Path

BASE = "http://127.0.0.1:8000"

print("=" * 60)
print("AUDIT COMPLETA — Pecunator")
print("=" * 60)

# 1. Health
try:
    h = httpx.get(f"{BASE}/api/v1/health/deep", timeout=5).json()
    status = h.get("status")
    print(f"\nEngine: {status}")
    hubs = h.get("hubs", {})
    for hub, info in hubs.items():
        total = info.get("hub_bots_total", 0)
        running = info.get("hub_bots_running", 0)
        desired = info.get("hub_bots_desired_running", 0)
        print(f"  {hub}: {running}/{total} running (desired={desired})")
except Exception as e:
    print(f"Health error: {e}")

# 2. Gateway
try:
    gw = httpx.get(f"{BASE}/api/v1/gateway/snapshot", timeout=5).json()
    w = gw.get("weight_used") or 0
    wl = gw.get("weight_limit") or 6000
    print(f"\nGateway: weight={w}/{wl} ({w/wl*100:.1f}%)")
    print(f"  WS connected: {gw.get('ws_connected')}")
except Exception as e:
    print(f"Gateway error: {e}")

# 3. Fuse
try:
    f = httpx.get(f"{BASE}/api-fuse/status", timeout=5).json()
    tripped = f.get("tripped")
    trips = f.get("trip_count", 0)
    streak = f.get("consecutive_streak", 0)
    print(f"\nFuse: tripped={tripped} trips={trips} streak={streak}")
except Exception as e:
    print(f"Fuse error: {e}")

# 4. Budget
try:
    bg = httpx.get(f"{BASE}/api/v1/budget-guard/status", timeout=5).json()
    spent = bg.get("spent_24h_usdt")
    mx = bg.get("max_daily_usdt")
    pct = bg.get("pct")
    print(f"\nBudget: {spent}/{mx} ({pct}%)")
    for hub, info in bg.get("hubs", {}).items():
        s = info.get("spent_24h")
        c = info.get("ceiling")
        p = info.get("pct")
        b = info.get("blocked")
        print(f"  {hub}: {s}/{c} ({p}%) blocked={b}")
except Exception as e:
    print(f"Budget error: {e}")

# 5. Order Ledger P&L
db_path = Path("runtime/data/order_ledger.sqlite")
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    total = conn.execute("SELECT COUNT(*) FROM order_ledger").fetchone()[0]
    buys = conn.execute("SELECT COUNT(*) FROM order_ledger WHERE side='BUY'").fetchone()[0]
    sells = conn.execute("SELECT COUNT(*) FROM order_ledger WHERE side='SELL'").fetchone()[0]

    # Real (non-simulated) trades
    real_buys = conn.execute(
        "SELECT symbol, qty, price, quote_order_qty, reason, ts_utc "
        "FROM order_ledger WHERE side='BUY' AND execution_mode != 'SIMULATED' ORDER BY id"
    ).fetchall()
    real_sells = conn.execute(
        "SELECT symbol, qty, price, quote_order_qty, reason, ts_utc "
        "FROM order_ledger WHERE side='SELL' AND execution_mode != 'SIMULATED' ORDER BY id"
    ).fetchall()

    print(f"\nOrder Ledger: {total} total ({buys} BUY, {sells} SELL)")
    print(f"  Real BUYs: {len(real_buys)}")
    print(f"  Real SELLs: {len(real_sells)}")

    total_bought = sum(float(r[3] or 0) for r in real_buys)
    total_sold = sum(float(r[3] or 0) for r in real_sells)
    print(f"  Total bought: {total_bought:.2f} USDT")
    print(f"  Total sold:   {total_sold:.2f} USDT")
    print(f"  Net flow:     {total_sold - total_bought:+.2f} USDT")

    if real_buys or real_sells:
        last = conn.execute(
            "SELECT ts_utc, bot_type, symbol, side, qty, price, reason, execution_mode "
            "FROM order_ledger WHERE execution_mode != 'SIMULATED' "
            "ORDER BY id DESC LIMIT 15"
        ).fetchall()
        print(f"\n  Last real trades:")
        for r in last:
            ts = str(r[0])[:19]
            bt = str(r[1])[:10]
            sym = str(r[2])[:12]
            side = str(r[3])
            qty = r[4]
            price = r[5]
            reason = r[6]
            print(f"    {ts} {bt:10s} {side:4s} {sym:12s} qty={qty} price={price} {reason}")

    # Simulated trades count
    sim = conn.execute(
        "SELECT COUNT(*) FROM order_ledger WHERE execution_mode = 'SIMULATED'"
    ).fetchone()[0]
    print(f"\n  Simulated trades: {sim}")
    conn.close()
else:
    print("\nNo order ledger found")

# 6. Spot account
try:
    spot = httpx.get(f"{BASE}/api/v1/account/spot", timeout=10).json()
    balances = spot.get("balances", [])
    usdt_bal = 0.0
    non_zero = []
    for b in balances:
        free = float(b.get("free", 0))
        locked = float(b.get("locked", 0))
        total_b = free + locked
        if total_b > 0.001:
            asset = b.get("asset", "?")
            if asset == "USDT":
                usdt_bal = total_b
            non_zero.append((asset, total_b, free, locked))
    print(f"\nSpot Account: {len(non_zero)} assets with balance")
    print(f"  USDT: {usdt_bal:.2f}")
    for asset, total_b, free, locked in sorted(non_zero, key=lambda x: -x[1])[:15]:
        if asset != "USDT":
            lock_str = f" (locked={locked:.6f})" if locked > 0.001 else ""
            print(f"  {asset}: {total_b:.6f}{lock_str}")
except Exception as e:
    print(f"Spot error: {e}")

print(f"\n{'='*60}")
print("AUDIT COMPLETE")
print(f"{'='*60}")
