"""Kline Collector — Marginal historical data downloader for backtesting.

Downloads kline (candlestick) data from Binance using the MARGINAL budget
leftover after operations, diagnostics, and monitoring. Stores everything
in TelemetryVault for statistical analysis and future backtesting.

Design principles:
  - NEVER compete with trading or VMO for API weight
  - Only runs when ApiGovernor reports Binance in GREEN zone with >15% budget free
  - Downloads incrementally: newest-to-oldest, 500 candles per request (~5 weight)
  - Resilient: saves progress per (symbol, interval), resumes where it left off
  - Respects 1-second rate limit between REST calls

Usage:
    collector = KlineCollector(client, vault, governor)
    downloaded = await collector.collect_marginal(budget=50)
    # Returns number of candles downloaded using at most 50 weight
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from runtime.core.api_governor import get_api_governor, P_COLLECTION
from runtime.core.exception_zoo import get_exception_zoo
from runtime.core.telemetry_vault import get_telemetry_vault

_LOG = logging.getLogger("pecunator.core.kline_collector")

# Default collection targets: symbols × intervals
# Must cover ALL symbols actively operated by any bot:
#   Dorothy:   BTCUSDT, ETHUSDT, SOLUSDT
#   Masha:     BTCUSDT, ETHUSDT, BNBUSDT
#   Thusnelda: PEPEUSDT, SUIUSDT, NEARUSDT, INJUSDT, FETUSDT
_DEFAULT_TARGETS = [
    # Blue-chips (Dorothy + Masha) — deeper history
    ("BTCUSDT", "1h"), ("BTCUSDT", "4h"), ("BTCUSDT", "1d"),
    ("ETHUSDT", "1h"), ("ETHUSDT", "4h"), ("ETHUSDT", "1d"),
    ("SOLUSDT", "4h"), ("SOLUSDT", "1d"),
    ("BNBUSDT", "4h"), ("BNBUSDT", "1d"),
    # Volatile basket (Thusnelda) — 4h for oscillation analysis
    ("PEPEUSDT", "4h"), ("SUIUSDT", "4h"), ("NEARUSDT", "4h"),
    ("INJUSDT", "4h"), ("FETUSDT", "4h"),
]

KLINE_WEIGHT = 5  # Binance weight per klines request


class KlineCollector:
    """Marginal kline downloader using leftover API budget."""

    def __init__(
        self,
        binance_client: Any = None,
        targets: Optional[list[tuple[str, str]]] = None,
    ) -> None:
        self._client = binance_client
        self._targets = targets or list(_DEFAULT_TARGETS)
        self._governor = get_api_governor()
        self._vault = get_telemetry_vault()
        self._zoo = get_exception_zoo()

    def set_client(self, client: Any) -> None:
        """Set the Binance client (python-binance Client instance)."""
        self._client = client

    async def collect_marginal(self, budget: int = 50) -> dict[str, Any]:
        """Download klines using at most `budget` weight points.

        Returns summary of what was downloaded.
        """
        if self._client is None:
            return {"error": "No Binance client configured", "candles": 0}

        total_candles = 0
        total_weight = 0
        downloaded: list[dict[str, Any]] = []

        for symbol, interval in self._targets:
            if total_weight + KLINE_WEIGHT > budget:
                _LOG.info(
                    "KlineCollector: budget exhausted (%d/%d weight used)",
                    total_weight, budget,
                )
                break

            # Check with ApiGovernor before each request
            allowed, wait = self._governor.request_token(
                "binance", units=KLINE_WEIGHT,
                priority=P_COLLECTION, caller="kline_collector",
            )
            if not allowed:
                if wait == float('inf'):
                    _LOG.info("KlineCollector: Binance budget exhausted for today")
                    break
                _LOG.debug("KlineCollector: throttled, waiting %.1fs", wait)
                await asyncio.sleep(min(wait, 5.0))
                # Re-check after wait
                allowed, _ = self._governor.request_token(
                    "binance", units=KLINE_WEIGHT,
                    priority=P_COLLECTION, caller="kline_collector",
                )
                if not allowed:
                    continue

            # Find where we left off (get latest stored open_time)
            existing = self._vault.get_klines(symbol, interval, limit=1)
            end_time = None
            if existing:
                # Download OLDER data (before what we have)
                end_time = existing[-1].get("open_time")

            try:
                t0 = time.monotonic()
                klines = await asyncio.to_thread(
                    self._fetch_klines, symbol, interval, end_time
                )
                latency = int((time.monotonic() - t0) * 1000)

                if klines:
                    stored = self._vault.store_klines(symbol, interval, klines)
                    total_candles += stored
                    downloaded.append({
                        "symbol": symbol, "interval": interval,
                        "fetched": len(klines), "stored": stored,
                    })
                    _LOG.info(
                        "KlineCollector: %s/%s → %d fetched, %d new (%dms)",
                        symbol, interval, len(klines), stored, latency,
                    )

                total_weight += KLINE_WEIGHT
                self._governor.record_usage(
                    "binance", action=f"get_klines:{symbol}:{interval}",
                    units=KLINE_WEIGHT, priority=P_COLLECTION,
                    caller="kline_collector", latency_ms=latency,
                    success=True,
                )

                # Rate limit: 1 second between requests
                await asyncio.sleep(1.0)

            except Exception as exc:
                self._zoo.register(
                    exc, module="kline_collector",
                    context=f"collect:{symbol}/{interval}",
                )
                self._governor.record_usage(
                    "binance", action=f"get_klines:{symbol}:{interval}",
                    units=KLINE_WEIGHT, priority=P_COLLECTION,
                    caller="kline_collector", success=False,
                    error_type=type(exc).__name__,
                )
                _LOG.warning("KlineCollector: %s/%s failed: %s", symbol, interval, exc)
                continue

        return {
            "total_candles": total_candles,
            "total_weight": total_weight,
            "budget": budget,
            "pairs_processed": len(downloaded),
            "details": downloaded,
        }

    def _fetch_klines(
        self, symbol: str, interval: str, end_time: Optional[int] = None
    ) -> list[list]:
        """Synchronous fetch of klines from Binance REST API."""
        kwargs: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": 500,
        }
        if end_time:
            kwargs["endTime"] = end_time - 1  # Exclude the candle we already have

        return self._client.get_klines(**kwargs)

    async def get_coverage_report(self) -> list[dict[str, Any]]:
        """Return a summary of kline data coverage."""
        return self._vault.kline_coverage()


# ── Singleton ───────────────────────────────────────────────────────

_collector: Optional[KlineCollector] = None


def get_kline_collector() -> KlineCollector:
    global _collector
    if _collector is None:
        _collector = KlineCollector()
    return _collector
