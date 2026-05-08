"""OrphanGuard — Lightweight janitor for orphaned positions.

Scans for positions (long holdings / short borrows) that don't have
a matching take-profit order. Attempts to place the missing TP and
alerts on failure.

Designed to run as a periodic watchdog (every ~10 minutes) instead
of bloating the main bot logic with retry machinery.

Orphan scenarios detected:
  Dorothy: Asset bought (XRP in Spot) but no SELL LIMIT exists
  Elphaba: Short borrowed (XRP debt in Margin) but no BUY LIMIT exists
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Optional

from runtime.bot._decimal_utils import dec as _dec, quantize as _q

_LOG = logging.getLogger("pecunator.core.orphan_guard")


class OrphanGuard:
    """Periodic scanner for orphaned positions without matching TP orders."""

    # Minimum interval between scans (seconds)
    SCAN_INTERVAL_SEC = 600.0  # 10 minutes
    # How far back to consider a position "stale" enough to be orphaned
    MAX_RETRY_ATTEMPTS = 3

    def __init__(self) -> None:
        self._last_scan_mono: float = 0.0
        self._retry_counts: dict[str, int] = {}  # key → attempts
        self._orphans: list[dict[str, Any]] = []

    def needs_scan(self) -> bool:
        if self._last_scan_mono == 0.0:
            return True
        return (time.monotonic() - self._last_scan_mono) >= self.SCAN_INTERVAL_SEC

    # ── Dorothy orphan detection ──────────────────────────────────

    async def scan_dorothy_orphans(
        self,
        client: Any,
        symbol: str,
        bot_tag: str,
        config: Any,
        *,
        _to_thread: Any = None,
    ) -> list[dict[str, Any]]:
        """Detect Spot holdings without a matching SELL LIMIT.

        A Dorothy orphan is: asset balance > 0 in Spot but no tagged
        SELL LIMIT order exists for that symbol.
        """
        import asyncio

        async def _run(fn: Any) -> Any:
            if _to_thread:
                return await _to_thread(fn)
            return await asyncio.get_event_loop().run_in_executor(None, fn)

        orphans: list[dict[str, Any]] = []

        try:
            # Get open orders
            open_orders = await _run(
                lambda: client.get_open_orders(symbol=symbol)
            )
            if not isinstance(open_orders, list):
                open_orders = []

            # Count tagged sell limits
            my_sells = [
                o for o in open_orders
                if (str(o.get("side")) == "SELL"
                    and str(o.get("type")) == "LIMIT"
                    and str(o.get("clientOrderId", "")).startswith(bot_tag))
            ]

            # Get asset balance
            base_asset = symbol.replace("USDT", "")
            account = await _run(lambda: client.get_account())
            asset_free = Decimal("0")
            for b in account.get("balances", []):
                if str(b.get("asset", "")).upper() == base_asset:
                    asset_free = _dec(b.get("free", "0"), "0")
                    break

            # Orphan: have asset but no sell limit
            min_qty = config.quote_order_qty / Decimal("1000")  # Negligible threshold
            if asset_free > min_qty and len(my_sells) == 0:
                orphans.append({
                    "type": "DOROTHY_ORPHAN",
                    "symbol": symbol,
                    "asset_free": str(asset_free),
                    "base_asset": base_asset,
                    "missing": "SELL_LIMIT",
                    "detected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })

        except Exception as e:
            _LOG.warning("Dorothy orphan scan failed: %s", e)

        return orphans

    # ── Elphaba orphan detection ──────────────────────────────────

    async def scan_elphaba_orphans(
        self,
        client: Any,
        symbol: str,
        bot_tag: str,
        *,
        _to_thread: Any = None,
    ) -> list[dict[str, Any]]:
        """Detect Margin short positions without a matching BUY LIMIT.

        An Elphaba orphan is: borrowed base asset > 0 but no tagged
        BUY LIMIT order exists for that symbol in isolated margin.
        """
        import asyncio

        async def _run(fn: Any) -> Any:
            if _to_thread:
                return await _to_thread(fn)
            return await asyncio.get_event_loop().run_in_executor(None, fn)

        orphans: list[dict[str, Any]] = []

        try:
            # Get isolated margin account
            iso_account = await _run(
                lambda: client.get_isolated_margin_account(symbols=symbol)
            )
            assets = iso_account.get("assets", [])
            if not assets:
                return orphans

            pair = assets[0] if isinstance(assets, list) else {}
            base_asset_info = pair.get("baseAsset", {})
            borrowed = _dec(base_asset_info.get("borrowed", "0"), "0")
            interest = _dec(base_asset_info.get("interest", "0"), "0")
            total_debt = borrowed + interest

            if total_debt <= Decimal("0"):
                return orphans  # No short position

            # Get open margin orders
            open_orders = await _run(
                lambda: client.get_open_margin_orders(
                    symbol=symbol, isIsolated="TRUE"
                )
            )
            if not isinstance(open_orders, list):
                open_orders = []

            # Count tagged buy limits (TP covers)
            my_buys = [
                o for o in open_orders
                if (str(o.get("side")) == "BUY"
                    and str(o.get("type")) == "LIMIT"
                    and str(o.get("clientOrderId", "")).startswith(bot_tag))
            ]

            # Orphan: have debt but no cover order
            if len(my_buys) == 0:
                orphans.append({
                    "type": "ELPHABA_ORPHAN",
                    "symbol": symbol,
                    "borrowed": str(borrowed),
                    "interest": str(interest),
                    "total_debt": str(total_debt),
                    "missing": "BUY_LIMIT_COVER",
                    "detected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })

        except Exception as e:
            _LOG.warning("Elphaba orphan scan failed: %s", e)

        return orphans

    # ── Combined scan ─────────────────────────────────────────────

    async def scan_all(
        self,
        client: Any,
        symbol: str,
        dorothy_tag: str,
        elphaba_tag: str,
        dorothy_config: Any,
        *,
        _to_thread: Any = None,
    ) -> dict[str, Any]:
        """Run both orphan scans and return combined report."""
        self._last_scan_mono = time.monotonic()

        d_orphans = await self.scan_dorothy_orphans(
            client, symbol, dorothy_tag, dorothy_config,
            _to_thread=_to_thread,
        )
        e_orphans = await self.scan_elphaba_orphans(
            client, symbol, elphaba_tag,
            _to_thread=_to_thread,
        )

        all_orphans = d_orphans + e_orphans
        self._orphans = all_orphans

        for orphan in all_orphans:
            _LOG.critical(
                "ORPHAN DETECTED: %s %s — missing %s",
                orphan["type"], orphan["symbol"], orphan["missing"],
            )

        return {
            "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "symbol": symbol,
            "orphans_found": len(all_orphans),
            "orphans": all_orphans,
            "healthy": len(all_orphans) == 0,
        }

    def get_last_orphans(self) -> list[dict[str, Any]]:
        """Return last scan results."""
        return list(self._orphans)


# ── Singleton ───────────────────────────────────────────────────────

_instance: Optional[OrphanGuard] = None


def get_orphan_guard() -> OrphanGuard:
    global _instance
    if _instance is None:
        _instance = OrphanGuard()
    return _instance
