"""Bot lifecycle simulation — credential-less validation."""
import requests, json, time

BASE = "http://127.0.0.1:8000"

def api(method, path, body=None, timeout=5):
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=timeout)
        elif method == "POST":
            r = requests.post(url, json=body or {}, timeout=timeout)
        elif method == "PATCH":
            r = requests.patch(url, json=body or {}, timeout=timeout)
        elif method == "DELETE":
            r = requests.delete(url, timeout=timeout)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text[:200]}
    except requests.exceptions.ReadTimeout:
        return 408, {"error": "timeout"}
    except Exception as e:
        return 0, {"error": str(e)}

print("=" * 60)
print("PECUNATOR BOT LIFECYCLE SIMULATION")
print("=" * 60)

# 1. Thusnelda CRUD
print("\n[1] Create Thusnelda L0 basket bot")
code, data = api("POST", "/api/v1/thusnelda/bots", {
    "tag": "Thusnelda-L0-Test",
    "symbols_csv": "PEPEUSDT,SUIUSDT,NEARUSDT,INJUSDT,FETUSDT",
    "loop_interval_sec": 300,
    "between_symbol_sec": 3,
    "quote_order_qty_modulo": "6",
    "factor_multiplication": "0.94",
    "profit_target_pct": "0.06",
    "meta_equity_usdt": "0",
    "qty_decimals": 8,
    "note": "L0 basket test",
    "max_drawdown_pct": "0.30",
    "stop_loss_pct": "0.25",
    "metrics_interval_cycles": 3,
    "simulated": True,
    "trading_enabled": False,
})
bot_id = data.get("bot_id", "")
print(f"    HTTP {code} | bot_id={bot_id}")

# 2. Verify L0 params persisted
print("\n[2] Verify L0 params in listing")
code, data = api("GET", "/api/v1/thusnelda/bots")
for b in data.get("bots", []):
    if b.get("bot_id") == bot_id:
        checks = {
            "symbols": b.get("symbols_csv") == "PEPEUSDT,SUIUSDT,NEARUSDT,INJUSDT,FETUSDT",
            "factor": b.get("factor_multiplication") == "0.94",
            "profit_target": b.get("profit_target_pct") == "0.06",
            "maxDd": b.get("max_drawdown_pct") == "0.30",
            "stopLoss": b.get("stop_loss_pct") == "0.25",
            "quote_qty": b.get("quote_order_qty_modulo") == "6",
            "loop": b.get("loop_interval_sec") == 300,
        }
        for k, v in checks.items():
            status = "PASS" if v else "FAIL"
            print(f"    [{status}] {k}: {b.get(k, '?')}")
        break

# 3. Update bot params
print("\n[3] Update bot params")
code, data = api("PATCH", f"/api/v1/thusnelda/bots/{bot_id}", {
    "profit_target_pct": "0.08",
    "note": "Updated target",
})
print(f"    HTTP {code} | new profit_target={data.get('profit_target_pct')}")

# 4. Verify update
code, data = api("GET", "/api/v1/thusnelda/bots")
for b in data.get("bots", []):
    if b.get("bot_id") == bot_id:
        print(f"    profit_target_pct={b.get('profit_target_pct')} (expected 0.08)")
        print(f"    note={b.get('note')}")

# 5. Run once (expect 400/credential error — no keys)
print("\n[5] Run once (no credentials — expect error)")
code, data = api("POST", f"/api/v1/thusnelda/bots/{bot_id}/run_once", timeout=5)
print(f"    HTTP {code} | detail={data.get('detail', data.get('error', '?'))}")

# 6. Start (expect 400 — no credentials)
print("\n[6] Start bot (no credentials)")
code, data = api("POST", f"/api/v1/thusnelda/bots/{bot_id}/start", timeout=5)
print(f"    HTTP {code} | detail={data.get('detail', '?')}")

# 7. Check logs (should have creation + update events)
print("\n[7] Check bot logs")
code, data = api("GET", f"/api/v1/thusnelda/bots/{bot_id}/logs?limit=20")
logs = data.get("logs", [])
print(f"    HTTP {code} | {len(logs)} log entries")
for log in logs[-5:]:
    if isinstance(log, dict):
        ts = str(log.get("ts_utc", ""))[-8:]
        level = log.get("level", "?")
        msg = str(log.get("message", ""))[:80]
        print(f"    [{ts}] {level}: {msg}")

# 8. VMO status
print("\n[8] VMO Configuration")
code, data = api("GET", "/api/v1/vision/status")
cfg = data.get("config", {})
syms = cfg.get("symbols", [])
basket_syms = {"PEPEUSDT", "SUIUSDT", "NEARUSDT", "INJUSDT", "FETUSDT"}
covered = basket_syms.issubset(set(syms))
print(f"    Symbols: {syms}")
print(f"    Basket covered by VMO: {'PASS' if covered else 'FAIL'}")
print(f"    Timeframes: {cfg.get('timeframes')}")
print(f"    LLM: {cfg.get('llm_provider')}/{cfg.get('llm_model')}")

# 9. Masha quick test
print("\n[9] Masha bot CRUD")
code, data = api("POST", "/api/v1/masha/bots", {
    "symbol": "BTCUSDT",
    "loop_interval_sec": 600,
    "profit_factor": "0.05",
    "simulated": True,
})
masha_id = data.get("bot_id", "")
print(f"    Created: {masha_id} (HTTP {code})")
if masha_id:
    code, data = api("GET", f"/api/v1/masha/bots/{masha_id}/logs?limit=5")
    print(f"    Logs: {len(data.get('logs', []))} entries")

# 10. Dorothy hub test
print("\n[10] Dorothy hub CRUD")
code, data = api("POST", "/api/v1/hub/bots", {
    "symbol": "ETHUSDT",
    "loop_interval_sec": 450,
    "profit_factor": "0.05",
    "margin_drop_factor": "0.03",
    "simulated": True,
})
dorothy_id = data.get("bot_id", "")
print(f"    Created: {dorothy_id} (HTTP {code})")
if dorothy_id:
    code, data = api("GET", f"/api/v1/hub/bots/{dorothy_id}/logs?limit=5")
    print(f"    Logs: {len(data.get('logs', []))} entries")

# 11. Final DB state
print("\n[11] Final Database State")
code, data = api("GET", "/api/v1/thusnelda/bots")
print(f"    Thusnelda instances: {len(data.get('bots', []))}")
for b in data.get("bots", []):
    print(f"      {b.get('bot_id')} | {b.get('symbols_csv')} | target={b.get('profit_target_pct')}")
code, data = api("GET", "/api/v1/masha/bots")
print(f"    Masha instances: {len(data.get('bots', []))}")
code, data = api("GET", "/api/v1/hub/bots")
# hub might return differently
if isinstance(data, dict):
    hubs = data.get("bots", [])
    print(f"    Dorothy instances: {len(hubs)}")

# 12. Delete test bots
print("\n[12] Cleanup")
if bot_id:
    code, _ = api("DELETE", f"/api/v1/thusnelda/bots/{bot_id}")
    print(f"    Thusnelda {bot_id}: HTTP {code}")
if masha_id:
    code, _ = api("DELETE", f"/api/v1/masha/bots/{masha_id}")
    print(f"    Masha {masha_id}: HTTP {code}")
if dorothy_id:
    code, _ = api("DELETE", f"/api/v1/hub/bots/{dorothy_id}")
    print(f"    Dorothy {dorothy_id}: HTTP {code}")

print("\n" + "=" * 60)
print("SIMULATION COMPLETE")
print("=" * 60)
