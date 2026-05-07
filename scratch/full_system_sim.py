"""Full system simulation — tests all endpoints and services."""
import requests
import json
import sys

BASE = "http://127.0.0.1:8000"

def test(label, url, extract=None):
    print(f"\n[{label}]")
    try:
        r = requests.get(f"{BASE}{url}", timeout=5)
        data = r.json()
        if extract:
            extract(data)
        else:
            print(f"    {json.dumps(data, indent=2, default=str)[:400]}")
        return data
    except Exception as e:
        print(f"    ERROR: {e}")
        return None

print("=" * 60)
print("PECUNATOR FULL SYSTEM SIMULATION")
print("=" * 60)

# 1. Health
test("1. Health", "/api/v1/system/health", lambda d: [
    print(f"    Status: {d.get('status')}"),
    print(f"    Gateway: {d.get('gateway_running')}"),
])

# 2. Dorothy
test("2. Dorothy Bots", "/api/v1/dorothy/bots", lambda d: [
    print(f"    Instances: {len(d.get('bots', []))}"),
    *[print(f"      {b.get('bot_id','')} sym={b.get('symbol','')} running={b.get('running')}")
      for b in d.get('bots', [])[:3]]
])

# 3. Masha
test("3. Masha Bots", "/api/v1/masha/bots", lambda d: [
    print(f"    Instances: {len(d.get('bots', []))}"),
    *[print(f"      {b.get('bot_id','')} sym={b.get('symbol','')} running={b.get('running')}")
      for b in d.get('bots', [])[:3]]
])

# 4. Thusnelda
test("4. Thusnelda Bots", "/api/v1/thusnelda/bots", lambda d: [
    print(f"    Instances: {len(d.get('bots', []))}"),
    *[print(f"      {b.get('bot_id','')} symbols={b.get('symbols_csv','')} running={b.get('running')}")
      for b in d.get('bots', [])[:3]]
])

# 5. VMO
test("5. VMO Status", "/api/v1/vision/status", lambda d: [
    print(f"    Enabled: {d.get('enabled')}"),
    print(f"    Symbols: {d.get('config', {}).get('symbols', [])}"),
    print(f"    Timeframes: {d.get('config', {}).get('timeframes', [])}"),
    print(f"    LLM: {d.get('config', {}).get('llm_provider')}/{d.get('config', {}).get('llm_model')}"),
    print(f"    Captures/cycle: {d.get('config', {}).get('captures_per_cycle')}"),
])

# 6. Coordinator
test("6. Bot Coordinator", "/api/v1/system/coordinator", lambda d: [
    print(f"    Zone: {d.get('zone')}"),
    print(f"    Active: {d.get('active_count', 0)}"),
    print(f"    Staged: {d.get('staged_count', 0)}"),
])

# 7. Governor
test("7. Weight Governor", "/api/v1/system/governor", lambda d: [
    print(f"    {svc}: zone={info.get('zone','?')} remaining={info.get('remaining','?')}")
    for svc, info in d.items() if isinstance(info, dict)
])

# 8. AutoPilot
test("8. AutoPilot", "/api/v1/system/autopilot", lambda d: [
    print(f"    Running: {d.get('running')}"),
    print(f"    Auto-stage: {d.get('auto_stage')}"),
    print(f"    VMO: {d.get('vmo_enabled')}"),
])

# 9. Telemetry
test("9. Telemetry Vault", "/api/v1/system/telemetry", lambda d: [
    print(f"    Klines: {d.get('kline_candles', 0)}"),
    print(f"    Decisions: {d.get('bot_decisions', 0)}"),
    print(f"    Captures: {d.get('indexed_captures', 0)}"),
])

# 10. SubAccounts
test("10. SubAccount Registry", "/api/v1/system/subaccounts", lambda d: [
    print(f"    {acc.get('account_id',''):<12} type={acc.get('bot_type',''):<10} sym={acc.get('symbols', [])}")
    for acc in d.get("accounts", [])
])

# 11. Integration test (offline)
print("\n[11. Integration Test (Offline)]")
import subprocess
r = subprocess.run(
    [sys.executable, "scratch/integration_test.py"],
    capture_output=True, text=True, timeout=30,
)
# Just show result line
for line in r.stdout.split("\n"):
    if "Result:" in line or "PASS" in line or "FAIL" in line:
        print(f"    {line.strip()}")

print("\n" + "=" * 60)
print("SIMULATION COMPLETE")
print("=" * 60)
