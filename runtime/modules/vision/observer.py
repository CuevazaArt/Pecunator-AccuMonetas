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
from pathlib import Path
from typing import Any, Optional

from runtime.modules.vision.chart_capture import (
    CaptureResult,
    capture_chart,
    prune_old_captures,
)
from runtime.modules.vision.chart_analyzer import MarketRegime, classify_chart
from runtime.modules.vision.config import get_vmo_config, VMOConfig
from runtime.modules.vision.regime_cache import RegimeCache

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
        total = cfg.total_captures_per_cycle
        _LOG.info(
            "Starting VMO cycle: %d symbols × %d timeframes = %d captures",
            len(cfg.symbols), len(cfg.timeframes), total,
        )

        t0 = time.monotonic()
        completed = 0
        failed = 0

        for symbol in cfg.symbols:
            for timeframe in cfg.timeframes:
                try:
                    regime = await self._capture_and_classify(
                        symbol, timeframe
                    )
                    results.append(regime)
                    completed += 1
                except Exception as e:
                    _LOG.error(
                        "VMO cycle error for %s/%s: %s",
                        symbol, timeframe, e,
                    )
                    failed += 1

                # Respect rate limits between captures
                if cfg.capture_delay_sec > 0:
                    await asyncio.sleep(cfg.capture_delay_sec)

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

        # Step 1: Capture
        cap = await capture_chart(
            symbol, timeframe,
            source=cfg.capture_source,
            api_key=cfg.chart_img_api_key,
            base_url=cfg.chart_img_base_url,
            save_dir=cfg.captures_dir,
        )

        if not cap.ok:
            _LOG.warning(
                "Capture failed for %s/%s: %s", symbol, timeframe, cap.error
            )
            # Return a "no data" regime
            regime = MarketRegime(
                symbol=symbol, timeframe=timeframe,
                trend="LATERAL", trend_strength="WEAK",
                volatility="NORMAL", regime="RANGING",
                confidence=0.0, recommended_bot="none",
                risk_level="HIGH",
                notes=f"Capture failed: {cap.error}",
                captured_at=cap.captured_at,
                capture_source=cap.source,
                llm_provider="none", llm_model="none",
            )
            self._cache.store(regime, capture_path=cap.saved_path)
            return regime

        # Step 2: Classify
        regime = await classify_chart(
            cap.png, symbol, timeframe,
            provider=cfg.llm_provider,
            model=cfg.llm_model,
            gemini_api_key=cfg.gemini_api_key,
            openai_api_key=cfg.openai_api_key,
            captured_at=cap.captured_at,
            capture_source=cap.source,
        )

        # Step 3: Store
        self._cache.store(regime, capture_path=cap.saved_path)
        return regime

    # ── Continuous loop ─────────────────────────────────────────────

    async def run_forever(self) -> None:
        """Run VMO cycles on the configured interval until stopped."""
        self._running = True
        _LOG.info(
            "VMO observer starting (interval=%dm, symbols=%d, timeframes=%d)",
            self.config.interval_minutes,
            len(self.config.symbols),
            len(self.config.timeframes),
        )

        while self._running:
            try:
                await self.run_cycle()
            except Exception:
                _LOG.exception("VMO cycle failed unexpectedly")

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
