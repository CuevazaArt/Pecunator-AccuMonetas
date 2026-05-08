"""SymmetryGuard — Pre-flight validator for symmetric hub operation.

Ensures Dorothy (long) and Elphaba (short) can operate as a coherent
hedged pair before allowing either to trade. Prevents system corruption
from asymmetric capital depletion, symbol mismatches, or failed orders.

Checks performed:
  1. Symbol Parity: Both bots must target the same symbol(s)
  2. Capital Adequacy: Spot wallet (Dorothy) and Isolated Margin (Elphaba)
     must have minimum funds for their max exposure
  3. Asymmetry Detection: If one side has open positions but the other
     has no capital to match, operation is blocked
  4. Order Failure Tracking: Failed orders are counted; excessive failures
     trigger a hub-wide pause to prevent drift

Usage:
    guard = get_symmetry_guard()
    result = await guard.preflight(client, dorothy_cfg, elphaba_cfg)
    if not result["cleared"]:
        # Block both bots from operating
        print(result["blockers"])
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from runtime.bot._decimal_utils import dec as _dec

_LOG = logging.getLogger("pecunator.core.symmetry_guard")

# Module-level singleton
_instance: Optional[SymmetryGuard] = None
_lock = threading.Lock()


@dataclass
class HubHealth:
    """Snapshot of a symmetric hub's health at a point in time."""
    cleared: bool = False
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    spot_usdt_free: Decimal = Decimal("0")
    margin_usdt_free: Decimal = Decimal("0")
    dorothy_exposure: Decimal = Decimal("0")
    elphaba_exposure: Decimal = Decimal("0")
    dorothy_symbol: str = ""
    elphaba_symbol: str = ""
    ts: float = 0.0

    def as_json(self) -> dict[str, Any]:
        return {
            "cleared": self.cleared,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "spot_usdt_free": str(self.spot_usdt_free),
            "margin_usdt_free": str(self.margin_usdt_free),
            "dorothy_max_exposure": str(self.dorothy_exposure),
            "elphaba_max_exposure": str(self.elphaba_exposure),
            "dorothy_symbol": self.dorothy_symbol,
            "elphaba_symbol": self.elphaba_symbol,
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.ts)),
        }


