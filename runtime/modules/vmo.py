"""Visual Market Observer (VMO) — Chart-IMG Integration.

Fetches advanced trading charts for S/A grade symbols to enable visual
validation for risk-averse autonomous trading.
"""

from __future__ import annotations

import logging
import asyncio
import os
from pathlib import Path
from typing import Optional

import requests

from runtime.core.api_governor import get_api_governor, P_DIAGNOSIS

_LOG = logging.getLogger("pecunator.modules.vmo")

# Chart-IMG API key — read exclusively from environment.
CHART_IMG_API_KEY = os.environ.get("CHART_IMG_API_KEY", "")
CHART_IMG_URL = "https://api.chart-img.com/v2/tradingview/advanced-chart"

class VisualMarketObserver:
    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or Path("data/vmo")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._governor = get_api_governor()

    def _fetch_chart_sync(self, symbol: str, interval: str) -> Optional[Path]:
        """Fetch a single chart using Chart-IMG synchronously."""
        # Request token from API Governor
        allowed, wait_sec = self._governor.request_token(
            service="chart-img",
            units=1,
            priority=P_DIAGNOSIS,
            caller=f"VMO:{symbol}:{interval}"
        )
        
        if not allowed:
            _LOG.warning("VMO: Chart-IMG request denied by governor (wait=%s)", wait_sec)
            return None

        # Format symbol for Chart-IMG (e.g. BINANCE:BTCUSDT)
        chart_symbol = f"BINANCE:{symbol.upper()}"
        
        payload = {
            "symbol": chart_symbol,
            "interval": interval,
            "style": "heikinAshi",
            "theme": "dark",
            "width": 800,
            "height": 500,
            "timezone": "UTC",
            "studies": [
                {
                    "name": "Bollinger Bands",
                    "input": {"length": 20, "stdDev": 2}
                },
                {
                    "name": "Relative Strength Index",
                    "input": {"length": 14}
                },
                {
                    "name": "Volume"
                }
            ],
        }

        headers = {
            "x-api-key": CHART_IMG_API_KEY,
            "Content-Type": "application/json",
        }

        success = False
        error_msg = ""
        latency_ms = 0
        path = self._data_dir / f"{symbol}_{interval}.png"
        
        try:
            import time
            t0 = time.monotonic()
            resp = requests.post(CHART_IMG_URL, headers=headers, json=payload, timeout=15)
            latency_ms = int((time.monotonic() - t0) * 1000)
            
            if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
                with open(path, "wb") as f:
                    f.write(resp.content)
                success = True
                _LOG.info("VMO: Downloaded chart %s %s", symbol, interval)
                return path
            else:
                error_msg = f"HTTP {resp.status_code}: {resp.text[:100]}"
                _LOG.error("VMO: Failed to fetch chart: %s", error_msg)
                return None
        except Exception as e:
            error_msg = str(e)
            _LOG.error("VMO: Exception fetching chart: %s", e)
            return None
        finally:
            self._governor.record_usage(
                service="chart-img",
                action=f"fetch_chart_{interval}",
                units=1,
                priority=P_DIAGNOSIS,
                caller=f"VMO:{symbol}",
                latency_ms=latency_ms,
                success=success,
                error_type=error_msg
            )

    async def fetch_triplet(self, symbol: str) -> dict[str, Optional[Path]]:
        """Fetch 4h, 1d, and 1w charts for the given symbol sequentially.

        Governor gating happens inside ``_fetch_chart_sync`` — no need to
        double-call ``request_token`` here.
        """
        intervals = ["4h", "1d", "1w"]
        loop = asyncio.get_running_loop()

        results = {}
        for iv in intervals:
            path = await loop.run_in_executor(None, self._fetch_chart_sync, symbol, iv)
            results[iv] = path

        return results

_instance: Optional[VisualMarketObserver] = None

def get_vmo() -> VisualMarketObserver:
    global _instance
    if _instance is None:
        _instance = VisualMarketObserver()
    return _instance
