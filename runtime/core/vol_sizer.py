"""T1.2: Volatility-targeting position sizer.

Instead of a fixed quote_order_qty (e.g., 8 USDT for everyone), this module
adjusts the order size inversely proportional to the symbol's realized
volatility:

    adjusted_qty = base_qty * (target_vol / realized_vol)

With floor (50% of base_qty) and ceiling (200% of base_qty) to prevent
extreme sizes.

Effect: A memecoin with 200% annualized vol gets ~40% of the qty
that BTC with 40% annualized vol would get.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

_LOG = logging.getLogger("pecunator.core.vol_sizer")

# Target annualized vol — the "neutral" reference point
DEFAULT_TARGET_VOL = Decimal("0.60")  # 60% annualized (mid-range crypto)


def compute_adjusted_qty(
    base_qty_usdt: Decimal,
    daily_closes: list[Decimal],
    *,
    lookback: int = 20,
    target_vol: Decimal = DEFAULT_TARGET_VOL,
    floor_pct: Decimal = Decimal("0.50"),
    ceiling_pct: Decimal = Decimal("2.00"),
) -> tuple[Decimal, dict[str, str]]:
    """Compute volatility-adjusted order quantity.

    Args:
        base_qty_usdt: The baseline order size (e.g., 8 USDT).
        daily_closes: List of daily close prices (most recent last).
        lookback: Number of days to compute realized vol.
        target_vol: The target annualized vol (neutral point).
        floor_pct: Minimum multiplier (0.50 = 50% of base).
        ceiling_pct: Maximum multiplier (2.00 = 200% of base).

    Returns:
        (adjusted_qty, diagnostics_dict)
    """
    if len(daily_closes) < lookback + 1:
        # Not enough data — return base qty unchanged
        return base_qty_usdt, {"reason": "insufficient_data", "adjusted": "false"}

    # Daily log returns
    returns: list[Decimal] = []
    for i in range(len(daily_closes) - lookback, len(daily_closes)):
        if daily_closes[i - 1] > 0:
            r = (daily_closes[i] - daily_closes[i - 1]) / daily_closes[i - 1]
            returns.append(r)

    if len(returns) < 5:
        return base_qty_usdt, {"reason": "insufficient_returns", "adjusted": "false"}

    # Realized vol (std of daily returns * sqrt(365))
    n = Decimal(len(returns))
    mean = sum(returns, Decimal("0")) / n
    variance = sum((r - mean) ** 2 for r in returns) / n
    daily_vol = variance.sqrt() if variance > 0 else Decimal("0")
    annualized_vol = daily_vol * Decimal("365").sqrt()

    if annualized_vol <= 0:
        return base_qty_usdt, {"reason": "zero_vol", "adjusted": "false"}

    # Multiplier = target_vol / realized_vol
    multiplier = target_vol / annualized_vol

    # Clamp to [floor, ceiling]
    multiplier = max(floor_pct, min(ceiling_pct, multiplier))

    adjusted = base_qty_usdt * multiplier

    diagnostics = {
        "base_qty": str(base_qty_usdt),
        "adjusted_qty": str(adjusted),
        "multiplier": str(multiplier),
        "annualized_vol": str(annualized_vol),
        "target_vol": str(target_vol),
        "daily_vol": str(daily_vol),
        "lookback": str(lookback),
        "adjusted": "true",
    }

    _LOG.debug(
        "vol_sizer: base=%s adj=%s mult=%.3f vol=%.1f%%",
        base_qty_usdt, adjusted, float(multiplier), float(annualized_vol * 100),
    )

    return adjusted, diagnostics
