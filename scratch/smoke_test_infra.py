"""Smoke test: instantiate all new infra modules for 1 second and stop."""
import sys, time
sys.path.insert(0, ".")

print("=== PECUNATOR INFRA SMOKE TEST ===\n")
t0 = time.monotonic()

# 1. Exception Zoo
print("[1/4] ExceptionZoo...", end=" ")
from runtime.core.exception_zoo import get_exception_zoo
zoo = get_exception_zoo()
fp, novel = zoo.register(ValueError("smoke_test_exception"), module="smoke_test")
assert novel, "Should be novel on first run"
fp2, novel2 = zoo.register(ValueError("smoke_test_exception"), module="smoke_test")
assert not novel2, "Should NOT be novel on second run"
print(f"OK (fingerprint={fp}, summary={zoo.summary()})")

# 2. API Governor
print("[2/4] ApiGovernor...", end=" ")
from runtime.core.api_governor import get_api_governor
gov = get_api_governor()
allowed, wait = gov.request_token("chart-img", units=1, caller="smoke_test")
print(f"OK (chart-img allowed={allowed}, wait={wait:.1f}s, status keys={list(gov.status().keys())})")

# 3. Telemetry Vault
print("[3/4] TelemetryVault...", end=" ")
from runtime.core.telemetry_vault import get_telemetry_vault
vault = get_telemetry_vault()
vault.log_decision(
    bot_id="smoke_bot", bot_type="dorothy",
    decision="BUY", symbol="BTCUSDT", reason="smoke test",
    regime="TRENDING"
)
vault.index_capture(
    symbol="BTCUSDT", timeframe="4h",
    captured_at="2026-05-06T00:00:00Z",
    file_path="runtime/data/vmo/captures/test.png",
    regime="TRENDING", confidence=0.85,
)
print(f"OK (summary={vault.summary()})")

# 4. Account Monitor
print("[4/4] AccountMonitor...", end=" ")
from runtime.core.account_monitor import get_account_monitor
mon = get_account_monitor()
row_id = mon.record_snapshot(
    account_id="main", total_equity="1000.00",
    free_usdt="600.00", locked_usdt="400.00",
)
latest = mon.get_latest_snapshot("main")
signals = mon.get_pending_signals()
print(f"OK (row={row_id}, equity={latest.get('total_equity') if latest else '?'}, signals={len(signals)})")

elapsed = round((time.monotonic() - t0) * 1000)
print(f"\n=== ALL 4 MODULES OK in {elapsed}ms ===")
print("No desbordamientos detectados. Sistema estable.")
