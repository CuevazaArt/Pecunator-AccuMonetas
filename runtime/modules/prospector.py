"""DorothyProspector — Symbol scanner for the Dorothy ⇄ Elphaba hub.

Scans all Binance USDT pairs, computes an Oscillation Score for each,
and ranks them by suitability for the symmetric DCA strategy.

The ideal symbol for Dorothy+Elphaba:
  - High ATR% (large relative swings → profit opportunities)
  - Low ADX (choppy/ranging → frequent reversals = more DCA entries)
  - Adequate volume (liquidity for clean fills)
  - Isolated Margin support (required for Elphaba shorts)
  - MIN_NOTIONAL ≤ 6 USDT (fits our quoteOrderQty)

Oscillation Score = ATR_pct × (100 − ADX) / 100
Higher score = more "electric" = better for DCA hub.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.modules.prospector")


# ── Data models ────────────────────────────────────────────────────

@dataclass
class SymbolProfile:
    """Analysis result for a single symbol."""
    symbol: str = ""
    # Filters
    margin_eligible: bool = False
    volume_24h_usdt: float = 0.0
    min_notional: float = 5.0
    # Scores
    atr_pct: float = 0.0          # ATR / price × 100
    adx: float = 0.0              # Average Directional Index (0-100)
    choppiness: float = 0.0       # Choppiness Index (0-100)
    oscillation_score: float = 0.0  # Composite: ATR% × (100-ADX)/100
    # Metadata
    current_price: float = 0.0
    avg_spread_pct: float = 0.0
    kline_count: int = 0
    error: str = ""

    def as_json(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "oscillation_score": round(self.oscillation_score, 4),
            "atr_pct": round(self.atr_pct, 4),
            "adx": round(self.adx, 2),
            "choppiness": round(self.choppiness, 2),
            "volume_24h_usdt": round(self.volume_24h_usdt, 2),
            "margin_eligible": self.margin_eligible,
            "current_price": self.current_price,
            "min_notional": self.min_notional,
            "grade": self.grade,
        }

    @property
    def grade(self) -> str:
        """Human-readable grade based on oscillation score."""
        s = self.oscillation_score
        if s >= 3.0:
            return "S"   # Exceptional
        elif s >= 2.0:
            return "A"   # Excellent
        elif s >= 1.5:
            return "B"   # Good
        elif s >= 1.0:
            return "C"   # Acceptable
        elif s >= 0.5:
            return "D"   # Marginal
        return "F"       # Unsuitable


# ── Math ───────────────────────────────────────────────────────────

def _compute_atr(highs: list[float], lows: list[float], closes: list[float],
                 period: int = 14) -> float:
    """Average True Range over `period` candles."""
    if len(highs) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return sum(trs[-period:]) / period if trs else 0.0


def _compute_adx(highs: list[float], lows: list[float], closes: list[float],
                 period: int = 14) -> float:
    """Simplified ADX (Average Directional Index)."""
    n = len(highs)
    if n < period + 2:
        return 50.0  # Neutral default

    plus_dm_list = []
    minus_dm_list = []
    tr_list = []

    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm = max(up, 0) if up > down else 0.0
        minus_dm = max(down, 0) if down > up else 0.0
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)

        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)

    # Simple moving averages for the last `period` values
    if len(tr_list) < period:
        return 50.0

    atr = sum(tr_list[-period:]) / period
    if atr == 0:
        return 50.0

    plus_di = (sum(plus_dm_list[-period:]) / period / atr) * 100
    minus_di = (sum(minus_dm_list[-period:]) / period / atr) * 100

    di_sum = plus_di + minus_di
    if di_sum == 0:
        return 0.0

    dx = abs(plus_di - minus_di) / di_sum * 100
    return dx


def _compute_choppiness(highs: list[float], lows: list[float], closes: list[float],
                        period: int = 14) -> float:
    """Choppiness Index: 0-100, higher = more choppy (range-bound)."""
    import math
    n = len(highs)
    if n < period + 1:
        return 50.0

    # ATR sum over period
    atr_sum = 0.0
    for i in range(n - period, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]) if i > 0 else highs[i] - lows[i],
            abs(lows[i] - closes[i - 1]) if i > 0 else highs[i] - lows[i],
        )
        atr_sum += tr

    # Highest high and lowest low in period
    hh = max(highs[n - period:n])
    ll = min(lows[n - period:n])
    hl_range = hh - ll

    if hl_range <= 0 or atr_sum <= 0:
        return 50.0

    chop = 100.0 * math.log10(atr_sum / hl_range) / math.log10(period)
    return max(0.0, min(100.0, chop))


def compute_oscillation_score(
    klines: list[list],
    period: int = 14,
) -> dict[str, float]:
    """Compute the full oscillation profile from raw Binance klines.

    Args:
        klines: Raw Binance klines [[open_time, O, H, L, C, vol, ...], ...]
        period: Lookback period for ATR/ADX/CHOP (default 14)

    Returns:
        Dict with atr_pct, adx, choppiness, oscillation_score
    """
    if len(klines) < period + 2:
        return {"atr_pct": 0, "adx": 50, "choppiness": 50, "oscillation_score": 0}

    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    closes = [float(k[4]) for k in klines]

    current_price = closes[-1] if closes else 1.0
    if current_price <= 0:
        current_price = 1.0

    atr = _compute_atr(highs, lows, closes, period)
    atr_pct = (atr / current_price) * 100

    adx = _compute_adx(highs, lows, closes, period)
    chop = _compute_choppiness(highs, lows, closes, period)

    # Composite: high ATR% + low directional = high oscillation
    oscillation_score = atr_pct * (100 - adx) / 100

    return {
        "atr_pct": atr_pct,
        "adx": adx,
        "choppiness": chop,
        "oscillation_score": oscillation_score,
        "current_price": current_price,
    }


# ── Prospector ─────────────────────────────────────────────────────

class DorothyProspector:
    """Scans Binance symbols and ranks them for the Dorothy hub."""

    # Minimum 24h volume in USDT to consider (filters dust pairs)
    MIN_VOLUME_USDT = 500_000.0
    # Maximum MIN_NOTIONAL to allow (must fit our 6 USDT quoteOrderQty)
    MAX_MIN_NOTIONAL = 6.0
    # Number of 1h klines to fetch for analysis
    KLINE_LIMIT = 100  # ~4 days of 1h candles
    # Rate-limit: sequential batches to respect Binance frequency limits
    BATCH_SIZE = 3          # kline requests per batch
    BATCH_DELAY_SEC = 0.6   # delay between batches (avoids frequency limit)
    # Max symbols to analyze (after volume filter)
    ANALYSIS_POOL_SIZE = 30

    def __init__(self) -> None:
        self._last_scan: Optional[list[SymbolProfile]] = None
        self._last_scan_ts: float = 0.0

    async def scan(
        self,
        client: Any,
        *,
        top_n: int = 20,
        min_volume: float | None = None,
        _to_thread: Any = None,
    ) -> list[SymbolProfile]:
        """Run full prospecting scan.

        Steps:
          1. Fetch all USDT pairs with 24h ticker data
          2. Filter by volume, notional, margin eligibility
          3. Fetch 1h klines for top candidates by volume (rate-limited)
          4. Compute oscillation scores
          5. Rank and return top N

        Rate budget: ~45 API weight total (well under 6000/min limit).
        Frequency: batches of 3 with 600ms pauses → ~6s for 30 symbols.

        Args:
            client: Authenticated Binance client
            top_n: Number of top results to return
            min_volume: Override minimum 24h volume filter
        """
        async def _run(fn: Any) -> Any:
            if _to_thread:
                return await _to_thread(fn)
            return await asyncio.get_event_loop().run_in_executor(None, fn)

        min_vol = min_volume or self.MIN_VOLUME_USDT

        # ── Step 1: Get all tickers + exchange info ───────────────
        # Weight: get_ticker=2, exchangeInfo=10, margin_symbols=10 = 22
        _LOG.info("Prospector: fetching tickers and exchange info...")
        tickers = await _run(lambda: client.get_ticker())
        await asyncio.sleep(0.3)  # Frequency spacing
        exchange_info = await _run(lambda: client.get_exchange_info())
        await asyncio.sleep(0.3)

        # Build filter lookup: symbol → {min_notional, status}
        sym_filters: dict[str, dict[str, Any]] = {}
        for s in exchange_info.get("symbols", []):
            sym = s.get("symbol", "")
            if not sym.endswith("USDT") or s.get("status") != "TRADING":
                continue
            min_not = 5.0
            for f in s.get("filters", []):
                if f.get("filterType") == "NOTIONAL":
                    min_not = float(f.get("minNotional", "5"))
                elif f.get("filterType") == "MIN_NOTIONAL":
                    min_not = float(f.get("minNotional", "5"))
            sym_filters[sym] = {"min_notional": min_not}

        # ── Step 2: Get margin-eligible symbols ───────────────────
        # Weight: ~10
        margin_symbols: set[str] = set()
        try:
            iso_pairs = await _run(lambda: client.get_all_isolated_margin_symbols())
            for p in (iso_pairs if isinstance(iso_pairs, list) else []):
                if p.get("isMarginTrade") and p.get("quote") == "USDT":
                    margin_symbols.add(p.get("symbol", ""))
        except Exception as e:
            _LOG.warning("Prospector: margin symbols fetch failed: %s", e)

        await asyncio.sleep(0.3)

        # ── Step 3: Filter candidates ─────────────────────────────
        candidates: list[SymbolProfile] = []
        for t in (tickers if isinstance(tickers, list) else []):
            sym = str(t.get("symbol", ""))
            if not sym.endswith("USDT"):
                continue
            if sym not in sym_filters:
                continue

            vol = float(t.get("quoteVolume", "0"))
            if vol < min_vol:
                continue

            flt = sym_filters[sym]
            if flt["min_notional"] > self.MAX_MIN_NOTIONAL:
                continue

            p = SymbolProfile(
                symbol=sym,
                volume_24h_usdt=vol,
                min_notional=flt["min_notional"],
                margin_eligible=sym in margin_symbols,
                current_price=float(t.get("lastPrice", "0")),
            )
            candidates.append(p)

        # Sort by volume (analyze highest-volume first)
        candidates.sort(key=lambda p: p.volume_24h_usdt, reverse=True)

        # Limit analysis pool (API budget control)
        analyze_pool = candidates[:self.ANALYSIS_POOL_SIZE]

        _LOG.info(
            "Prospector: %d USDT pairs found, %d pass filters, analyzing top %d",
            len([t for t in tickers if str(t.get("symbol", "")).endswith("USDT")]),
            len(candidates),
            len(analyze_pool),
        )

        # ── Step 4: Fetch klines in rate-limited batches ──────────
        # Each get_klines = weight 1. 30 symbols = 30 weight.
        # Batched in groups of BATCH_SIZE with BATCH_DELAY_SEC pause.

        async def _analyze_one(profile: SymbolProfile) -> None:
            try:
                klines = await _run(
                    lambda _s=profile.symbol: client.get_klines(
                        symbol=_s, interval="1h", limit=self.KLINE_LIMIT
                    )
                )
                if not klines or len(klines) < 20:
                    profile.error = "insufficient_klines"
                    return

                profile.kline_count = len(klines)
                scores = compute_oscillation_score(klines)
                profile.atr_pct = scores["atr_pct"]
                profile.adx = scores["adx"]
                profile.choppiness = scores["choppiness"]
                profile.oscillation_score = scores["oscillation_score"]
                profile.current_price = scores["current_price"]

            except Exception as e:
                profile.error = str(e)[:100]

        # Sequential batched processing
        for batch_start in range(0, len(analyze_pool), self.BATCH_SIZE):
            batch = analyze_pool[batch_start:batch_start + self.BATCH_SIZE]
            # Run batch concurrently (small batch = safe)
            await asyncio.gather(*[_analyze_one(p) for p in batch])
            # Throttle between batches
            if batch_start + self.BATCH_SIZE < len(analyze_pool):
                await asyncio.sleep(self.BATCH_DELAY_SEC)

        # ── Step 5: Rank by oscillation score ─────────────────────
        scored = [p for p in analyze_pool if p.oscillation_score > 0]
        scored.sort(key=lambda p: p.oscillation_score, reverse=True)

        result = scored[:top_n]
        self._last_scan = result
        self._last_scan_ts = time.time()

        _LOG.info(
            "Prospector: scan complete. Top symbol: %s (score=%.4f, grade=%s)",
            result[0].symbol if result else "NONE",
            result[0].oscillation_score if result else 0,
            result[0].grade if result else "F",
        )

        return result

    def get_last_scan(self) -> Optional[list[SymbolProfile]]:
        return self._last_scan

    def get_recommendation(self) -> Optional[SymbolProfile]:
        """Get the #1 recommended symbol from the last scan.

        Prioritizes margin-eligible symbols. If the top oscillation
        score symbol isn't margin-eligible, finds the best that is.
        """
        if not self._last_scan:
            return None

        # First choice: best margin-eligible symbol
        for p in self._last_scan:
            if p.margin_eligible:
                return p

        # Fallback: best overall (Dorothy-only, no Elphaba)
        return self._last_scan[0] if self._last_scan else None

    def format_report(self, results: list[SymbolProfile] | None = None) -> str:
        """Format scan results as a readable table."""
        data = results or self._last_scan
        if not data:
            return "No scan results available. Run scan() first."

        lines = [
            "╔══════════════════════════════════════════════════════════════════════╗",
            "║             DOROTHY PROSPECTOR — Symbol Ranking                     ║",
            "╠══════════════════════════════════════════════════════════════════════╣",
            "║ #  │ Symbol      │ Score │ ATR%  │ ADX  │ CHOP │ Vol(M$) │ Margin  ║",
            "╠════╪═════════════╪═══════╪═══════╪══════╪══════╪═════════╪═════════╣",
        ]
        for i, p in enumerate(data, 1):
            margin_str = "  ✅  " if p.margin_eligible else "  ❌  "
            grade_str = f"[{p.grade}]"
            lines.append(
                f"║ {i:>2} │ {p.symbol:<11} │ {p.oscillation_score:>5.2f} │ "
                f"{p.atr_pct:>5.2f} │ {p.adx:>4.1f} │ {p.choppiness:>4.1f} │ "
                f"{p.volume_24h_usdt / 1e6:>6.1f} │{margin_str}║"
            )
        lines.append(
            "╚══════════════════════════════════════════════════════════════════════╝"
        )

        # Recommendation
        rec = self.get_recommendation()
        if rec:
            lines.append("")
            lines.append(f"🎯 RECOMENDACIÓN: {rec.symbol} (Grade {rec.grade})")
            lines.append(f"   Score={rec.oscillation_score:.4f}  ATR%={rec.atr_pct:.2f}  "
                         f"ADX={rec.adx:.1f}  CHOP={rec.choppiness:.1f}")
            lines.append(f"   Volume=${rec.volume_24h_usdt / 1e6:.1f}M  "
                         f"Margin={'SÍ' if rec.margin_eligible else 'NO'}")

        return "\n".join(lines)


# ── Singleton ──────────────────────────────────────────────────────

_instance: Optional[DorothyProspector] = None


def get_prospector() -> DorothyProspector:
    global _instance
    if _instance is None:
        _instance = DorothyProspector()
    return _instance