class SymmetryGuard:
    """Validates pre-conditions for symmetric Dorothy+Elphaba operation.

    Designed to be called BEFORE each bot cycle or at hub startup.
    Results are cached for a configurable TTL to avoid redundant API calls.
    """

    # Minimum USDT buffer above max exposure (covers fees + slippage)
    CAPITAL_BUFFER_PCT = Decimal("0.10")  # 10% above max exposure
    # Max consecutive order failures before hub pause
    MAX_FAILURE_STREAK = 3
    # Cache TTL for preflight results (seconds)
    PREFLIGHT_CACHE_TTL = 120.0  # 2 minutes

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_health: Optional[HubHealth] = None
        self._failure_counts: dict[str, int] = {}  # bot_key -> consecutive failures
        self._hub_paused: bool = False
        self._pause_reason: str = ""

    # ── Order failure tracking ────────────────────────────────────

    def record_order_success(self, bot_key: str) -> None:
        """Reset failure counter on successful order."""
        with self._lock:
            self._failure_counts[bot_key] = 0

    def record_order_failure(self, bot_key: str, error: str) -> None:
        """Increment failure counter; pause hub if threshold exceeded."""
        with self._lock:
            count = self._failure_counts.get(bot_key, 0) + 1
            self._failure_counts[bot_key] = count
            if count >= self.MAX_FAILURE_STREAK:
                self._hub_paused = True
                self._pause_reason = (
                    f"Hub paused: {bot_key} hit {count} consecutive order failures. "
                    f"Last error: {error[:200]}"
                )
                _LOG.critical(self._pause_reason)

    def is_hub_paused(self) -> bool:
        return self._hub_paused

    def get_pause_reason(self) -> str:
        return self._pause_reason

    def reset_pause(self) -> None:
        """Manual reset after operator inspects the situation."""
        with self._lock:
            self._hub_paused = False
            self._pause_reason = ""
            self._failure_counts.clear()

    # ── Cached preflight ──────────────────────────────────────────

    def get_cached_health(self) -> Optional[HubHealth]:
        """Return last preflight result if within TTL."""
        h = self._last_health
        if h and (time.time() - h.ts) < self.PREFLIGHT_CACHE_TTL:
            return h
        return None

    # ── Core preflight check ──────────────────────────────────────

    async def preflight(
        self,
        client: Any,
        dorothy_cfg: Any,
        elphaba_cfg: Any,
        *,
        _to_thread: Any = None,
    ) -> HubHealth:
        """Run all pre-flight checks for symmetric hub operation.

        Args:
            client: Authenticated Binance client
            dorothy_cfg: DorothyConfig instance
            elphaba_cfg: ElphabaConfig instance
            _to_thread: async wrapper for sync calls (from BaseStrategyRunner)

        Returns:
            HubHealth with cleared=True if all checks pass
        """
        import asyncio

        async def _run(fn: Any) -> Any:
            if _to_thread:
                return await _to_thread(fn)
            return await asyncio.get_event_loop().run_in_executor(None, fn)

        health = HubHealth(ts=time.time())

        # ── Check 0: Hub pause (order failure streak) ─────────────
        if self._hub_paused:
            health.blockers.append(f"HUB_PAUSED: {self._pause_reason}")
            self._last_health = health
            return health

        # ── Check 1: Symbol parity ────────────────────────────────
        d_sym = str(getattr(dorothy_cfg, "symbol", "")).upper()
        e_sym = str(getattr(elphaba_cfg, "symbol", "")).upper()
        health.dorothy_symbol = d_sym
        health.elphaba_symbol = e_sym

        if not d_sym or not e_sym:
            health.blockers.append("SYMBOL_MISSING: One or both bots have no symbol configured")
        elif d_sym != e_sym:
            health.blockers.append(
                f"SYMBOL_MISMATCH: Dorothy={d_sym} vs Elphaba={e_sym}. "
                f"Symmetric hedge requires identical symbols."
            )

        # ── Check 2: Compute max exposure ─────────────────────────
        d_qty = _dec(getattr(dorothy_cfg, "quote_order_qty", "6"), "6")
        d_rungs = max(1, int(getattr(dorothy_cfg, "max_rungs_per_symbol", 3)))
        health.dorothy_exposure = d_qty * d_rungs

        e_qty = _dec(getattr(elphaba_cfg, "quote_order_qty", "6"), "6")
        e_rungs = max(1, int(getattr(elphaba_cfg, "max_rungs_per_symbol", 3)))
        health.elphaba_exposure = e_qty * e_rungs

        # ── Check 3: Exposure symmetry ────────────────────────────
        if health.dorothy_exposure != health.elphaba_exposure:
            health.warnings.append(
                f"EXPOSURE_ASYMMETRIC: Dorothy max={health.dorothy_exposure} USDT vs "
                f"Elphaba max={health.elphaba_exposure} USDT. Hedge may be imperfect."
            )

        # ── Check 4: Spot capital (Dorothy) ───────────────────────
        try:
            account = await _run(lambda: client.get_account())
            balances = account.get("balances", []) if isinstance(account, dict) else []
            for b in (balances if isinstance(balances, list) else []):
                if isinstance(b, dict) and str(b.get("asset", "")).upper() == "USDT":
                    health.spot_usdt_free = _dec(b.get("free", "0"), "0")
                    break
        except Exception as e:
            health.blockers.append(f"SPOT_QUERY_FAILED: {str(e)[:200]}")

        required_spot = health.dorothy_exposure * (Decimal("1") + self.CAPITAL_BUFFER_PCT)
        if health.spot_usdt_free < required_spot:
            health.blockers.append(
                f"SPOT_CAPITAL_LOW: Need {required_spot} USDT for Dorothy "
                f"(max_exposure={health.dorothy_exposure} + {self.CAPITAL_BUFFER_PCT*100}% buffer), "
                f"have {health.spot_usdt_free} USDT free."
            )

        # ── Check 5: Margin capital (Elphaba) ─────────────────────
        if e_sym:
            try:
                iso_account = await _run(
                    lambda: client.get_isolated_margin_account(symbols=e_sym)
                )
                assets = iso_account.get("assets", [])
                if assets and isinstance(assets, list):
                    pair = assets[0]
                    quote = pair.get("quoteAsset", {})
                    health.margin_usdt_free = _dec(quote.get("free", "0"), "0")
                    # Also check net asset (collateral health)
                    net = _dec(quote.get("netAsset", "0"), "0")
                    if net < Decimal("0"):
                        health.warnings.append(
                            f"MARGIN_NEGATIVE_NET: {e_sym} isolated margin has "
                            f"negative net USDT ({net}). Possible unreturned loan."
                        )
                else:
                    # No isolated margin account yet — need initial transfer
                    health.warnings.append(
                        f"MARGIN_WALLET_EMPTY: {e_sym} isolated margin not initialized. "
                        f"First trade will auto-transfer from Spot."
                    )
            except Exception as e:
                err_str = str(e)
                if "not enabled" in err_str.lower() or "-11001" in err_str:
                    health.blockers.append(
                        f"MARGIN_NOT_ENABLED: Isolated margin for {e_sym} is not "
                        f"activated on this Binance account."
                    )
                else:
                    health.warnings.append(f"MARGIN_QUERY_WARN: {err_str[:200]}")

            # Check total available = spot + margin for Elphaba's needs
            total_for_elphaba = health.spot_usdt_free + health.margin_usdt_free
            required_margin = health.elphaba_exposure * (Decimal("1") + self.CAPITAL_BUFFER_PCT)
            if total_for_elphaba < required_spot + required_margin:
                health.blockers.append(
                    f"TOTAL_CAPITAL_LOW: Combined Spot+Margin={total_for_elphaba} USDT "
                    f"insufficient for both Dorothy ({required_spot}) + Elphaba ({required_margin}) "
                    f"= {required_spot + required_margin} USDT needed."
                )

        # ── Check 6: Stop-loss configuration ──────────────────────
        d_sl = _dec(getattr(dorothy_cfg, "stop_loss_pct", "0"), "0")
        if d_sl > Decimal("0"):
            health.warnings.append(
                f"DOROTHY_HAS_STOP_LOSS: stop_loss_pct={d_sl}. L0 symmetric hub "
                f"doctrine recommends 0 (disabled) when paired with Elphaba."
            )

        # ── Verdict ───────────────────────────────────────────────
        health.cleared = len(health.blockers) == 0
        self._last_health = health
        return health

    # ── Static check (no API calls) ───────────────────────────────

    def check_config_only(
        self,
        dorothy_cfg: Any,
        elphaba_cfg: Any,
    ) -> HubHealth:
        """Quick config-only validation without API calls.

        Use this for instant feedback in the UI before starting bots.
        """
        health = HubHealth(ts=time.time())

        if self._hub_paused:
            health.blockers.append(f"HUB_PAUSED: {self._pause_reason}")
            return health

        d_sym = str(getattr(dorothy_cfg, "symbol", "")).upper()
        e_sym = str(getattr(elphaba_cfg, "symbol", "")).upper()
        health.dorothy_symbol = d_sym
        health.elphaba_symbol = e_sym

        if d_sym != e_sym:
            health.blockers.append(
                f"SYMBOL_MISMATCH: Dorothy={d_sym} vs Elphaba={e_sym}"
            )

        d_qty = _dec(getattr(dorothy_cfg, "quote_order_qty", "6"), "6")
        d_rungs = max(1, int(getattr(dorothy_cfg, "max_rungs_per_symbol", 3)))
        health.dorothy_exposure = d_qty * d_rungs

        e_qty = _dec(getattr(elphaba_cfg, "quote_order_qty", "6"), "6")
        e_rungs = max(1, int(getattr(elphaba_cfg, "max_rungs_per_symbol", 3)))
        health.elphaba_exposure = e_qty * e_rungs

        if health.dorothy_exposure != health.elphaba_exposure:
            health.warnings.append(
                f"EXPOSURE_ASYMMETRIC: Dorothy={health.dorothy_exposure} vs "
                f"Elphaba={health.elphaba_exposure} USDT"
            )

        d_sl = _dec(getattr(dorothy_cfg, "stop_loss_pct", "0"), "0")
        if d_sl > Decimal("0"):
            health.warnings.append(
                f"DOROTHY_STOP_LOSS_ACTIVE: {d_sl}. Recommend 0 for symmetric hub."
            )

        health.cleared = len(health.blockers) == 0
        return health

    # ── Capital Model: Spot-Only with On-Demand Margin Transfer ───
    #
    # All capital lives in Spot.  Elphaba's _ensure_collateral() auto-
    # transfers the needed USDT from Spot → Isolated Margin before each
    # short.  After covers, funds auto-return via AUTO_REPAY.
    #
    # compute_allocation() is for UI/planning display only.
    # rebalance() is an optional manual tool — NOT auto-invoked.

    # Minimum reserve per wallet: 3 operations × 6 USDT = 18 USDT
    MIN_RESERVE_USDT = Decimal("18")
    ACTIVE_RATIO = Decimal("0.75")
    INACTIVE_RATIO = Decimal("0.25")

    def compute_allocation(
        self,
        total_capital: Decimal,
        active_trend: str,
    ) -> dict[str, Any]:
        """Compute the target capital allocation based on active trend.

        Returns target amounts for Spot (Dorothy) and Margin (Elphaba)
        with minimum reserve floors.

        Args:
            total_capital: Total USDT available across both wallets
            active_trend: "BULLISH", "BEARISH", or "NEUTRAL"
        """
        MIN = self.MIN_RESERVE_USDT

        if total_capital < MIN * 2:
            return {
                "cleared": False,
                "blocker": f"CAPITAL_INSUFFICIENT: Need {MIN * 2} USDT minimum, have {total_capital}",
                "spot_target": total_capital / 2,
                "margin_target": total_capital / 2,
                "trend": active_trend,
            }

        if active_trend == "BULLISH":
            spot_raw = total_capital * self.ACTIVE_RATIO
            margin_raw = total_capital * self.INACTIVE_RATIO
        elif active_trend == "BEARISH":
            spot_raw = total_capital * self.INACTIVE_RATIO
            margin_raw = total_capital * self.ACTIVE_RATIO
        else:  # NEUTRAL
            spot_raw = total_capital / 2
            margin_raw = total_capital / 2

        # Enforce floor: both wallets must have >= MIN_RESERVE
        spot_target = max(spot_raw, MIN)
        margin_target = max(margin_raw, MIN)

        # If enforcing floor pushes above total, redistribute
        if spot_target + margin_target > total_capital:
            spot_target = total_capital / 2
            margin_target = total_capital / 2

        ops_spot = int(spot_target / Decimal("6"))
        ops_margin = int(margin_target / Decimal("6"))

        return {
            "cleared": True,
            "trend": active_trend,
            "total_capital": str(total_capital),
            "spot_target": str(spot_target),
            "margin_target": str(margin_target),
            "spot_ops_capacity": ops_spot,
            "margin_ops_capacity": ops_margin,
            "min_reserve_each": str(MIN),
        }

    async def rebalance(
        self,
        client: Any,
        symbol: str,
        active_trend: str,
        *,
        _to_thread: Any = None,
    ) -> dict[str, Any]:
        """Execute capital rebalance between Spot and Isolated Margin.

        Call this ONLY when trend direction changes. Moves excess USDT
        to the active wallet while maintaining MIN_RESERVE in both.
        """
        import asyncio

        async def _run(fn: Any) -> Any:
            if _to_thread:
                return await _to_thread(fn)
            return await asyncio.get_event_loop().run_in_executor(None, fn)

        MIN = self.MIN_RESERVE_USDT
        result: dict[str, Any] = {"action": "NONE", "trend": active_trend}

        # Query current balances
        try:
            account = await _run(lambda: client.get_account())
            spot_free = Decimal("0")
            for b in account.get("balances", []):
                if str(b.get("asset", "")).upper() == "USDT":
                    spot_free = _dec(b.get("free", "0"), "0")
                    break

            margin_free = Decimal("0")
            try:
                iso = await _run(
                    lambda: client.get_isolated_margin_account(symbols=symbol)
                )
                assets = iso.get("assets", [])
                if assets:
                    margin_free = _dec(assets[0].get("quoteAsset", {}).get("free", "0"), "0")
            except Exception:
                pass  # Margin wallet may not exist yet

            total = spot_free + margin_free
            result["spot_before"] = str(spot_free)
            result["margin_before"] = str(margin_free)
            result["total"] = str(total)

        except Exception as e:
            result["action"] = "QUERY_FAILED"
            result["error"] = str(e)[:200]
            return result

        if total < MIN * 2:
            result["action"] = "CAPITAL_INSUFFICIENT"
            result["alert"] = f"Total {total} USDT < minimum {MIN * 2} USDT"
            _LOG.critical("REBALANCE BLOCKED: %s", result["alert"])
            return result

        # Compute targets
        alloc = self.compute_allocation(total, active_trend)
        spot_target = _dec(alloc["spot_target"], "0")
        margin_target = _dec(alloc["margin_target"], "0")
        result["spot_target"] = str(spot_target)
        result["margin_target"] = str(margin_target)

        # Determine transfer direction and amount
        if spot_free > spot_target and margin_free < margin_target:
            # Move from Spot → Margin
            transfer_amt = min(spot_free - spot_target, margin_target - margin_free)
            # Ensure we don't drop Spot below MIN
            transfer_amt = min(transfer_amt, spot_free - MIN)
            if transfer_amt > Decimal("1"):  # Minimum meaningful transfer
                try:
                    await _run(lambda: client.transfer_spot_to_isolated_margin(
                        asset="USDT", symbol=symbol, amount=str(transfer_amt),
                    ))
                    result["action"] = "TRANSFER_SPOT_TO_MARGIN"
                    result["amount"] = str(transfer_amt)
                    _LOG.info("Rebalanced %.2f USDT Spot→Margin for %s", transfer_amt, symbol)
                except Exception as e:
                    result["action"] = "TRANSFER_FAILED"
                    result["error"] = str(e)[:200]
            else:
                result["action"] = "NO_TRANSFER_NEEDED"

        elif margin_free > margin_target and spot_free < spot_target:
            # Move from Margin → Spot
            transfer_amt = min(margin_free - margin_target, spot_target - spot_free)
            transfer_amt = min(transfer_amt, margin_free - MIN)
            if transfer_amt > Decimal("1"):
                try:
                    await _run(lambda: client.transfer_isolated_margin_to_spot(
                        asset="USDT", symbol=symbol, amount=str(transfer_amt),
                    ))
                    result["action"] = "TRANSFER_MARGIN_TO_SPOT"
                    result["amount"] = str(transfer_amt)
                    _LOG.info("Rebalanced %.2f USDT Margin→Spot for %s", transfer_amt, symbol)
                except Exception as e:
                    result["action"] = "TRANSFER_FAILED"
                    result["error"] = str(e)[:200]
            else:
                result["action"] = "NO_TRANSFER_NEEDED"
        else:
            result["action"] = "ALREADY_BALANCED"

        return result


def get_symmetry_guard() -> SymmetryGuard:
    """Module-level singleton accessor."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = SymmetryGuard()
    return _instance
