"""ExchangeFilters — Universal Binance symbol precision & validation.

Fetches and caches LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL, and NOTIONAL
filters from exchangeInfo once per symbol, then provides:

  - quantize_qty(symbol, qty)   → valid stepSize-aligned quantity
  - quantize_price(symbol, px)  → valid tickSize-aligned price
  - validate_order(symbol, qty, price) → (ok, reason)
  - get_filters(symbol)         → raw filter dict

This eliminates per-bot ad-hoc precision handling and prevents
LOT_SIZE / MIN_NOTIONAL rejections that caused TP orphans.
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal, ROUND_DOWN
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.core.exchange_filters")

_ZERO = Decimal("0")


def _dec(v: Any, fallback: str = "0") -> Decimal:
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal(fallback)


def _step_decimals(step: str) -> int:
    """Number of decimal places implied by a step/tick size."""
    d = _dec(step, "1")
    if d <= 0 or d >= 1:
        return 0
    return max(0, -d.normalize().as_tuple().exponent)


class SymbolFilters:
    """Cached filter set for one Binance symbol."""

    __slots__ = (
        "symbol", "qty_step", "qty_decimals", "min_qty", "max_qty",
        "price_tick", "price_decimals", "min_price", "max_price",
        "min_notional", "fetched_at",
    )

    def __init__(self, symbol: str, info: dict[str, Any]) -> None:
        self.symbol = symbol
        self.fetched_at = time.monotonic()

        # Defaults
        self.qty_step = Decimal("0.00000001")
        self.qty_decimals = 8
        self.min_qty = Decimal("0.00000001")
        self.max_qty = Decimal("99999999")
        self.price_tick = Decimal("0.01")
        self.price_decimals = 2
        self.min_price = Decimal("0.00000001")
        self.max_price = Decimal("99999999")
        self.min_notional = Decimal("5")  # Binance default

        for flt in info.get("filters", []):
            ft = str(flt.get("filterType", "")).upper()

            if ft == "LOT_SIZE":
                self.qty_step = _dec(flt.get("stepSize", "0.00000001"))
                self.qty_decimals = _step_decimals(flt.get("stepSize", "0.00000001"))
                self.min_qty = _dec(flt.get("minQty", "0"))
                self.max_qty = _dec(flt.get("maxQty", "99999999"))

            elif ft == "PRICE_FILTER":
                self.price_tick = _dec(flt.get("tickSize", "0.01"))
                self.price_decimals = _step_decimals(flt.get("tickSize", "0.01"))
                self.min_price = _dec(flt.get("minPrice", "0"))
                self.max_price = _dec(flt.get("maxPrice", "99999999"))

            elif ft in ("MIN_NOTIONAL", "NOTIONAL"):
                self.min_notional = _dec(flt.get("minNotional", "5"))

    def quantize_qty(self, qty: Decimal) -> Decimal:
        """Round qty DOWN to the nearest valid stepSize multiple."""
        if self.qty_step <= 0:
            return round(qty, self.qty_decimals)
        return (qty // self.qty_step) * self.qty_step

    def quantize_price(self, price: Decimal) -> Decimal:
        """Round price to the nearest valid tickSize."""
        if self.price_tick <= 0:
            return round(price, self.price_decimals)
        return (price // self.price_tick) * self.price_tick

    def validate_order(
        self, qty: Decimal, price: Decimal
    ) -> tuple[bool, str]:
        """Validate qty × price against all Binance filters.

        Returns (True, "") if valid, (False, reason) if not.
        """
        if qty < self.min_qty:
            return False, f"qty {qty} < minQty {self.min_qty}"
        if qty > self.max_qty:
            return False, f"qty {qty} > maxQty {self.max_qty}"
        if price < self.min_price:
            return False, f"price {price} < minPrice {self.min_price}"
        if price > self.max_price:
            return False, f"price {price} > maxPrice {self.max_price}"
        notional = qty * price
        if notional < self.min_notional:
            return False, f"notional {notional} < minNotional {self.min_notional}"
        return True, ""


class ExchangeFilterCache:
    """Singleton cache of SymbolFilters.

    Fetches from Binance exchangeInfo once per symbol and caches
    indefinitely (symbol filters change very rarely).
    """

    def __init__(self) -> None:
        self._cache: dict[str, SymbolFilters] = {}

    def get(self, symbol: str) -> Optional[SymbolFilters]:
        return self._cache.get(symbol.upper())

    async def ensure_loaded(
        self, symbol: str, client: Any, *, _to_thread: Any = None
    ) -> SymbolFilters:
        """Load symbol filters from Binance if not already cached."""
        import asyncio

        key = symbol.upper()
        if key in self._cache:
            return self._cache[key]

        async def _run(fn: Any) -> Any:
            if _to_thread:
                return await _to_thread(fn)
            return await asyncio.get_running_loop().run_in_executor(None, fn)

        try:
            info = await _run(lambda: client.get_symbol_info(key))
            if info is None:
                _LOG.warning("ExchangeFilters: no info for %s — using defaults", key)
                info = {}
        except Exception as e:
            _LOG.warning("ExchangeFilters: failed to fetch %s — %s", key, e)
            info = {}

        sf = SymbolFilters(key, info)
        self._cache[key] = sf
        _LOG.info(
            "ExchangeFilters: %s loaded — qty_step=%s price_tick=%s min_notional=%s",
            key, sf.qty_step, sf.price_tick, sf.min_notional,
        )
        return sf

    def invalidate(self, symbol: str) -> None:
        self._cache.pop(symbol.upper(), None)


# ── Singleton ───────────────────────────────────────────────────────

_instance: Optional[ExchangeFilterCache] = None


def get_exchange_filters() -> ExchangeFilterCache:
    global _instance
    if _instance is None:
        _instance = ExchangeFilterCache()
    return _instance
