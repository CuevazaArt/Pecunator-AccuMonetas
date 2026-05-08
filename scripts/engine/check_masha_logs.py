import sqlite3
import json

print("--- MASHA LOGS ---")
try:
    conn = sqlite3.connect('runtime/data/masha_hub.sqlite')
    conn.row_factory = sqlite3.Row
    for row in conn.execute('SELECT ts_utc, tag, message, payload_json FROM masha_logs ORDER BY id DESC LIMIT 15').fetchall():
        payload = json.loads(row['payload_json']) if row['payload_json'] else {}
        print(f"{row['ts_utc']} [{row['tag']}] {row['message']}")
        if payload.get('report'):
            rep = payload['report']
            print(f"  -> decision: {rep.get('decision')}, regime_reason: {rep.get('regime_reason')}")
except Exception as e:
    print(f'Error reading DB: {e}')
