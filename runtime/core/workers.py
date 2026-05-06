"""Background Workers — Autonomous loops for account monitoring and rebalancing.

Workers:
  1. AccountMonitorLoop — Takes balance snapshots every N hours
  2. RebalanceWorker — Consumes rebalance_signals and executes transfers

Both run as asyncio.Tasks, started from the main application lifecycle.
All operations are governed by ApiGovernor and logged in ExceptionZoo.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from runtime.core.account_monitor import get_account_monitor
from runtime.core.api_governor import get_api_governor, P_MONITORING
from runtime.core.exception_zoo import get_exception_zoo
from runtime.core.subaccount_registry import get_subaccount_registry
from runtime.core.telemetry_vault import get_telemetry_vault

_LOG = logging.getLogger("pecunator.core.workers")


# ── AccountMonitor Auto-Loop ────────────────────────────────────────

class AccountMonitorLoop:
    """Takes periodic balance snapshots for all enabled sub-accounts.

    Cadence: configurable (default 4 hours).
    Weight per snapshot: ~10 (account info + tickers for equity).
    Total per cycle: ~50 weight (5 accounts × 10 weight).
    """

    def __init__(
        self,
        interval_hours: float = 4.0,
        api_key: str = "",
        api_secret: str = "",
    ) -> None:
        self._interval_sec = interval_hours * 3600
        self._key = api_key
        self._secret = api_secret
        self._running = False
        self._task: Optional[asyncio.Task[Any]] = None
        self._cycles = 0

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        _LOG.info(
            "AccountMonitorLoop started (interval=%.1fh)",
            self._interval_sec / 3600,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        _LOG.info("AccountMonitorLoop stopped")

    async def _loop(self) -> None:
        zoo = get_exception_zoo()
        governor = get_api_governor()
        monitor = get_account_monitor()
        registry = get_subaccount_registry()

        while self._running:
            try:
                t0 = time.monotonic()
                accounts = registry.list_active()
                _LOG.info(
                    "AccountMonitor cycle %d: checking %d accounts",
                    self._cycles, len(accounts),
                )

                for acct in accounts:
                    # Check governor for budget
                    allowed, wait = governor.request_token(
                        "binance", units=10, priority=P_MONITORING,
                        caller=f"acct_monitor:{acct.account_id}",
                    )
                    if not allowed:
                        _LOG.warning(
                            "AccountMonitor: governor denied for %s (wait=%.1fs)",
                            acct.account_id, wait,
                        )
                        continue

                    try:
                        snapshot = await self._take_snapshot(
                            acct.account_id, acct.email,
                        )
                        t_snap = time.monotonic()
                        governor.record_usage(
                            "binance",
                            action=f"snapshot:{acct.account_id}",
                            units=10, priority=P_MONITORING,
                            caller="account_monitor_loop",
                            latency_ms=int((t_snap - t0) * 1000),
                            success=snapshot.get("ok", False),
                        )

                        if snapshot.get("ok"):
                            monitor.record_snapshot(
                                account_id=acct.account_id,
                                total_equity=snapshot.get("total_equity", "0"),
                                free_usdt=snapshot.get("free_usdt", "0"),
                                locked_usdt=snapshot.get("locked_usdt", "0"),
                                api_weight_used=snapshot.get("weight", 0),
                                assets_json=json.dumps(
                                    snapshot.get("assets", [])[:20]
                                ),
                            )
                            _LOG.info(
                                "Snapshot OK: %s equity=%s USDT",
                                acct.account_id,
                                snapshot.get("total_equity", "?"),
                            )
                        else:
                            monitor.record_snapshot(
                                account_id=acct.account_id,
                                error_note=snapshot.get("error", "unknown"),
                            )
                    except Exception as exc:
                        zoo.register(
                            exc, module="account_monitor_loop",
                            context=f"snapshot:{acct.account_id}",
                        )
                        monitor.record_snapshot(
                            account_id=acct.account_id,
                            error_note=str(exc)[:200],
                        )

                    # Rate limit between accounts
                    await asyncio.sleep(2.0)

                self._cycles += 1
                elapsed = time.monotonic() - t0
                _LOG.info(
                    "AccountMonitor cycle %d complete (%.1fs), next in %.0fh",
                    self._cycles, elapsed, self._interval_sec / 3600,
                )

            except Exception as exc:
                zoo.register(exc, module="account_monitor_loop", context="cycle")
                _LOG.exception("AccountMonitor cycle failed")

            # Wait for next cycle
            try:
                await asyncio.sleep(self._interval_sec)
            except asyncio.CancelledError:
                break

    async def _take_snapshot(
        self, account_id: str, email: str
    ) -> dict[str, Any]:
        """Take a balance snapshot via REST API.

        For the master account, uses self._key/self._secret.
        For sub-accounts, uses the master account to query sub-account assets.
        """
        import hashlib
        import hmac
        import requests

        if not self._key or not self._secret:
            return {"ok": False, "error": "no_credentials"}

        params: dict[str, str] = {"timestamp": str(int(time.time() * 1000))}

        if account_id == "reserve" or "@gmail.com" in email:
            # Master account — direct query
            path = "/api/v3/account"
        else:
            # Sub-account — query via master
            path = "/sapi/v1/sub-account/assets"
            params["email"] = email

        query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        sig = hmac.new(
            self._secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        url = f"https://api.binance.com{path}?{query}&signature={sig}"

        try:
            r = requests.get(
                url,
                headers={"X-MBX-APIKEY": self._key},
                timeout=15,
            )
            if r.status_code != 200:
                err = r.json() if "json" in r.headers.get("content-type", "") else {}
                return {
                    "ok": False,
                    "error": f"{err.get('code', r.status_code)}: {err.get('msg', '')}",
                }

            data = r.json()

            # Extract weight from headers
            weight = 0
            for k, v in r.headers.items():
                if k.upper() == "X-MBX-USED-WEIGHT-1M":
                    weight = int(v)

            # Parse balances
            if "balances" in data:
                balances = data["balances"]
            else:
                balances = data.get("balances", [])

            non_zero = [
                b for b in balances
                if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0
            ]

            # Calculate USDT equity (simplified: sum free+locked of stablecoin assets)
            total_usdt = sum(
                float(b.get("free", 0)) + float(b.get("locked", 0))
                for b in balances
                if b.get("asset") in ("USDT", "BUSD", "FDUSD", "USDC")
            )
            free_usdt = sum(
                float(b.get("free", 0))
                for b in balances
                if b.get("asset") in ("USDT", "BUSD", "FDUSD", "USDC")
            )
            locked_usdt = sum(
                float(b.get("locked", 0))
                for b in balances
                if b.get("asset") in ("USDT", "BUSD", "FDUSD", "USDC")
            )

            return {
                "ok": True,
                "total_equity": str(round(total_usdt, 4)),
                "free_usdt": str(round(free_usdt, 4)),
                "locked_usdt": str(round(locked_usdt, 4)),
                "weight": weight,
                "assets": [
                    {"a": b["asset"], "f": b["free"], "l": b["locked"]}
                    for b in non_zero[:20]
                ],
            }
        except requests.RequestException as exc:
            return {"ok": False, "error": str(exc)}


# ── Rebalance Worker ────────────────────────────────────────────────

class RebalanceWorker:
    """Consumes pending rebalance signals and logs actions.

    Checks every `check_interval_min` minutes for unacknowledged signals.
    For now, logs recommendations — actual transfers require operator approval
    unless auto_execute is True and amount < auto_threshold_usdt.
    """

    def __init__(
        self,
        check_interval_min: float = 30.0,
        auto_execute: bool = False,
        auto_threshold_usdt: float = 50.0,
    ) -> None:
        self._interval_sec = check_interval_min * 60
        self._auto_execute = auto_execute
        self._auto_threshold = auto_threshold_usdt
        self._running = False
        self._task: Optional[asyncio.Task[Any]] = None
        self._processed = 0

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        _LOG.info(
            "RebalanceWorker started (interval=%.0fmin, auto=%s)",
            self._interval_sec / 60, self._auto_execute,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        zoo = get_exception_zoo()
        monitor = get_account_monitor()
        vault = get_telemetry_vault()

        while self._running:
            try:
                signals = monitor.get_pending_signals()

                if signals:
                    _LOG.info(
                        "RebalanceWorker: %d pending signals", len(signals),
                    )

                for sig in signals:
                    sig_id = sig.get("id", 0)
                    sig_type = sig.get("signal_type", "UNKNOWN")
                    account_id = sig.get("account_id", "main")
                    description = sig.get("description", "")

                    # Log the signal as a decision
                    vault.log_decision(
                        bot_id="rebalance_worker",
                        bot_type="system",
                        decision=f"SIGNAL_{sig_type}",
                        action_taken=False,
                        symbol="PORTFOLIO",
                        reason=description,
                        context={
                            "signal_id": sig_id,
                            "account_id": account_id,
                            "current_value": sig.get("current_value"),
                            "threshold": sig.get("threshold"),
                        },
                    )

                    _LOG.info(
                        "Rebalance signal #%d: %s on %s — %s",
                        sig_id, sig_type, account_id, description,
                    )

                    # Acknowledge the signal (mark as seen)
                    monitor.acknowledge_signal(sig_id, acted_on=False)
                    self._processed += 1

            except Exception as exc:
                zoo.register(exc, module="rebalance_worker", context="check_signals")

            try:
                await asyncio.sleep(self._interval_sec)
            except asyncio.CancelledError:
                break

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "processed_signals": self._processed,
            "auto_execute": self._auto_execute,
            "check_interval_min": self._interval_sec / 60,
        }


# ── Convenience: start all workers ──────────────────────────────────

_monitor_loop: Optional[AccountMonitorLoop] = None
_rebalance_worker: Optional[RebalanceWorker] = None


async def start_background_workers(
    api_key: str = "",
    api_secret: str = "",
    monitor_hours: float = 4.0,
    rebalance_min: float = 30.0,
) -> dict[str, str]:
    """Start all background workers. Safe to call multiple times."""
    global _monitor_loop, _rebalance_worker

    results = {}

    if _monitor_loop is None:
        _monitor_loop = AccountMonitorLoop(
            interval_hours=monitor_hours,
            api_key=api_key,
            api_secret=api_secret,
        )
    if not _monitor_loop._running:
        await _monitor_loop.start()
        results["account_monitor"] = "started"
    else:
        results["account_monitor"] = "already_running"

    if _rebalance_worker is None:
        _rebalance_worker = RebalanceWorker(
            check_interval_min=rebalance_min,
        )
    if not _rebalance_worker._running:
        await _rebalance_worker.start()
        results["rebalance_worker"] = "started"
    else:
        results["rebalance_worker"] = "already_running"

    return results


async def stop_background_workers() -> None:
    global _monitor_loop, _rebalance_worker
    if _monitor_loop:
        await _monitor_loop.stop()
    if _rebalance_worker:
        await _rebalance_worker.stop()
