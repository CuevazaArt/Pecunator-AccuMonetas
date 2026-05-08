"""VMO Observer — Orchestrates capture → analysis → cache cycles.

The observer is the top-level coordinator for the Visual Market Observer.
It runs scheduled capture cycles across all configured symbols and timeframes,
analyses each chart image via LLM Vision, and stores the results.

Usage:
    # Single cycle (for testing)
    python -m runtime.modules.vision.observer --once

    # Continuous mode (production)
    python -m runtime.modules.vision.observer
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from runtime.modules.vision.chart_capture import (
    capture_chart,
    prune_old_captures,
)
from runtime.modules.vision.chart_analyzer import MarketRegime, classify_chart
from runtime.modules.vision.config import get_vmo_config, VMOConfig
from runtime.modules.vision.regime_cache import RegimeCache
from runtime.core.api_governor import get_api_governor, P_DIAGNOSIS
from runtime.core.exception_zoo import get_exception_zoo
from runtime.core.telemetry_vault import get_telemetry_vault

_LOG = logging.getLogger("pecunator.vmo.observer")


class VMObserver:
    """Orchestrates VMO capture-analyse-store cycles."""

    def __init__(self, config: Optional[VMOConfig] = None):
        self.config = config or get_vmo_config()
        self._cache = RegimeCache(self.config.db_path)
        self._last_cycle_at: Optional[str] = None
        self._last_cycle_results: list[MarketRegime] = []
        self._total_cycles: int = 0
        self._running = False

    # ── Single cycle ────────────────────────────────────────────────

    async def run_cycle(self) -> list[MarketRegime]:
        """Run one full capture+analysis cycle across all symbols/timeframes.

        Returns list of MarketRegime classifications.
        """
        cfg = self.config
        results: list[MarketRegime] = []
        total = len(cfg.symbols) * len(cfg.timeframes)
        # Dynamically calculate which timeframes to process now
        now_utc = datetime.now(timezone.utc)
        active_pairs = []
        for tf in cfg.timeframes:
            # For 1d timeframe, only process around midnight UTC (00:xx)
            if tf == "1d" and now_utc.hour != 0:
                _LOG.info("Skipping 1d timeframe (only runs at 00:xx UTC)")
                continue
            for symbol in cfg.symbols:
                active_pairs.append((symbol, tf))

        if not active_pairs:
            _LOG.info("No timeframes scheduled for current hour. Cycle skipped.")
            return []

        _LOG.info(
            "Starting VMO cycle: %d symbols × dynamic timeframes = %d captures scheduled",
            len(cfg.symbols), len(active_pairs),
        )

        t0 = time.monotonic()
        
        # Concurrency limit to respect free tier rate limits while speeding up
        # Gemini 2.5 Flash can handle ~15 RPM for free tier.
        # chart-img has ~100 RPM.
        # We use a semaphore of 3 to be safe.
        sem = asyncio.Semaphore(1)
        
        async def _bounded_capture(sym: str, tf: str) -> Optional[MarketRegime]:
            async with sem:
                try:
                    return await self._capture_and_classify(sym, tf)
                except Exception as e:
                    _LOG.error("VMO cycle error for %s/%s: %s", sym, tf, e)
                    return None
                finally:
                    if cfg.capture_delay_sec > 0:
                        await asyncio.sleep(cfg.capture_delay_sec)
                        
        tasks = [
            _bounded_capture(symbol, timeframe)
            for symbol, timeframe in active_pairs
        ]
        
        raw_results = await asyncio.gather(*tasks)
        results = [r for r in raw_results if r is not None]
        
        completed = len(results)
        failed = total - completed

        elapsed = round(time.monotonic() - t0, 1)
        self._last_cycle_at = datetime.now(timezone.utc).isoformat()
        self._last_cycle_results = results
        self._total_cycles += 1

        # Prune old captures
        try:
            prune_old_captures(
                cfg.captures_dir, cfg.png_retention_hours
            )
        except Exception:
            pass

        _LOG.info(
            "VMO cycle complete: %d/%d ok, %d failed, %.1fs total",
            completed, total, failed, elapsed,
        )
        return results

    async def _capture_and_classify(
        self, symbol: str, timeframe: str
    ) -> MarketRegime:
        """Capture one chart and classify it."""
        cfg = self.config

        # Resilience: Circuit Breaker / Exponential Backoff
        max_retries = 3
        base_delay = 5.0

        governor = get_api_governor()
        zoo = get_exception_zoo()
        vault = get_telemetry_vault()

        for attempt in range(1, max_retries + 1):
            try:
                # Step 0: Ask ApiGovernor for Chart-Img permission
                allowed, wait = governor.request_token(
                    "chart-img", units=1, priority=P_DIAGNOSIS,
                    caller=f"vmo:{symbol}/{timeframe}",
                )
                if not allowed:
                    if wait == float('inf'):
                        raise RuntimeError("Chart-Img daily quota exhausted")
                    _LOG.info("VMO: Chart-Img throttled, waiting %.1fs", wait)
                    await asyncio.sleep(wait)

                # Step 1: Capture
                t_cap = time.monotonic()
                cap = await capture_chart(
                    symbol, timeframe,
                    source=cfg.capture_source,
                    api_key=cfg.chart_img_api_key,
                    base_url=cfg.chart_img_base_url,
                    save_dir=cfg.captures_dir,
                )
                cap_ms = int((time.monotonic() - t_cap) * 1000)
                governor.record_usage(
                    "chart-img", action=f"capture:{symbol}/{timeframe}",
                    units=1, priority=P_DIAGNOSIS,
                    caller="vmo", latency_ms=cap_ms,
                    success=cap.ok, error_type=cap.error or "",
                )

                if not cap.ok:
                    raise RuntimeError(f"Capture failed: {cap.error}")

                # Index capture in TelemetryVault
                if cap.saved_path:
                    vault.index_capture(
                        symbol=symbol, timeframe=timeframe,
                        captured_at=cap.captured_at,
                        file_path=str(cap.saved_path),
                        file_size=len(cap.png) if cap.png else 0,
                        source=cap.source,
                        indicators="RSI:14,MACD,BB:20,2",
                    )

                # Step 1.5: Retrieve Historical Context
                past_regimes = self._cache.get_latest(symbol, timeframe, limit=3)
                history_context = "\n".join(
                    [f"- {r.captured_at}: {r.regime} (Bot: {r.recommended_bot})" for r in past_regimes]
                ) if past_regimes else "No history available."

                # Step 2: Ask ApiGovernor for LLM permission
                llm_svc = "gemini" if cfg.llm_provider != "openai" else "openai"
                allowed, wait = governor.request_token(
                    llm_svc, units=1, priority=P_DIAGNOSIS,
                    caller=f"vmo:{symbol}/{timeframe}",
                )
                if not allowed and wait != float('inf'):
                    _LOG.info("VMO: %s throttled, waiting %.1fs", llm_svc, wait)
                    await asyncio.sleep(wait)

                # Step 2b: Classify
                t_llm = time.monotonic()
                regime = await classify_chart(
                    cap.png, symbol, timeframe,
                    provider=cfg.llm_provider,
                    model=cfg.llm_model,
                    gemini_api_key=cfg.gemini_api_key,
                    openai_api_key=cfg.openai_api_key,
                    captured_at=cap.captured_at,
                    capture_source=cap.source,
                    history_context=history_context,
                )
                llm_ms = int((time.monotonic() - t_llm) * 1000)
                governor.record_usage(
                    llm_svc, action=f"classify:{symbol}/{timeframe}",
                    units=1, priority=P_DIAGNOSIS,
                    caller="vmo", latency_ms=llm_ms, success=True,
                )

                # Update capture index with regime result
                if cap.saved_path:
                    vault.index_capture(
                        symbol=symbol, timeframe=timeframe,
                        captured_at=cap.captured_at,
                        file_path=str(cap.saved_path),
                        regime=regime.regime,
                        confidence=regime.confidence,
                        recommended_bot=regime.recommended_bot,
                    )

                # Success
                break

            except Exception as e:
                zoo.register(e, module="vmo.observer", context=f"{symbol}/{timeframe}/attempt={attempt}")
                _LOG.warning(
                    "VMO _capture_and_classify attempt %d failed for %s/%s: %s", 
                    attempt, symbol, timeframe, e
                )
                if attempt == max_retries:
                    # Return safe default after max retries
                    regime = MarketRegime(
                        symbol=symbol, timeframe=timeframe,
                        trend="LATERAL", trend_strength="WEAK",
                        volatility="NORMAL", regime="RANGING",
                        confidence=0.0, recommended_bot="none",
                        risk_level="HIGH",
                        notes=f"All {max_retries} attempts failed. Last error: {e}",
                        captured_at=datetime.now(timezone.utc).isoformat(),
                        capture_source=cfg.capture_source,
                        llm_provider="none", llm_model="none",
                    )
                    self._cache.store(regime, capture_path="")
                    return regime
                else:
                    await asyncio.sleep(base_delay * attempt)

        # Step 3: Store
        self._cache.store(regime, capture_path=cap.saved_path)
        return regime

    # ── Continuous loop ─────────────────────────────────────────────

    async def run_forever(self) -> None:
        """Run VMO cycles on the configured interval until stopped.

        Post-cycle hooks:
          1. Prune old PNG captures (configurable retention)
          2. Marginal kline collection (uses leftover Binance weight)
          3. Register any unhandled errors in ExceptionZoo
        """
        self._running = True
        zoo = get_exception_zoo()
        _LOG.info(
            "VMO observer starting (interval=%dm, symbols=%d, timeframes=%d)",
            self.config.interval_minutes,
            len(self.config.symbols),
            len(self.config.timeframes),
        )

        while self._running:
            try:
                await self.run_cycle()
            except Exception as exc:
                zoo.register(exc, module="vmo.observer", context="run_cycle_unhandled")
                _LOG.exception("VMO cycle failed unexpectedly")

            # Post-cycle: marginal kline collection
            try:
                from runtime.core.kline_collector import get_kline_collector
                collector = get_kline_collector()
                if collector._client is not None:
                    result = await collector.collect_marginal(budget=30)
                    if result.get("total_candles", 0) > 0:
                        _LOG.info(
                            "Post-cycle kline collection: %d candles (%d weight)",
                            result["total_candles"], result["total_weight"],
                        )
            except Exception as exc:
                zoo.register(exc, module="vmo.observer", context="post_cycle_klines")

            # Post-cycle: telemetry purge (once per day, check by cycle count)
            if self._total_cycles % 24 == 0 and self._total_cycles > 0:
                try:
                    vault = get_telemetry_vault()
                    purged = vault.purge_old_data(
                        kline_days=365, decision_days=90, capture_days=30,
                    )
                    _LOG.info("Telemetry purge: %s", purged)
                except Exception as exc:
                    zoo.register(exc, module="vmo.observer", context="post_cycle_purge")

            # Wait for next cycle
            wait_sec = self.config.interval_minutes * 60
            _LOG.info("Next VMO cycle in %d minutes", self.config.interval_minutes)
            try:
                await asyncio.sleep(wait_sec)
            except asyncio.CancelledError:
                break

        _LOG.info("VMO observer stopped")

    def stop(self) -> None:
        """Signal the observer to stop after the current cycle."""
        self._running = False

    # ── Status ──────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return current VMO status for API/UI consumption."""
        cache_summary = self._cache.summary()
        return {
            "enabled": self.config.enabled,
            "running": self._running,
            "total_cycles": self._total_cycles,
            "last_cycle_at": self._last_cycle_at,
            "last_cycle_count": len(self._last_cycle_results),
            "config": self.config.summary(),
            "cache": cache_summary,
        }

    def get_latest_regimes(self) -> dict[str, dict[str, dict]]:
        """Get the latest regime per symbol/timeframe as dicts."""
        raw = self._cache.get_latest_per_symbol()
        return {
            sym: {tf: r.to_dict() for tf, r in tfs.items()}
            for sym, tfs in raw.items()
        }

    def get_regime_history(
        self, symbol: str = "", timeframe: str = "", limit: int = 50
    ) -> list[dict]:
        """Get regime history as dicts."""
        regimes = self._cache.get_latest(symbol, timeframe, limit)
        return [r.to_dict() for r in regimes]


# ── CLI entrypoint ──────────────────────────────────────────────────

async def _cli_main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="VMO Observer")
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single cycle and exit",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print current status and exit",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    observer = VMObserver()

    if args.status:
        import json
        print(json.dumps(observer.status(), indent=2, default=str))
        return

    if args.once:
        results = await observer.run_cycle()
        print(f"\nCycle complete: {len(results)} classifications")
        for r in results:
            emoji = {"TRENDING": "📈", "RANGING": "📊", "CHOPPY": "🌀", "BREAKOUT": "🚀"}.get(r.regime, "❓")
            bot_emoji = {"dorothy": "🟢", "masha": "🔵", "thusnelda": "🟡", "none": "⚪"}.get(r.recommended_bot, "❓")
            print(
                f"  {emoji} {r.symbol:>10}/{r.timeframe:<3} "
                f"→ {r.regime:<10} ({r.confidence:.0%}) "
                f"{bot_emoji} {r.recommended_bot}"
            )
    else:
        await observer.run_forever()


if __name__ == "__main__":
    asyncio.run(_cli_main())
