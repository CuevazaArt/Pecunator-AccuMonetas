"""Quick diagnostic script — reads the current state of the running engine."""
import sqlite3, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA = os.path.join("runtime", "data")

def _query(db_name, sql, limit=20):
    path = os.path.join(DATA, db_name)
    if not os.path.exists(path):
        return []
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql).fetchall()[:limit]]
    except sqlite3.OperationalError as e:
        print(f"  (DB error: {e})")
        return []
    finally:
        conn.close()

print("=" * 60)
print("📊 PECUNATOR DIAGNOSTIC REPORT")
print("=" * 60)

# Order Ledger
print("\n── ORDER LEDGER (last 20) ──")
rows = _query("order_ledger.sqlite", "SELECT * FROM order_ledger ORDER BY id DESC LIMIT 20")
if rows:
    for r in reversed(rows):
        print(f"  [{r.get('ts_utc','')[:19]}] {r.get('bot_type',''):10s} {r.get('side',''):4s} "
              f"{r.get('symbol',''):12s} qty={r.get('qty',''):>8s} reason={r.get('reason',''):25s} "
              f"mode={r.get('execution_mode',''):10s} binance_id={r.get('binance_order_id','')}")
else:
    print("  (empty)")

# Budget Guard
print("\n── BUDGET GUARD (today) ──")
rows = _query("budget_guard.sqlite", "SELECT * FROM budget_ledger ORDER BY id DESC LIMIT 10")
if rows:
    for r in rows:
        print(f"  [{r.get('ts_utc','')}] {r.get('bot_id','')} {r.get('symbol','')} "
              f"{r.get('side','')} {r.get('amount_usdt','')} USDT")
else:
    print("  (no budget transactions yet)")

# Dorothy logs
print("\n── DOROTHY LOGS (last 10) ──")
rows = _query("dorothy_hub.sqlite", "SELECT ts_utc, level, message FROM dorothy_logs ORDER BY id DESC LIMIT 10")
if rows:
    for r in reversed(rows):
        print(f"  [{r.get('ts_utc','')[:19]}] [{r.get('level',''):7s}] {r.get('message','')[:120]}")
else:
    print("  (empty)")

# Masha logs
print("\n── MASHA LOGS (last 10) ──")
rows = _query("masha_hub.sqlite", "SELECT ts_utc, level, message FROM masha_logs ORDER BY id DESC LIMIT 10")
if rows:
    for r in reversed(rows):
        print(f"  [{r.get('ts_utc','')[:19]}] [{r.get('level',''):7s}] {r.get('message','')[:120]}")
else:
    print("  (empty)")

# Thusnelda logs
print("\n── THUSNELDA LOGS (last 10) ──")
rows = _query("thusnelda_hub.sqlite", "SELECT ts_utc, level, message FROM thusnelda_logs ORDER BY id DESC LIMIT 10")
if rows:
    for r in reversed(rows):
        print(f"  [{r.get('ts_utc','')[:19]}] [{r.get('level',''):7s}] {r.get('message','')[:120]}")
else:
    print("  (empty)")

# Hub instances
print("\n── ACTIVE BOT INSTANCES ──")
for hub, table in [("dorothy_hub.sqlite", "dorothy_instances"), ("masha_hub.sqlite", "masha_instances"), ("thusnelda_hub.sqlite", "thusnelda_instances")]:
    rows = _query(hub, f"SELECT bot_id, tag, simulated, trading_enabled, desired_running FROM {table}")
    for r in rows:
        mode = "🔴 LIVE" if not r.get("simulated") else "🟢 SIM"
        active = "▶ RUNNING" if r.get("desired_running") else "⏸ STOPPED"
        trade = "✅ ENABLED" if r.get("trading_enabled") else "❌ DISABLED"
        print(f"  {r.get('tag','?'):25s} {r.get('bot_id','?')[:20]:20s} {mode} {trade} {active}")

# Equity snapshots
print("\n── EQUITY SNAPSHOTS (last 5 per bot) ──")
for hub, pfx in [("dorothy_hub.sqlite", "dorothy"), ("masha_hub.sqlite", "masha"), ("thusnelda_hub.sqlite", "thusnelda")]:
    rows = _query(hub, f"SELECT ts_utc, bot_id, equity_usdt, drawdown_pct, trading_blocked FROM {pfx}_equity_snapshots ORDER BY id DESC LIMIT 5")
    if rows:
        print(f"  [{pfx.upper()}]")
        for r in rows:
            blocked = "⛔" if r.get("trading_blocked") else "✅"
            print(f"    {r.get('ts_utc','')[:19]} equity={r.get('equity_usdt','?'):>12s} dd={r.get('drawdown_pct','?'):>8s} {blocked}")

print("\n" + "=" * 60)
