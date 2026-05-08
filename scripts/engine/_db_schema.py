import sqlite3
from pathlib import Path

for db_name in ["order_ledger.sqlite", "dorothy_hub.sqlite", "masha_hub.sqlite", "thusnelda_hub.sqlite"]:
    db = Path("runtime/data") / db_name
    if db.exists():
        conn = sqlite3.connect(str(db))
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
        print(f"\n{db_name}: {tables}")
        for t, c in counts.items():
            print(f"  {t}: {c} rows")
            if c > 0:
                cols = [d[1] for d in conn.execute(f'PRAGMA table_info("{t}")').fetchall()]
                print(f"    columns: {cols}")
                sample = conn.execute(f'SELECT * FROM "{t}" LIMIT 1').fetchone()
                if sample:
                    print(f"    sample: {dict(zip(cols, sample))}")
        conn.close()
