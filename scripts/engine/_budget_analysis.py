import httpx, sqlite3
from pathlib import Path

# Check via API
try:
    r = httpx.get("http://127.0.0.1:8000/api/v1/health/deep", timeout=5).json()
    bg = r.get("budget_guard", {})
    print(f"Budget Guard Status:")
    print(f"  Spent 24h: {bg.get('spent_24h_usdt')} USDT")
    print(f"  Max daily: {bg.get('max_daily_usdt')} USDT")
    print(f"  Remaining: {bg.get('remaining_usdt')} USDT")
    print(f"  Blocked:   {bg.get('blocked')}")
except Exception as e:
    print(f"API error: {e}")

# Check raw ledger for pattern analysis
db = Path("runtime/data/budget_guard.sqlite")
if db.exists():
    conn = sqlite3.connect(str(db))
    # Count entries
    total = conn.execute("SELECT COUNT(*) FROM budget_ledger").fetchone()[0]
    buys = conn.execute("SELECT COUNT(*) FROM budget_ledger WHERE side='BUY'").fetchone()[0]
    
    # Recent entries
    rows = conn.execute(
        "SELECT ts_utc, bot_id, symbol, side, amount_usdt FROM budget_ledger "
        "ORDER BY id DESC LIMIT 20"
    ).fetchall()
    
    print(f"\nLedger: {total} entries, {buys} BUY records")
    print(f"\nLast 20 entries:")
    for r in rows:
        print(f"  {r[0][:19]} {r[1][:20]:20s} {r[3]:4s} {r[2]:12s} {r[4]:>8s} USDT")
    
    # Breakdown by bot_id
    bots = conn.execute(
        "SELECT bot_id, COUNT(*), SUM(CAST(amount_usdt AS REAL)) "
        "FROM budget_ledger WHERE side='BUY' "
        "GROUP BY bot_id ORDER BY SUM(CAST(amount_usdt AS REAL)) DESC"
    ).fetchall()
    
    print(f"\nSpend by bot (top consumers):")
    for b in bots[:10]:
        print(f"  {b[0][:30]:30s} {b[1]:4d} buys = {b[2]:>10.2f} USDT")
    
    conn.close()
