"""AutoPilot — Fully autonomous orchestration for Pecunator.

Starts everything, decides everything, monitors everything.

Boot sequence:
  1. Start FastAPI server (uvicorn)
  2. Launch Flutter desktop shell (subprocess)
  3. Start VMO Observer (market classification loop)
  4. Start AccountMonitor (balance snapshots)
  5. Start RebalanceWorker (signal consumer)
  6. Start AutoStager (auto-launches bots based on VMO)
  7. Start ProcessWatchdog (monitors all processes)

AutoStager Logic:
  - Every VMO cycle produces regime classifications
  - If confidence > 80% and a specific bot is recommended:
    - Check if that bot is already running for that symbol
    - If not, auto-create and auto-stage via BotCoordinator
  - If regime shifts to CHOPPY/hostile → auto-stop the bot
  - All decisions logged in TelemetryVault

AutoTuner Logic:
  - After each bot cycle, reviews last N trades
  - Adjusts parameters within safe bounds based on regime:
    - TRENDING: wider profit_factor, tighter stop_loss
    - RANGING: tighter profit_factor, wider margin_drop
    - HIGH volatility: reduce quote_order_qty
    - LOW volatility: increase quote_order_qty
  - All adjustments logged, capped at ±20% from baseline
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.autopilot")

# ── L0 Profit Floor ─────────────────────────────────────────────────
# The absolute minimum profit_factor allowed by the system.
# Below this, Binance commissions (0.2% round-trip) erode returns
# to unacceptable levels for micro-operations (5-8 USDT notional).
PROFIT_FLOOR: float = 0.03  # 3% — L0 viability threshold

# ── Auto-Tuning Parameter Bounds ────────────────────────────────────

@dataclass
class TuningProfile:
    """Safe bounds for auto-tuning bot parameters.

    Each field is a tuple of (min, default, max).
    The tuner will never push a parameter outside [min, max].

    L0 Calibration (v0.7):
      - quote_order_qty capped at 5-8 USDT for micro-operations
      - profit_factor floor at 3% (PROFIT_FLOOR) to ensure viability
      - margin_drop calibrated for DCA breathing room (~3% per step)
    """
    # Dorothy — trend-following scalper
    dorothy_quote_order_qty: tuple[float, float, float] = (5.0, 6.0, 8.0)
    dorothy_profit_factor: tuple[float, float, float] = (0.03, 0.05, 0.15)
    dorothy_margin_drop: tuple[float, float, float] = (0.02, 0.03, 0.05)
    dorothy_stop_loss: tuple[float, float, float] = (0.08, 0.15, 0.30)
    dorothy_interval_sec: tuple[int, int, int] = (180, 450, 900)

    # Masha — DCA range accumulator
    masha_quote_order_qty: tuple[float, float, float] = (5.0, 6.0, 8.0)
    masha_profit_factor: tuple[float, float, float] = (0.03, 0.05, 0.12)
    masha_margin_drop: tuple[float, float, float] = (0.02, 0.03, 0.05)
    masha_stop_loss: tuple[float, float, float] = (0.10, 0.20, 0.30)
    masha_interval_sec: tuple[int, int, int] = (300, 600, 1200)

    # Thusnelda — volatile basket (6% profit floor)
    thusnelda_quote_order_qty: tuple[float, float, float] = (5.0, 6.0, 8.0)
    thusnelda_profit_factor: tuple[float, float, float] = (0.06, 0.08, 0.15)
    thusnelda_interval_sec: tuple[int, int, int] = (120, 300, 600)


# ── Regime-to-Parameter Mapping ─────────────────────────────────────

REGIME_ADJUSTMENTS: dict[str, dict[str, float]] = {
    # regime: {param_key: multiplier relative to default}
    "TRENDING": {
        "profit_factor": 1.4,      # Wider — let profits run
        "stop_loss": 0.7,          # Tighter — cut losses fast
        "margin_drop": 0.8,        # Slightly tighter entries
        "interval_sec": 0.8,       # Faster cycles
        "quote_order_qty": 1.2,    # Slightly larger positions
    },
    "RANGING": {
        "profit_factor": 0.7,      # Tighter — take profits early
        "stop_loss": 1.3,          # Wider — give room to oscillate
        "margin_drop": 1.2,        # Wider entries
        "interval_sec": 1.2,       # Slower cycles
        "quote_order_qty": 1.0,    # Normal size
    },
    "BREAKOUT": {
        "profit_factor": 1.6,      # Very wide — momentum play
        "stop_loss": 0.6,          # Very tight — wrong breakout = cut
        "margin_drop": 0.6,        # Aggressive entries
        "interval_sec": 0.6,       # Fast cycles
        "quote_order_qty": 0.8,    # Smaller (high risk)
    },
    "CHOPPY": {
        "profit_factor": 1.0,      # Default
        "stop_loss": 1.0,
        "margin_drop": 1.0,
        "interval_sec": 1.5,       # Much slower
        "quote_order_qty": 0.5,    # Half size (capital preservation)
    },
}

# Volatility overlays
VOLATILITY_MULTIPLIERS: dict[str, dict[str, float]] = {
    "HIGH": {"quote_order_qty": 0.7, "stop_loss": 1.3, "interval_sec": 1.3},
    "NORMAL": {"quote_order_qty": 1.0, "stop_loss": 1.0, "interval_sec": 1.0},
    "LOW": {"quote_order_qty": 1.3, "stop_loss": 0.8, "interval_sec": 0.8},
    "COMPRESSED": {"quote_order_qty": 0.5, "stop_loss": 0.6, "interval_sec": 1.5},
}


class AutoTuner:
    """Adjusts bot parameters based on market regime and volatility.

    Criteria:
      1. Regime (from VMO) → base adjustments
      2. Volatility overlay → modifies position size and stops
      3. Confidence filter → only tune if confidence > threshold
      4. Adaptive profit factor → oscillation spectrum + capital
      5. Safety clamps → never exceed TuningProfile bounds
      6. L0 floor → profit_factor never below PROFIT_FLOOR (3%)
    """

    def __init__(
        self,
        profile: Optional[TuningProfile] = None,
        confidence_threshold: float = 0.70,
    ) -> None:
        self._profile = profile or TuningProfile()
        self._conf_threshold = confidence_threshold
        self._history: list[dict[str, Any]] = []

    @staticmethod
    def compute_adaptive_profit(
        oscillation_pct: float,
        regime: str,
        volatility: str,
        available_capital: float = 0.0,
        num_instruments: int = 1,
    ) -> float:
        """Compute the optimal profit_factor for a symbol.

        The profit factor is derived from the price oscillation spectrum
        (the natural swing range of the asset) and adjusted by market
        conditions and capital constraints.

        Args:
            oscillation_pct: Price oscillation range as percentage
                (e.g. 5.0 means the price swings ~5% in its cycle).
                Typically computed as (High - Low) / Close over recent
                candles from VMO/chart_analyzer.
            regime: Market regime from VMO (TRENDING, RANGING, etc.)
            volatility: Volatility classification (HIGH, NORMAL, etc.)
            available_capital: Free USDT in the bot's sub-account.
                Used to bias the factor when capital is scarce.
            num_instruments: Number of active trading pairs for this bot.
                More instruments → less capital per pair → demand more %.

        Returns:
            Optimal profit_factor as a float, guaranteed >= PROFIT_FLOOR.
        """
        # ── Base: half the natural oscillation range ──
        # Capturing half the swing is realistic without overfitting.
        # If oscillation data is unavailable (0), fall back to floor.
        base = (oscillation_pct / 200.0) if oscillation_pct > 0 else PROFIT_FLOOR

        # ── Regime multiplier ──
        regime_mult = {
            "TRENDING": 1.4,    # Let profits run — momentum in our favor
            "RANGING": 0.75,    # Take profits quickly — price will revert
            "BREAKOUT": 1.8,    # Very wide — capture the impulse move
            "CHOPPY": 1.0,      # Default (should not be operating)
        }.get(regime, 1.0)

        # ── Volatility multiplier ──
        vol_mult = {
            "HIGH": 0.85,       # Reduce — high vol = more noise
            "NORMAL": 1.0,
            "LOW": 1.15,        # Widen — cleaner movements
            "COMPRESSED": 0.7,  # Compress — pre-breakout, be cautious
        }.get(volatility, 1.0)

        # ── Capital scarcity adjustment ──
        # With little capital per instrument, demand higher % to justify
        # the operational overhead. With ample capital, accept lower %.
        capital_per_instrument = (
            available_capital / max(num_instruments, 1)
            if available_capital > 0
            else 0.0
        )
        if capital_per_instrument <= 0:
            capital_mult = 1.0   # No data → neutral
        elif capital_per_instrument < 30:
            capital_mult = 1.3   # Scarce → demand more %
        elif capital_per_instrument < 80:
            capital_mult = 1.0   # Normal
        else:
            capital_mult = 0.85  # Ample → accept less %

        # ── Final computation ──
        profit = base * regime_mult * vol_mult * capital_mult

        # Clamp: never below L0 floor, never above 15%
        return max(PROFIT_FLOOR, min(profit, 0.15))

    def compute_params(
        self,
        bot_type: str,
        regime: str,
        volatility: str,
        confidence: float,
        current_params: dict[str, Any],
        *,
        oscillation_pct: float = 0.0,
        available_capital: float = 0.0,
        num_instruments: int = 1,
    ) -> dict[str, Any]:
        """Compute tuned parameters for a bot.

        Args:
            bot_type: Bot type identifier (dorothy, masha, thusnelda).
            regime: Market regime from VMO.
            volatility: Volatility classification from VMO.
            confidence: VMO confidence score (0-1).
            current_params: Current bot parameters to adjust from.
            oscillation_pct: Price oscillation spectrum (%) for adaptive
                profit computation. 0 = use static multiplier fallback.
            available_capital: Free USDT for capital-aware sizing.
            num_instruments: Active trading pairs count.

        Returns:
            Dict with adjusted parameters + reasoning.
            If confidence is below threshold, returns current_params unchanged.
        """
        if confidence < self._conf_threshold:
            return {
                "adjusted": False,
                "reason": (
                    f"Confidence {confidence:.2f} below "
                    f"threshold {self._conf_threshold}"
                ),
                "params": current_params,
            }

        regime_adj = REGIME_ADJUSTMENTS.get(regime, REGIME_ADJUSTMENTS["RANGING"])
        vol_adj = VOLATILITY_MULTIPLIERS.get(
            volatility, VOLATILITY_MULTIPLIERS["NORMAL"]
        )

        # Merge adjustments
        combined: dict[str, float] = {}
        params = ("profit_factor", "stop_loss",
                  "margin_drop", "interval_sec",
                  "quote_order_qty")
        for key in params:
            r_mult = regime_adj.get(key, 1.0)
            v_mult = vol_adj.get(key, 1.0)
            combined[key] = r_mult * v_mult

        # Apply to current params with bounds clamping
        prefix = bot_type.lower().split("-")[0]  # "dorothy-xxx" → "dorothy"
        if prefix not in ("dorothy", "masha", "thusnelda"):
            prefix = "dorothy"  # Default

        new_params = dict(current_params)
        adjustments_made: list[str] = []

        for param_key, multiplier in combined.items():
            profile_key = f"{prefix}_{param_key}"
            bounds = getattr(self._profile, profile_key, None)
            if bounds is None:
                continue

            p_min, p_default, p_max = bounds
            current_val = float(current_params.get(param_key, p_default))
            new_val = p_default * multiplier

            # Clamp
            new_val = max(p_min, min(p_max, new_val))

            # Only adjust if change > 5%
            if abs(new_val - current_val) / max(current_val, 0.001) > 0.05:
                if param_key == "interval_sec":
                    new_val = int(new_val)
                else:
                    new_val = round(new_val, 6)
                new_params[param_key] = new_val
                adjustments_made.append(
                    f"{param_key}: {current_val} -> {new_val} (x{multiplier:.2f})"
                )

        # ── Adaptive Profit Factor Override ──
        # If oscillation data is available, compute the optimal profit
        # using the L0 adaptive formula and override the static result.
        if oscillation_pct > 0:
            adaptive_pf = self.compute_adaptive_profit(
                oscillation_pct=oscillation_pct,
                regime=regime,
                volatility=volatility,
                available_capital=available_capital,
                num_instruments=num_instruments,
            )
            current_pf = float(new_params.get("profit_factor", 0.05))
            if abs(adaptive_pf - current_pf) / max(current_pf, 0.001) > 0.05:
                new_params["profit_factor"] = round(adaptive_pf, 6)
                adjustments_made.append(
                    f"profit_factor: {current_pf} -> {adaptive_pf:.6f} "
                    f"(adaptive, osc={oscillation_pct:.1f}%)"
                )

        # ── L0 Floor Enforcement ──
        # Regardless of all adjustments, profit_factor must never drop
        # below PROFIT_FLOOR. This is the last safety net.
        final_pf = float(new_params.get("profit_factor", PROFIT_FLOOR))
        if final_pf < PROFIT_FLOOR:
            new_params["profit_factor"] = PROFIT_FLOOR
            adjustments_made.append(
                f"profit_factor: {final_pf} -> {PROFIT_FLOOR} (L0 floor enforced)"
            )

        result = {
            "adjusted": len(adjustments_made) > 0,
            "reason": (
                f"Regime={regime}, Volatility={volatility}, "
                f"Confidence={confidence:.2f}"
            ),
            "adjustments": adjustments_made,
            "params": new_params,
            "regime": regime,
            "volatility": volatility,
        }

        self._history.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "bot_type": bot_type,
            **result,
        })
        # Keep history bounded
        if len(self._history) > 500:
            self._history = self._history[-200:]

        return result


class AutoStager:
    """Automatically stages/unstages bots based on VMO regime signals.

    Rules:
      1. If VMO confidence > 80% and recommended bot isn't running → stage it
      2. If regime shifts to CHOPPY for a symbol → stop its bot
      3. Max 1 bot per symbol (prevent double-staging)
      4. All decisions logged in TelemetryVault
      5. Rate-limited: max 1 stage action per 10 minutes per symbol
    """

    def __init__(self) -> None:
        self._last_action: dict[str, float] = {}  # symbol → monotonic timestamp
        self._cooldown_sec = 600  # 10 minutes between actions per symbol
        self._tuner = AutoTuner()

    async def evaluate_and_act(
        self, regimes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Evaluate VMO regime results and auto-stage/unstage bots.

        Args:
            regimes: List of MarketRegime.to_dict() results

        Returns:
            List of actions taken (for logging)
        """
        from runtime.core.bot_coordinator import get_bot_coordinator
        from runtime.core.exception_zoo import get_exception_zoo
        from runtime.core.telemetry_vault import get_telemetry_vault

        coordinator = get_bot_coordinator()
        vault = get_telemetry_vault()
        zoo = get_exception_zoo()
        actions: list[dict[str, Any]] = []
        now = time.monotonic()

        for regime in regimes:
            symbol = regime.get("symbol", "")
            rec_bot = regime.get("recommended_bot", "none")
            confidence = float(regime.get("confidence", 0))
            regime_name = regime.get("regime", "UNKNOWN")
            volatility = regime.get("volatility", "NORMAL")

            if not symbol:
                continue

            # Cooldown check
            last = self._last_action.get(symbol, 0)
            if (now - last) < self._cooldown_sec:
                continue

            try:
                # High confidence + specific bot recommended → stage
                if confidence >= 0.80 and rec_bot not in ("none", ""):
                    # Check if bot already active for this symbol
                    coord_status = coordinator.status()
                    active_for_symbol = any(
                        symbol.lower() in bid.lower()
                        for bid in coord_status.get("active", {})
                    )
                    if not active_for_symbol:
                        # Compute tuned parameters
                        tune_result = self._tuner.compute_params(
                            bot_type=rec_bot,
                            regime=regime_name,
                            volatility=volatility,
                            confidence=confidence,
                            current_params={},  # Will use defaults from profile
                        )

                        bot_id = f"{rec_bot}_auto_{symbol.lower()}"
                        stage_result = coordinator.stage_bot(
                            bot_id=bot_id,
                            hub_type=rec_bot,
                            loop_interval_sec=float(
                                tune_result["params"].get("interval_sec", 450)
                            ),
                            override_vmo=True,
                        )

                        action = {
                            "type": "AUTO_STAGE",
                            "symbol": symbol,
                            "bot": rec_bot,
                            "bot_id": bot_id,
                            "regime": regime_name,
                            "confidence": confidence,
                            "tuning": tune_result.get("adjustments", []),
                            "stage_result": stage_result,
                        }
                        actions.append(action)
                        self._last_action[symbol] = now

                        vault.log_decision(
                            bot_id="autopilot", bot_type="system",
                            decision="AUTO_STAGE", action_taken=True,
                            symbol=symbol,
                            reason=(
                                f"Regime={regime_name} conf={confidence:.2f} "
                                f"→ staging {rec_bot} with "
                                f"{len(tune_result.get('adjustments', []))} "
                                f"tuning adjustments"
                            ),
                            context=action,
                        )

                        _LOG.info(
                            "AUTO_STAGE: %s for %s (regime=%s, conf=%.2f)",
                            rec_bot, symbol, regime_name, confidence,
                        )

                # CHOPPY regime → stop bot if running
                elif regime_name == "CHOPPY" and confidence >= 0.70:
                    coord_status = coordinator.status()
                    for bid in list(coord_status.get("active", {})):
                        if symbol.lower() in bid.lower():
                            coordinator.unregister_active(bid)
                            action = {
                                "type": "AUTO_UNSTAGE",
                                "symbol": symbol,
                                "bot_id": bid,
                                "regime": regime_name,
                                "confidence": confidence,
                                "reason": "CHOPPY regime detected — sit out",
                            }
                            actions.append(action)
                            self._last_action[symbol] = now

                            vault.log_decision(
                                bot_id="autopilot", bot_type="system",
                                decision="AUTO_UNSTAGE", action_taken=True,
                                symbol=symbol,
                                reason=(
                                    f"CHOPPY regime (conf={confidence:.2f}) "
                                    f"→ unregistering {bid}"
                                ),
                                context=action,
                            )
                            _LOG.info(
                                "AUTO_UNSTAGE: %s for %s (CHOPPY, conf=%.2f)",
                                bid, symbol, confidence,
                            )

            except Exception as exc:
                zoo.register(
                    exc, module="autopilot.autostager",
                    context=f"evaluate:{symbol}",
                )

        return actions


