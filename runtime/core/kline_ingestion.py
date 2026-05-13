"""Kline ingestion service — periodic fetch of OHLC + recursive HA storage.

Maintains a continuous chain of Heikin-Ashi values in `kline_history` for all
symbols traded by bots in the hub.

Lifecycle per (symbol, interval):
  1. Bootstrap (one-shot at startup): fetches ``bootstrap_candles`` history
     and stores them with recursively-computed HA. Older candles bootstrap the
     formula; later candles use the prior candle's HA → continuous chain.
  2. Periodic refresh: every ``poll_interval_sec``, fetches the last
     ``refresh_tail_candles`` candles and UPSERTs them (latest unclosed candle
     gets updated as it forms).

Symbols are discovered dynamically from the ``louise_bots`` table — when a new
bot is created with a new symbol, it is auto-bootstrapped on the next tick.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from runtime.api import deps
from runtime.core.louise_db import LouiseDB
from runtime.core.telemetry_vault import get_telemetry_vault

_LOG = logging.getLogger("pecunator.kline_ingestion")


class KlineIngestionService:
    """Singleton service that keeps kline_history fresh with HA continuity."""

    def __init__(
        self,
        intervals: tuple[str, ...] = ("1d",),
        bootstrap_candles: int = 500,
        poll_interval_sec: float = 300.0,
        refresh_tail_candles: int = 3,
    ) -> None:
        self._intervals = intervals
        self._bootstrap_candles = bootstrap_candles
        self._poll_interval_sec = poll_interval_sec
        self._refresh_tail_candles = refresh_tail_candles
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._bootstrapped: set[tuple[str, str]] = set()
        # Cache the DB handle — constructor runs schema init + migrations,
        # so instantiating per-tick would re-run those every cycle.
        self._db: Optional[LouiseDB] = None

    # ── Discovery ────────────────────────────────────────────────────

    def _symbols_in_use(self) -> set[str]:
        """Return set of symbols currently in use by any bot in louise_bots."""
        try:
            if self._db is None:
                self._db = LouiseDB()
            bots = self._db.get_all_bots()
            return {b["symbol"] for b in bots if b.get("symbol")}
        except Exception as e:
            _LOG.warning("Failed to discover symbols: %s", e)
            return set()

    # ── Lifecycle ────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop())
        _LOG.info(
            "KlineIngestionService started (intervals=%s, bootstrap=%d, poll=%.0fs)",
            self._intervals, self._bootstrap_candles, self._poll_interval_sec,
        )

    async def stop(self) -> None:
        self._stop.set()
        t = self._task
        if t is not None:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._task = None
        _LOG.info("KlineIngestionService stopped")

    # ── Main loop ────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOG.warning("Kline tick error: %s", e)
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self._poll_interval_sec
                )
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        ctx = deps.peek_ctx()
        if ctx is None or ctx.gateway is None:
            return
        client = getattr(ctx.gateway, "_client", None)
        if client is None:
            return

        symbols = self._symbols_in_use()
        if not symbols:
            return

        vault = get_telemetry_vault(ctx.config.data_dir)

        # Get server time once per tick to mark open vs closed candles
        try:
            srv = await client.get_server_time()
            server_ms = int((srv or {}).get("serverTime", 0)) or None
        except Exception:
            server_ms = None

        # Build (symbol, interval) work units and fetch them concurrently.
        # Each fetch is independent — gather amortizes round-trip latency.
        units = [(sym, iv) for sym in symbols for iv in self._intervals]

        async def _fetch_one(sym: str, iv: str):
            try:
                if (sym, iv) not in self._bootstrapped:
                    klines = await client.get_klines(
                        symbol=sym,
                        interval=iv,
                        limit=self._bootstrap_candles,
                    )
                    if klines:
                        vault.store_klines_with_ha(sym, iv, klines, server_ms)
                        self._bootstrapped.add((sym, iv))
                        _LOG.info(
                            "Bootstrapped %s %s with %d candles",
                            sym, iv, len(klines),
                        )
                else:
                    klines = await client.get_klines(
                        symbol=sym,
                        interval=iv,
                        limit=self._refresh_tail_candles,
                    )
                    if klines:
                        vault.store_klines_with_ha(sym, iv, klines, server_ms)
            except Exception as e:
                _LOG.warning("Kline fetch %s %s failed: %s", sym, iv, e)

        await asyncio.gather(
            *[_fetch_one(s, i) for s, i in units],
            return_exceptions=True,
        )


# ── Singleton ──────────────────────────────────────────────────────────

_service: Optional[KlineIngestionService] = None


def get_kline_ingestion_service() -> KlineIngestionService:
    global _service
    if _service is None:
        _service = KlineIngestionService()
    return _service
