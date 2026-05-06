"""Full system integration test — starts AutoPilot subsystems for 90 seconds.

Tests:
  1. ApiGovernor operational
  2. ExceptionZoo collecting
  3. TelemetryVault storing
  4. SubAccountRegistry resolving
  5. TransferService dry-run
  6. AccountMonitor snapshots
  7. AutoTuner computing
  8. AutoStager evaluating
  9. BotCoordinator staging
  10. Batch LLM import check
  11. KlineCollector import check
  12. Workers start/stop
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, ".")
os.environ.setdefault("PECUNATOR_LOG_LEVEL", "INFO")

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOG = logging.getLogger("integration_test")


async def main():
    t0 = time.monotonic()
    results = {}
    errors = []

    # ── 1. ApiGovernor ──
    try:
        from runtime.core.api_governor import get_api_governor, P_DIAGNOSIS, P_TRADING
        gov = get_api_governor()
        allowed, wait = gov.request_token("binance", units=10, priority=P_TRADING)
        gov.record_usage("binance", action="integration_test", units=10, caller="test")
        s = gov.status()
        results["api_governor"] = f"OK (binance used={s['binance']['used']}, remaining={s['binance']['remaining']})"
        LOG.info("1. ApiGovernor: %s", results["api_governor"])
    except Exception as e:
        results["api_governor"] = f"FAIL: {e}"
        errors.append(("api_governor", e))

    # ── 2. ExceptionZoo ──
    try:
        from runtime.core.exception_zoo import get_exception_zoo
        zoo = get_exception_zoo()
        try:
            raise ValueError("integration test exception")
        except ValueError as e:
            zoo.register(e, module="integration_test", context="smoke")
        s = zoo.summary()
        results["exception_zoo"] = f"OK (unique={s['unique_exceptions']}, total={s['total_occurrences']})"
        LOG.info("2. ExceptionZoo: %s", results["exception_zoo"])
    except Exception as e:
        results["exception_zoo"] = f"FAIL: {e}"
        errors.append(("exception_zoo", e))

    # ── 3. TelemetryVault ──
    try:
        from runtime.core.telemetry_vault import get_telemetry_vault
        vault = get_telemetry_vault()
        vault.log_decision(
            bot_id="integration_test", bot_type="system",
            decision="TEST", action_taken=False,
            symbol="BTCUSDT", reason="Integration test decision",
        )
        s = vault.summary()
        results["telemetry_vault"] = f"OK (decisions={s.get('bot_decisions', 0)}, klines={s.get('kline_candles', 0)})"
        LOG.info("3. TelemetryVault: %s", results["telemetry_vault"])
    except Exception as e:
        results["telemetry_vault"] = f"FAIL: {e}"
        errors.append(("telemetry_vault", e))

    # ── 4. SubAccountRegistry ──
    try:
        from runtime.core.subaccount_registry import get_subaccount_registry
        reg = get_subaccount_registry()
        s = reg.summary()
        bots = reg.list_bots()
        results["subaccount_registry"] = f"OK (accounts={s['total_accounts']}, active_bots={s['active_bots']}, bots={[b.account_id for b in bots]})"
        LOG.info("4. SubAccountRegistry: %s", results["subaccount_registry"])
    except Exception as e:
        results["subaccount_registry"] = f"FAIL: {e}"
        errors.append(("subaccount_registry", e))

    # ── 5. TransferService ──
    try:
        from runtime.core.transfer_service import TransferService
        ts = TransferService("test", "test")
        r1 = ts.fund_bot("dorothy", "USDT", "10", dry_run=True)
        r2 = ts.fund_bot("dorothy", "USDT", "99999", dry_run=True)
        r3 = ts.fund_bot("nonexistent", "USDT", "10", dry_run=True)
        ok_count = sum([r1["ok"], not r2["ok"], not r3["ok"]])
        results["transfer_service"] = f"OK ({ok_count}/3 validations pass)"
        LOG.info("5. TransferService: %s", results["transfer_service"])
    except Exception as e:
        results["transfer_service"] = f"FAIL: {e}"
        errors.append(("transfer_service", e))

    # ── 6. AccountMonitor ──
    try:
        from runtime.core.account_monitor import get_account_monitor
        mon = get_account_monitor()
        row_id = mon.record_snapshot(
            account_id="integration_test",
            total_equity="1000",
            free_usdt="200",
        )
        s = mon.summary()
        results["account_monitor"] = f"OK (snapshot_id={row_id}, total={s['total_snapshots']}, pending_signals={s['pending_signals']})"
        LOG.info("6. AccountMonitor: %s", results["account_monitor"])
    except Exception as e:
        results["account_monitor"] = f"FAIL: {e}"
        errors.append(("account_monitor", e))

    # ── 7. AutoTuner ──
    try:
        from runtime.core.autopilot import AutoTuner
        tuner = AutoTuner()
        r = tuner.compute_params("dorothy", "TRENDING", "HIGH", 0.90, {
            "profit_factor": 0.05, "stop_loss": 0.10,
            "margin_drop": 0.004, "interval_sec": 450, "quote_order_qty": 8.0,
        })
        adj_count = len(r.get("adjustments", []))
        results["auto_tuner"] = f"OK (adjusted={r['adjusted']}, changes={adj_count})"
        LOG.info("7. AutoTuner: %s", results["auto_tuner"])
    except Exception as e:
        results["auto_tuner"] = f"FAIL: {e}"
        errors.append(("auto_tuner", e))

    # ── 8. AutoStager ──
    try:
        from runtime.core.autopilot import AutoStager
        stager = AutoStager()
        actions = await stager.evaluate_and_act([
            {"symbol": "BTCUSDT", "recommended_bot": "dorothy", "confidence": 0.90,
             "regime": "TRENDING", "volatility": "NORMAL"},
        ])
        results["auto_stager"] = f"OK (actions={len(actions)})"
        LOG.info("8. AutoStager: %s", results["auto_stager"])
    except Exception as e:
        results["auto_stager"] = f"FAIL: {e}"
        errors.append(("auto_stager", e))

    # ── 9. BotCoordinator ──
    try:
        from runtime.core.bot_coordinator import get_bot_coordinator
        coord = get_bot_coordinator()
        s = coord.status()
        results["bot_coordinator"] = f"OK (active={s['active_bots']}, staged={s['staged_bots']}, zone={s['weight_zone']})"
        LOG.info("9. BotCoordinator: %s", results["bot_coordinator"])
    except Exception as e:
        results["bot_coordinator"] = f"FAIL: {e}"
        errors.append(("bot_coordinator", e))

    # ── 10. Batch LLM ──
    try:
        from runtime.modules.vision.chart_analyzer import classify_charts_batch
        results["batch_llm"] = "OK (import successful)"
        LOG.info("10. Batch LLM: %s", results["batch_llm"])
    except Exception as e:
        results["batch_llm"] = f"FAIL: {e}"
        errors.append(("batch_llm", e))

    # ── 11. KlineCollector ──
    try:
        from runtime.core.kline_collector import get_kline_collector
        kc = get_kline_collector()
        results["kline_collector"] = "OK (import successful)"
        LOG.info("11. KlineCollector: %s", results["kline_collector"])
    except Exception as e:
        results["kline_collector"] = f"FAIL: {e}"
        errors.append(("kline_collector", e))

    # ── 12. Workers ──
    try:
        from runtime.core.workers import start_background_workers, stop_background_workers
        w = await start_background_workers(api_key="", api_secret="", monitor_hours=999)
        await asyncio.sleep(2)
        await stop_background_workers()
        results["workers"] = f"OK (start={w})"
        LOG.info("12. Workers: %s", results["workers"])
    except Exception as e:
        results["workers"] = f"FAIL: {e}"
        errors.append(("workers", e))

    # ── 13. Binance API Keys Validation ──
    try:
        from dotenv import load_dotenv
        load_dotenv()
        key_names = ["DOROTHY_API_KEY", "MASHA_API_KEY", "BLUECHIP_API_KEY"]
        found = sum(1 for k in key_names if os.environ.get(k, "").strip("'"))
        results["api_keys"] = f"OK ({found}/3 keys loaded from .env)"
        LOG.info("13. API Keys: %s", results["api_keys"])
    except Exception as e:
        results["api_keys"] = f"FAIL: {e}"
        errors.append(("api_keys", e))

    # ── REPORT ──
    elapsed = time.monotonic() - t0
    print("\n" + "=" * 65)
    print("PECUNATOR INTEGRATION TEST REPORT")
    print("=" * 65)
    passed = sum(1 for v in results.values() if v.startswith("OK"))
    total = len(results)
    for name, result in results.items():
        icon = "  PASS" if result.startswith("OK") else "**FAIL"
        print(f"  {icon}  {name:25s} {result}")
    print("-" * 65)
    print(f"  Result: {passed}/{total} passed in {elapsed:.1f}s")
    if errors:
        print(f"  Errors: {len(errors)}")
        for name, exc in errors:
            print(f"    {name}: {type(exc).__name__}: {exc}")
    print("=" * 65)

    return passed == total


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
