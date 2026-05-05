"""Chart capture engine — dual source: chart-img.com API + Playwright fallback.

This module is responsible for obtaining PNG screenshots of TradingView charts.
It has no knowledge of analysis or regime classification — pure capture.

Usage:
    from runtime.modules.vision.chart_capture import capture_chart
    result = await capture_chart("BTCUSDT", "4h")
    if result.ok:
        with open("chart.png", "wb") as f:
            f.write(result.png)

CLI:
    python -m runtime.modules.vision.chart_capture --symbol BTCUSDT --interval 4h
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_LOG = logging.getLogger("pecunator.vmo.capture")


# ── Result dataclass ────────────────────────────────────────────────

@dataclass
class CaptureResult:
    """Outcome of a chart capture attempt."""
    ok: bool
    png: bytes = b""
    source: str = "none"          # "chart-img" | "playwright" | "none"
    symbol: str = ""
    interval: str = ""
    elapsed_ms: int = 0
    error: Optional[str] = None
    captured_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    saved_path: Optional[str] = None


# ── chart-img.com API ───────────────────────────────────────────────

async def _capture_chart_img(
    symbol: str,
    interval: str,
    api_key: str,
    base_url: str = "https://api.chart-img.com/v2/tradingview/advanced-chart",
    width: int = 800,
    height: int = 600,
) -> bytes:
    """Capture a chart via the chart-img.com REST API.

    Returns PNG bytes on success. Raises on failure.
    """
    try:
        import httpx
    except ImportError as e:
        raise RuntimeError(
            "httpx is required for chart-img captures: pip install httpx"
        ) from e

    if not api_key:
        raise ValueError("CHART_IMG_API_KEY is not set")

    # Map interval to chart-img format
    interval_map = {
        "1m": "1", "5m": "5", "15m": "15", "30m": "30",
        "1h": "1h", "2h": "2h", "4h": "4h",
        "1d": "1D", "1w": "1W", "1M": "1M",
    }
    tv_interval = interval_map.get(interval, interval)

    params = {
        "symbol": f"BINANCE:{symbol}",
        "interval": tv_interval,
        "theme": "dark",
        "width": width,
        "height": height,
    }
    headers = {"x-api-key": api_key}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(base_url, params=params, headers=headers)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and len(resp.content) < 1000:
            raise ValueError(
                f"chart-img returned non-image response: "
                f"{content_type} ({len(resp.content)} bytes)"
            )
        return resp.content


# ── Playwright fallback ─────────────────────────────────────────────

async def _capture_playwright(
    symbol: str,
    interval: str,
    width: int = 1280,
    height: int = 720,
) -> bytes:
    """Capture a chart via headless Playwright (Chromium).

    Returns PNG bytes on success. Raises on failure.
    Requires: pip install playwright && playwright install chromium
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise RuntimeError(
            "playwright is required for headless capture: "
            "pip install playwright && playwright install chromium"
        ) from e

    # Map interval to TradingView URL parameter (in minutes for most)
    interval_map = {
        "1m": "1", "5m": "5", "15m": "15", "30m": "30",
        "1h": "60", "2h": "120", "4h": "240",
        "1d": "D", "1w": "W", "1M": "M",
    }
    tv_interval = interval_map.get(interval, interval)

    url = (
        f"https://www.tradingview.com/chart/"
        f"?symbol=BINANCE%3A{symbol}&interval={tv_interval}"
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        try:
            page = await browser.new_page(
                viewport={"width": width, "height": height},
            )
            _LOG.debug("Navigating to %s", url)
            await page.goto(url, wait_until="networkidle", timeout=45000)

            # Wait for chart canvas to render
            try:
                await page.wait_for_selector(
                    "canvas", state="attached", timeout=20000
                )
            except Exception:
                _LOG.warning("Canvas not found, taking full-page screenshot")

            # Extra wait for indicators/data to finish painting
            await asyncio.sleep(3)

            # Dismiss any overlays (cookies, popups)
            for selector in [
                "button:has-text('Accept')",
                "button:has-text('OK')",
                "button:has-text('Got it')",
                "[class*='close']",
            ]:
                try:
                    btn = await page.query_selector(selector)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(0.5)
                except Exception:
                    pass

            png = await page.screenshot(type="png")
            return png
        finally:
            await browser.close()


# ── Unified capture with failover ───────────────────────────────────

async def capture_chart(
    symbol: str,
    interval: str,
    *,
    source: str = "auto",
    api_key: str = "",
    base_url: str = "",
    save_dir: Optional[Path] = None,
) -> CaptureResult:
    """Capture a TradingView chart with automatic failover.

    Args:
        symbol: e.g. "BTCUSDT"
        interval: e.g. "4h", "1d"
        source: "chart-img", "playwright", or "auto" (try chart-img first)
        api_key: chart-img API key
        base_url: chart-img API base URL override
        save_dir: directory to save PNG (optional)

    Returns:
        CaptureResult with png bytes and metadata.
    """
    t0 = time.monotonic()

    # Resolve config defaults if not provided
    if not api_key or not base_url:
        from runtime.modules.vision.config import get_vmo_config
        cfg = get_vmo_config()
        api_key = api_key or cfg.chart_img_api_key
        base_url = base_url or cfg.chart_img_base_url
        if save_dir is None:
            save_dir = cfg.captures_dir

    # ── Try chart-img first ─────────────────────────────────────
    if source in ("chart-img", "auto") and api_key:
        try:
            png = await _capture_chart_img(
                symbol, interval, api_key, base_url=base_url
            )
            elapsed = int((time.monotonic() - t0) * 1000)
            result = CaptureResult(
                ok=True, png=png, source="chart-img",
                symbol=symbol, interval=interval, elapsed_ms=elapsed,
            )
            if save_dir:
                result.saved_path = _save_png(result, save_dir)
            _LOG.info(
                "Captured %s/%s via chart-img (%d bytes, %dms)",
                symbol, interval, len(png), elapsed,
            )
            return result
        except Exception as e:
            _LOG.warning(
                "chart-img failed for %s/%s: %s", symbol, interval, e
            )
            if source == "chart-img":
                # Explicit source, don't fallback
                elapsed = int((time.monotonic() - t0) * 1000)
                return CaptureResult(
                    ok=False, source="chart-img",
                    symbol=symbol, interval=interval,
                    elapsed_ms=elapsed, error=str(e),
                )

    # ── Try Playwright fallback ─────────────────────────────────
    if source in ("playwright", "auto"):
        try:
            png = await _capture_playwright(symbol, interval)
            elapsed = int((time.monotonic() - t0) * 1000)
            result = CaptureResult(
                ok=True, png=png, source="playwright",
                symbol=symbol, interval=interval, elapsed_ms=elapsed,
            )
            if save_dir:
                result.saved_path = _save_png(result, save_dir)
            _LOG.info(
                "Captured %s/%s via Playwright (%d bytes, %dms)",
                symbol, interval, len(png), elapsed,
            )
            return result
        except Exception as e:
            _LOG.error(
                "Playwright failed for %s/%s: %s", symbol, interval, e
            )
            elapsed = int((time.monotonic() - t0) * 1000)
            return CaptureResult(
                ok=False, source="playwright",
                symbol=symbol, interval=interval,
                elapsed_ms=elapsed, error=str(e),
            )

    # ── No source available ─────────────────────────────────────
    elapsed = int((time.monotonic() - t0) * 1000)
    return CaptureResult(
        ok=False, source="none",
        symbol=symbol, interval=interval,
        elapsed_ms=elapsed,
        error="No capture source available (set CHART_IMG_API_KEY or install playwright)",
    )


# ── PNG storage ─────────────────────────────────────────────────────

def _save_png(result: CaptureResult, save_dir: Path) -> str:
    """Save PNG to disk with structured filename."""
    save_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{result.symbol}_{result.interval}_{ts}.png"
    path = save_dir / filename
    path.write_bytes(result.png)
    return str(path)


def prune_old_captures(save_dir: Path, retention_hours: int = 48) -> int:
    """Delete PNGs older than retention_hours. Returns count deleted."""
    if not save_dir.exists():
        return 0
    cutoff = time.time() - (retention_hours * 3600)
    deleted = 0
    for f in save_dir.glob("*.png"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError:
            pass
    if deleted:
        _LOG.info("Pruned %d old captures from %s", deleted, save_dir)
    return deleted


# ── CLI entrypoint ──────────────────────────────────────────────────

async def _cli_main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="VMO Chart Capture")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol to capture")
    parser.add_argument("--interval", default="4h", help="Timeframe (1h, 4h, 1d)")
    parser.add_argument("--source", default="auto", help="chart-img | playwright | auto")
    parser.add_argument("--out", default="", help="Output directory for PNG")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    save_dir = Path(args.out) if args.out else None
    result = await capture_chart(
        args.symbol, args.interval,
        source=args.source, save_dir=save_dir,
    )

    if result.ok:
        print(f"✅ Captured {result.symbol}/{result.interval}")
        print(f"   Source:  {result.source}")
        print(f"   Size:   {len(result.png):,} bytes")
        print(f"   Time:   {result.elapsed_ms}ms")
        if result.saved_path:
            print(f"   Saved:  {result.saved_path}")
        else:
            # Save to current dir if no save_dir was specified
            out = Path(f"{result.symbol}_{result.interval}.png")
            out.write_bytes(result.png)
            print(f"   Saved:  {out}")
    else:
        print(f"❌ Failed: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(_cli_main())
