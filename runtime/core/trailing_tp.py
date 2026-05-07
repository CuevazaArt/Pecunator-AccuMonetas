"""T1.3: Trailing take-profit based on ATR.

When the current price exceeds the static TP level, a trailing stop is
activated at 1.5×ATR(14) below the highest price seen since activation.

This captures significantly more upside in strong moves while still
protecting profits on reversals.

Usage in bot runners:
    tracker = TrailingTP(atr_multiplier=Decimal("1.5"))
    # Each cycle:
    action = tracker.update(symbol, current_price, static_tp_price, klines_4h)
    if action == "SELL":
        execute_sell()
    elif action == "TRAILING":
        # In trailing mode, don't place static SELL LIMIT
        pass
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.core.trailing_tp")


def compute_atr(
    highs: list[Decimal],
    lows: list[Decimal],
    closes: list[Decimal],
    period: int = 14,
) -> Decimal:
    """Compute Average True Range from OHLC data."""
    n = len(closes)
    if n < period + 1:
        # Not enough data, return a wide default
        if highs and lows:
            return max(h - l for h, l in zip(highs[-5:], lows[-5:])) if len(highs) >= 5 else Decimal("0")
        return Decimal("0")

    tr_values: list[Decimal] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)

    # Wilder smoothing
    atr = sum(tr_values[:period], Decimal("0")) / Decimal(period)
    p = Decimal(period)
    for i in range(period, len(tr_values)):
        atr = (atr * (p - Decimal("1")) + tr_values[i]) / p

    return atr


class TrailingTP:
    """Per-symbol trailing take-profit tracker.

    States per symbol:
    - INACTIVE: price below static TP → normal SELL LIMIT behavior
    - TRAILING: price above static TP → track highest, trail at 1.5×ATR
    """

    def __init__(self, atr_multiplier: Decimal = Decimal("1.5")) -> None:
        self._multiplier = atr_multiplier
        # {symbol: {"highest": Decimal, "trail_stop": Decimal, "atr": Decimal}}
        self._state: dict[str, dict[str, Any]] = {}

    def update(
        self,
        symbol: str,
        current_price: Decimal,
        static_tp_price: Decimal,
        atr: Decimal,
    ) -> str:
        """Update trailing state and return action.

        Returns:
            "INACTIVE" - price below TP, use normal static TP
            "TRAILING" - in trailing mode, don't use static TP
            "SELL"     - trailing stop hit, execute market sell NOW
        """
        state = self._state.get(symbol)

        # Below static TP — inactive
        if current_price < static_tp_price:
            if state:
                # Price dropped below TP after being in trailing mode
                _LOG.info("trailing_tp: %s deactivated (price below TP)", symbol)
                del self._state[symbol]
            return "INACTIVE"

        trail_distance = atr * self._multiplier

        if state is None:
            # First time above TP — activate trailing
            trail_stop = current_price - trail_distance
            self._state[symbol] = {
                "highest": current_price,
                "trail_stop": trail_stop,
                "atr": atr,
                "activated_at": str(current_price),
            }
            _LOG.info(
                "trailing_tp: %s ACTIVATED at %s (trail_stop=%s, atr=%s)",
                symbol, current_price, trail_stop, atr,
            )
            return "TRAILING"

        # Update highest
        if current_price > state["highest"]:
            state["highest"] = current_price
            state["trail_stop"] = current_price - trail_distance
            state["atr"] = atr

        # Check if trail stop hit
        if current_price <= state["trail_stop"]:
            _LOG.info(
                "trailing_tp: %s SELL signal (price=%s <= trail_stop=%s, highest=%s)",
                symbol, current_price, state["trail_stop"], state["highest"],
            )
            del self._state[symbol]
            return "SELL"

        return "TRAILING"

    def status(self) -> dict[str, Any]:
        """Return current trailing state for all tracked symbols."""
        return {
            sym: {
                "highest": str(s["highest"]),
                "trail_stop": str(s["trail_stop"]),
                "atr": str(s["atr"]),
                "activated_at": s.get("activated_at", ""),
            }
            for sym, s in self._state.items()
        }


# ── Singleton ───────────────────────────────────────────────────────

_tracker: Optional[TrailingTP] = None


def get_trailing_tp() -> TrailingTP:
    """Get or create the global TrailingTP tracker."""
    global _tracker
    if _tracker is None:
        _tracker = TrailingTP()
    return _tracker
