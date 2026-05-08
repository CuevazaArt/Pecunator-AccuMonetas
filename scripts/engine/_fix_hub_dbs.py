"""One-shot: update hub databases to production-ready config."""
import sqlite3
import datetime

DATA = "runtime/data"

# Dorothy
conn = sqlite3.connect(f"{DATA}/dorothy_hub.sqlite")
conn.execute("UPDATE dorothy_instances SET quote_order_qty='8'")
conn.commit()
print("[OK] Dorothy: quote_order_qty -> 8 USDT")
conn.close()

# Thusnelda
conn = sqlite3.connect(f"{DATA}/thusnelda_hub.sqlite")
now_iso = datetime.datetime.now().isoformat()
conn.execute(
    "UPDATE thusnelda_instances SET quote_order_qty_modulo='8', reference_ts_iso=?",
    (now_iso,),
)
conn.commit()
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM thusnelda_instances").fetchone()
print(f"[OK] Thusnelda: quote_order_qty_modulo -> 8 USDT")
print(f"     reference_ts_iso reset to {now_iso}")
print(f"     symbols_csv = {row['symbols_csv']}")
print(f"     desired_running = {row['desired_running']}")
conn.close()

# Masha (verify only)
conn = sqlite3.connect(f"{DATA}/masha_hub.sqlite")
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM masha_instances").fetchone()
print(f"[OK] Masha: buy_qty_base = {row['buy_qty_base']} BTC (no change needed)")
print(f"     desired_running = {row['desired_running']}")
conn.close()

print("\nAll hub databases updated for production.")
