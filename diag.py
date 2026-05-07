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
        print(f"  [{r.get('ts_utc','')}] {r.get('bot_type','')} {r.get('side','')} {r.get('order_type','')} "
              f"{r.get('symbol','')} qty={r.get('qty','')} reason={r.get('reason','')} "
              f"mode={r.get('execution_mode','')} binance_id={r.get('binance_order_id','')}")
else:
    print("  (empty)")

# Budget Guard
print("\n── BUDGET GUARD (today) ──")
rows = _query("budget_guard.sqlite", "SELECT * FROM budget_transactions ORDER BY id DESC LIMIT 10")
if rows:
    for r in rows:
        print(f"  [{r.get('ts_utc','')}] {r.get('bot_id','')} {r.get('symbol','')} "
              f"{r.get('side','')} {r.get('amount_usdt','')} USDT")
else:
    print("  (no transactions)")

# Dorothy logs
print("\n── DOROTHY LOGS (last 10) ──")
rows = _query("dorothy_hub.sqlite", "SELECT ts_utc, level, message FROM dorothy_logs ORDER BY id DESC LIMIT 10")
if rows:
    for r in reversed(rows):
        print(f"  [{r.get('ts_utc','')}] [{r.get('level','')}] {r.get('message','')[:120]}")
else:
    print("  (empty)")

# Masha logs
print("\n── MASHA LOGS (last 10) ──")
rows = _query("masha_hub.sqlite", "SELECT ts_utc, level, message FROM masha_logs ORDER BY id DESC LIMIT 10")
if rows:
    for r in reversed(rows):
        print(f"  [{r.get('ts_utc','')}] [{r.get('level','')}] {r.get('message','')[:120]}")
else:
    print("  (empty)")

# Thusnelda logs
print("\n── THUSNELDA LOGS (last 10) ──")
rows = _query("thusnelda_hub.sqlite", "SELECT ts_utc, level, message FROM thusnelda_logs ORDER BY id DESC LIMIT 10")
if rows:
    for r in reversed(rows):
        print(f"  [{r.get('ts_utc','')}] [{r.get('level','')}] {r.get('message','')[:120]}")
else:
    print("  (empty)")

# Exception Zoo
print("\n── EXCEPTION ZOO (last 5) ──")
try:
    rows = _query("exception_zoo.sqlite", "SELECT * FROM exceptions ORDER BY id DESC LIMIT 5")
    if rows:
        for r in rows:
            print(f"  [{r.get('ts_utc','')}] {r.get('module','')} — {r.get('message','')[:100]}")
    else:
        print("  (no exceptions)")
except Exception:
    print("  (table not found)")

# Hub instances
print("\n── ACTIVE BOT INSTANCES ──")
for hub, table in [("dorothy_hub.sqlite", "dorothy_instances"), ("masha_hub.sqlite", "masha_instances"), ("thusnelda_hub.sqlite", "thusnelda_instances")]:
    rows = _query(hub, f"SELECT bot_id, tag, simulated, trading_enabled, desired_running FROM {table}")
    for r in rows:
        mode = "🔴 LIVE" if not r.get("simulated") else "🟢 SIM"
        active = "▶ RUNNING" if r.get("desired_running") else "⏸ STOPPED"
        trade = "✅ ENABLED" if r.get("trading_enabled") else "❌ DISABLED"
        print(f"  {r.get('tag','?'):20s} {r.get('bot_id','?'):30s} {mode} {trade} {active}")

print("\n" + "=" * 60)
