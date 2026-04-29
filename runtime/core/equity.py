"""Account equity helpers (spot balances -> base asset) with rolling stats."""

from __future__ import annotations

from collections import deque
from decimal import Decimal, InvalidOperation
from typing import Any


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def build_ticker_price_map(raw_tickers: list[dict[str, Any]] | Any) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    if not isinstance(raw_tickers, list):
        return out
    for row in raw_tickers:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol", "")).strip().upper()
        if not sym:
            continue
        px = _dec(row.get("price"))
        if px > 0:
            out[sym] = px
    return out


def compute_spot_equity_in_base(
    balances: list[dict[str, Any]] | Any,
    ticker_prices: dict[str, Decimal],
    base_asset: str = "USDT",
) -> dict[str, Any]:
    base = (base_asset or "USDT").strip().upper() or "USDT"
    total = Decimal("0")
    missing_assets: list[str] = []
    converted_assets = 0

    rows = balances if isinstance(balances, list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        asset = str(row.get("asset", "")).strip().upper()
        if not asset:
            continue
        free = _dec(row.get("free"))
        locked = _dec(row.get("locked"))
        qty = free + locked
        if qty <= 0:
            continue
        if asset == base:
            total += qty
            converted_assets += 1
            continue

        direct = ticker_prices.get(f"{asset}{base}")
        if direct and direct > 0:
            total += qty * direct
            converted_assets += 1
            continue

        inverse = ticker_prices.get(f"{base}{asset}")
        if inverse and inverse > 0:
            total += qty / inverse
            converted_assets += 1
            continue

        missing_assets.append(asset)

    return {
        "base_asset": base,
        "current": str(total),
        "converted_assets": converted_assets,
        "missing_assets": missing_assets[:50],
        "missing_assets_count": len(missing_assets),
    }


class EquityRollingWindow:
    def __init__(self, sample_window: int = 6) -> None:
        self._window = max(1, min(int(sample_window), 300))
        self._history: dict[str, deque[Decimal]] = {}
        self._high_avg: dict[str, Decimal] = {}

    def update(self, *, base_asset: str, current: Decimal) -> dict[str, str]:
        base = (base_asset or "USDT").strip().upper() or "USDT"
        q = self._history.get(base)
        if q is None:
            q = deque(maxlen=self._window)
            self._history[base] = q
        q.append(current)
        avg = sum(q, Decimal("0")) / Decimal(len(q))
        prev = self._high_avg.get(base, Decimal("0"))
        high = avg if avg > prev else prev
        self._high_avg[base] = high
        return {
            "avg": str(avg),
            "high_avg": str(high),
            "samples": str(len(q)),
            "sample_window": str(self._window),
        }