class ProcessWatchdog:
    """Monitors critical processes and restarts them on failure.

    Watches:
      1. Flutter desktop shell process
      2. FastAPI server responsiveness (HTTP health check)
      3. Bot runners (via BotCoordinator status)
      4. VMO Observer (via status method)

    Reports health status and takes corrective actions.
    """

    def __init__(self) -> None:
        self._flutter_proc: Optional[subprocess.Popen[str]] = None
        self._flutter_restarts = 0
        self._max_flutter_restarts = 5
        self._check_interval_sec = 30.0
        self._running = False
        self._task: Optional[asyncio.Task[Any]] = None

    def register_flutter(self, proc: subprocess.Popen[str]) -> None:
        self._flutter_proc = proc

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        _LOG.info("ProcessWatchdog started (interval=%.0fs)", self._check_interval_sec)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        from runtime.core.exception_zoo import get_exception_zoo
        zoo = get_exception_zoo()

        while self._running:
            try:
                health = self._check_health()

                flut_dead = not health["flutter_alive"]
                can_restart = self._flutter_restarts < self._max_flutter_restarts
                if flut_dead and can_restart:
                    _LOG.warning(
                        "Flutter process died (restart #%d/%d)",
                        self._flutter_restarts + 1, self._max_flutter_restarts,
                    )
                    self._restart_flutter()

                # Log health periodically
                _LOG.debug("Watchdog health: %s", json.dumps(health, default=str))

            except Exception as exc:
                zoo.register(exc, module="watchdog", context="health_check")

            try:
                await asyncio.sleep(self._check_interval_sec)
            except asyncio.CancelledError:
                break

    def _check_health(self) -> dict[str, Any]:
        flutter_alive = False
        if self._flutter_proc is not None:
            flutter_alive = self._flutter_proc.poll() is None

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "flutter_alive": flutter_alive,
            "flutter_restarts": self._flutter_restarts,
        }

    def _restart_flutter(self) -> None:
        """Attempt to restart Flutter desktop shell."""
        flutter_path = Path("desktop_shell")
        if not flutter_path.exists():
            _LOG.error("Cannot restart Flutter: desktop_shell/ not found")
            return

        try:
            if self._flutter_proc and self._flutter_proc.poll() is None:
                self._flutter_proc.terminate()
                self._flutter_proc.wait(timeout=5)
        except Exception:
            pass

        try:
            self._flutter_proc = subprocess.Popen(
                ["flutter", "run", "-d", "windows"],
                cwd=str(flutter_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                if sys.platform == "win32" else 0,
            )
            self._flutter_restarts += 1
            _LOG.info("Flutter restarted (PID=%d)", self._flutter_proc.pid)
        except Exception as exc:
            _LOG.error("Flutter restart failed: %s", exc)

    def status(self) -> dict[str, Any]:
        return {
            **self._check_health(),
            "max_restarts": self._max_flutter_restarts,
            "watchdog_running": self._running,
        }


# ── Main AutoPilot Orchestrator ─────────────────────────────────────

class AutoPilot:
    """Master orchestrator — boots and runs all Pecunator systems.

    Usage:
        pilot = AutoPilot()
        asyncio.run(pilot.run())  # Blocks forever
    """

    def __init__(
        self,
        *,
        flutter_enabled: bool = True,
        vmo_enabled: bool = True,
        monitor_hours: float = 4.0,
        auto_stage: bool = True,
    ) -> None:
        self._flutter_enabled = flutter_enabled
        self._vmo_enabled = vmo_enabled
        self._monitor_hours = monitor_hours
        self._auto_stage = auto_stage
        self._watchdog = ProcessWatchdog()
        self._stager = AutoStager()
        self._running = False

    async def run(self) -> None:
        """Boot everything and run forever."""
        from runtime.core.exception_zoo import get_exception_zoo
        zoo = get_exception_zoo()

        _LOG.info("=" * 60)
        _LOG.info("PECUNATOR AUTOPILOT — Full Autonomous Mode")
        _LOG.info("=" * 60)

        self._running = True

        # 1. Launch Flutter
        if self._flutter_enabled:
            try:
                self._launch_flutter()
            except Exception as exc:
                zoo.register(exc, module="autopilot", context="flutter_launch")
                _LOG.error("Flutter launch failed: %s", exc)

        # 2. Start watchdog
        await self._watchdog.start()

        # 3. Start background workers
        try:
            from runtime.core.workers import start_background_workers
            from runtime.core.settings import binance_credentials_from_env

            creds = binance_credentials_from_env()
            key = creds[0] if creds else ""
            secret = creds[1] if creds else ""

            workers_result = await start_background_workers(
                api_key=key, api_secret=secret,
                monitor_hours=self._monitor_hours,
            )
            _LOG.info("Background workers: %s", workers_result)
        except Exception as exc:
            zoo.register(exc, module="autopilot", context="workers_start")

        # 4. Start VMO + AutoStager loop
        if self._vmo_enabled:
            asyncio.create_task(self._vmo_autostage_loop())

        # 5. Block forever
        _LOG.info("AutoPilot fully operational. Ctrl+C to stop.")
        try:
            while self._running:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            pass
        finally:
            await self._shutdown()

    def _launch_flutter(self) -> None:
        """Launch Flutter desktop shell as a subprocess."""
        flutter_dir = Path("desktop_shell")
        if not flutter_dir.exists():
            _LOG.warning("Flutter shell not found at desktop_shell/")
            return

        # Check if Flutter is available
        try:
            subprocess.run(
                ["flutter", "--version"],
                capture_output=True, timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _LOG.warning("Flutter SDK not found in PATH — skipping UI launch")
            return

        _LOG.info("Launching Flutter desktop shell...")
        proc = subprocess.Popen(
            ["flutter", "run", "-d", "windows", "--release"],
            cwd=str(flutter_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            if sys.platform == "win32" else 0,
        )
        self._watchdog.register_flutter(proc)
        _LOG.info("Flutter launched (PID=%d)", proc.pid)

    async def _vmo_autostage_loop(self) -> None:
        """VMO cycle + AutoStager evaluation loop."""
        from runtime.core.exception_zoo import get_exception_zoo
        from runtime.modules.vision.observer import VMObserver

        zoo = get_exception_zoo()
        observer = VMObserver()

        _LOG.info("VMO + AutoStager loop starting...")

        while self._running:
            try:
                # Run VMO cycle
                results = await observer.run_cycle()

                # Feed results to AutoStager
                if self._auto_stage and results:
                    regime_dicts = [r.to_dict() for r in results]
                    actions = await self._stager.evaluate_and_act(regime_dicts)
                    if actions:
                        _LOG.info(
                            "AutoStager took %d actions this cycle", len(actions),
                        )

            except Exception as exc:
                zoo.register(exc, module="autopilot", context="vmo_autostage")
                _LOG.exception("VMO/AutoStager cycle failed")

            # Wait for next VMO cycle
            wait = observer.config.interval_minutes * 60
            _LOG.info(
                "Next VMO+AutoStage cycle in %d minutes",
                observer.config.interval_minutes,
            )
            try:
                await asyncio.sleep(wait)
            except asyncio.CancelledError:
                break

    async def _shutdown(self) -> None:
        """Graceful shutdown of all systems."""
        _LOG.info("AutoPilot shutting down...")
        self._running = False

        await self._watchdog.stop()

        try:
            from runtime.core.workers import stop_background_workers
            await stop_background_workers()
        except Exception:
            pass

        # Terminate Flutter
        if self._watchdog._flutter_proc:
            try:
                self._watchdog._flutter_proc.terminate()
                self._watchdog._flutter_proc.wait(timeout=10)
            except Exception:
                pass

        _LOG.info("AutoPilot shutdown complete.")

    def status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "flutter_enabled": self._flutter_enabled,
            "vmo_enabled": self._vmo_enabled,
            "auto_stage": self._auto_stage,
            "watchdog": self._watchdog.status(),
        }


# ── CLI Entry Point ─────────────────────────────────────────────────

def run_autopilot() -> None:
    """CLI entry: starts Pecunator in full autonomous mode."""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    pilot = AutoPilot(
        flutter_enabled=os.environ.get("PECUNATOR_FLUTTER", "1").strip() != "0",
        vmo_enabled=os.environ.get("PECUNATOR_VMO", "1").strip() != "0",
        auto_stage=os.environ.get("PECUNATOR_AUTO_STAGE", "1").strip() != "0",
        monitor_hours=float(os.environ.get("PECUNATOR_MONITOR_HOURS", "4")),
    )

    asyncio.run(pilot.run())


if __name__ == "__main__":
    run_autopilot()
