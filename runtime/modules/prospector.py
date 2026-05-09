"""DorothyProspector — Symbol scanner for the Dorothy ⇄ Elphaba hub.

Scans all Binance USDT pairs, computes an Electric Volatility Index (EVI)
for each and ranks them by suitability for the symmetric DCA strategy.

The ideal symbol for Dorothy+Elphaba:
  - High ATR% (NATR: large relative swings → profit opportunities)
  - High speed (mean |1-candle return|: fast traversal of range)
  - High frequency of extreme events (spikes > 1.5σ → more DCA entries)
  - Low ADX / high Choppiness (range-bound → frequent reversals)
  - Adequate volume (liquidity for clean fills)
  - Isolated Margin support (required for Elphaba shorts)
  - MIN_NOTIONAL ≤ 6 USDT (fits our quoteOrderQty)

EVI = NATR × AvgSpeed × FreqExtreme × (Choppiness/50)
Higher EVI = more "electric" = better for DCA hub.
"""

from __future__ import annotations

import asyncio
import logging
import time
import math
import statistics
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
    # Scores (legacy)
    atr_pct: float = 0.0          # ATR / price × 100 (NATR)
    adx: float = 0.0              # Average Directional Index (0-100)
    choppiness: float = 0.0       # Choppiness Index (0-100)
    oscillation_score: float = 0.0  # Legacy: ATR% × (100-ADX)/100
    # EVI components
    avg_speed: float = 0.0        # Mean |1-candle return| (speed dimension)
    freq_extreme: float = 0.0     # Fraction of candles with |ret| > 1.5σ
    kurtosis: float = 0.0         # Excess kurtosis of returns (tail thickness)
    evi_score: float = 0.0        # EVI = NATR × AvgSpeed × FreqExtreme × (CHOP/50)
    sei_score: float = 0.0        # SEI = EVI_v2 * safety_multiplier
    safety_multiplier: float = 1.0
    # Metadata
    current_price: float = 0.0
    avg_spread_pct: float = 0.0
    kline_count: int = 0
    error: str = ""

    def as_json(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "evi_score": round(self.evi_score, 4),
            "sei_score": round(self.sei_score, 4),
            "safety_multiplier": round(self.safety_multiplier, 4),
            "oscillation_score": round(self.oscillation_score, 4),
            "atr_pct": round(self.atr_pct, 4),
            "avg_speed": round(self.avg_speed, 4),
            "freq_extreme": round(self.freq_extreme, 4),
            "kurtosis": round(self.kurtosis, 2),
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
        """Human-readable grade based on SEI score."""
        s = self.sei_score
        if s >= 0.50:
            return "S"   # Exceptional electric
        elif s >= 0.20:
            return "A"   # Excellent
        elif s >= 0.10:
            return "B"   # Good
        elif s >= 0.05:
            return "C"   # Acceptable
        elif s >= 0.02:
            return "D"   # Marginal
        return "F"       # Dead market


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


import traceback  # added for detailed error logging

def _compute_speed_and_frequency(
    closes: list[float],
    sigma_threshold: float = 0.8,
) -> tuple[float, float, float, float]:
    """Compute oscillatory speed, extreme frequency, kurtosis, and skew.

    Args:
        closes: Close prices series
        sigma_threshold: Multiplier of σ to define 'extreme' (default 1.5)

    Returns:
        (oscillatory_speed_pct, freq_extreme, excess_kurtosis, skewness)
    """
    if len(closes) < 5:
        return 0.0, 0.0, 0.0, 0.0

    # Compute 1-candle percentage returns
    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            returns.append((closes[i] - closes[i - 1]) / closes[i - 1] * 100)

    if len(returns) < 4:
        return 0.0, 0.0, 0.0, 0.0

    abs_returns = [abs(r) for r in returns]
    mean_abs_ret = sum(abs_returns) / len(abs_returns)
    mean_ret = sum(returns) / len(returns)
    
    # Oscillatory Speed: mean(abs(ret)) - abs(mean(ret))
    avg_speed = mean_abs_ret - abs(mean_ret)

    # Frequency of significant moves: candles where |return| > median |return|
    # This captures clustering: fat-tailed distributions have more extreme moves
    # above the median than normal distributions (50% for uniform, higher for
    # leptokurtic). For perfectly regular oscillations freq ≈ 0.5 (healthy).
    sorted_abs = sorted(abs_returns)
    median_abs = sorted_abs[len(sorted_abs) // 2]
    if median_abs > 0:
        # Count candles with |return| > 1.5 × median
        threshold = sigma_threshold * median_abs
        extreme_count = sum(1 for r in abs_returns if r > threshold)
        freq_extreme = extreme_count / len(abs_returns)
    else:
        freq_extreme = 0.0

    # Excess kurtosis and Skewness
    var = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    if var > 0:
        m4 = sum((r - mean_ret) ** 4 for r in returns) / len(returns)
        kurtosis = (m4 / (var ** 2)) - 3.0  # excess kurtosis
        
        stdev = math.sqrt(var)
        skew = sum(((r - mean_ret) / stdev) ** 3 for r in returns) / len(returns)
    else:
        kurtosis = 0.0
        skew = 0.0

    return avg_speed, freq_extreme, kurtosis, skew


def check_hard_vetos(
    klines: list[list],
    volume_24h_usdt: float = 0.0,
    spread_pct: float = 0.0,
) -> tuple[bool, str]:
    """SEVI-M Hard Vetos — binary pre-filter.

    Returns:
        (is_vetoed, reason) — if is_vetoed=True, skip all calculations.
    All data comes from klines + ticker already fetched — 0 extra API calls.
    """
    if len(klines) < 20:
        return True, "insufficient_data"

    closes = [float(k[4]) for k in klines]
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    current_price = closes[-1] if closes[-1] > 0 else 1.0

    # VETO 1: Dead market (NATR < 0.5%)
    atr = _compute_atr(highs, lows, closes, period=14)
    natr = atr / current_price
    if natr < 0.005:
        return True, f"NATR={natr:.4f} < 0.5% — dead market"

    # VETO 2: Structural collapse (MA200 slope < -5%)
    if len(closes) >= 200:
        ma200 = [sum(closes[i-200:i]) / 200 for i in range(200, len(closes)+1)]
        if len(ma200) >= 20 and ma200[-20] > 0:
            slope = (ma200[-1] - ma200[-20]) / ma200[-20]
            if slope < -0.05:
                return True, f"MA200 slope={slope:.2%} — structural collapse"

    # VETO 3: Ghost volume (< 500K USDT)
    if volume_24h_usdt < 500_000:
        return True, f"Vol=${volume_24h_usdt:,.0f} < 500K — ghost"

    # VETO 4: Lethal spread (> 2% of price)
    if spread_pct > 0.02:
        return True, f"Spread={spread_pct:.3%} — lethal"

    return False, ""


def _compute_liquidity_penalty(volume_24h_usdt: float) -> float:
    """Liquidity penalty based on 24h volume tiers.

    Higher volume = better fill quality in spot.
    Range: 0.5 (min viable) to 1.0 (excellent).
    Below 500K is already vetoed.
    """
    if volume_24h_usdt > 10_000_000:
        return 1.0
    elif volume_24h_usdt > 5_000_000:
        return 0.9
    elif volume_24h_usdt > 2_000_000:
        return 0.8
    elif volume_24h_usdt > 1_000_000:
        return 0.7
    else:
        return 0.5


def compute_oscillation_score(
    klines: list[list],
    period: int = 14,
    volume_24h_usdt: float = 0.0,
    spread_pct: float = 0.0,
) -> dict[str, float]:
    """Compute the full SEVI-M profile from raw Binance klines.

    SEVI-M (Safe Electric Volatility Index — Minimalista Definitivo):
      EVI = adjusted_atr × oscillatory_speed × freq_extreme × (chop/50)
      safety = macro_penalty × liquidity_penalty
      SEVI = EVI × safety

    6 factors total. 0 external dependencies. 100% deterministic.

    Args:
        klines: Raw Binance klines [[open_time, O, H, L, C, vol, ...], ...]
        period: Lookback period for ATR/ADX/CHOP (default 14)
        volume_24h_usdt: 24h volume for liquidity penalty
        spread_pct: Bid-ask spread as fraction of price

    Returns:
        Dict with all SEVI components + legacy oscillation_score
    """
    zero = {
        "atr_pct": 0, "adx": 50, "choppiness": 50,
        "oscillation_score": 0, "avg_speed": 0,
        "freq_extreme": 0, "kurtosis": 0, "evi_score": 0,
        "sei_score": 0, "safety_multiplier": 1.0,
        "macro_penalty": 1.0, "liquidity_penalty": 1.0,
        "vetoed": False, "veto_reason": "",
    }
    if len(klines) < period + 2:
        return zero

    # ── Hard Vetos ─────────────────────────────────────────────────
    is_vetoed, veto_reason = check_hard_vetos(klines, volume_24h_usdt, spread_pct)
    if is_vetoed:
        zero["vetoed"] = True
        zero["veto_reason"] = veto_reason
        return zero

    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    closes = [float(k[4]) for k in klines]

    current_price = closes[-1] if closes else 1.0
    if current_price <= 0:
        current_price = 1.0

    atr = _compute_atr(highs, lows, closes, period)
    atr_pct = (atr / current_price) * 100  # NATR

    adx = _compute_adx(highs, lows, closes, period)
    chop = _compute_choppiness(highs, lows, closes, period)

    # Speed + frequency + kurtosis + skew
    avg_speed, freq_extreme, kurtosis, skew = _compute_speed_and_frequency(closes)

    # Legacy score (backward compat)
    oscillation_score = atr_pct * (100 - adx) / 100

    # ── SEVI-M: Adjusted ATR (skew penalty) ────────────────────────
    skew_penalty = 1.0 / (1.0 + abs(skew))
    adjusted_atr_pct = atr_pct * skew_penalty

    # ── SEVI-M: Safety = macro_penalty × liquidity_penalty ─────────
    # Macro Penalty (MA200 slope — the single most important safety filter)
    macro_penalty = 1.0
    if len(closes) >= 200:
        ma200 = [sum(closes[i-200:i]) / 200 for i in range(200, len(closes)+1)]
        if len(ma200) >= 20 and ma200[-20] > 0:
            slope_ma = (ma200[-1] - ma200[-20]) / ma200[-20]
            if slope_ma < -0.03:
                macro_penalty = 0.2
            elif slope_ma < -0.01:
                macro_penalty = 0.6

    # Liquidity Penalty (volume tiers — critical for spot execution)
    liquidity_penalty = _compute_liquidity_penalty(volume_24h_usdt)

    # Safety = macro × liquidity (2 factors, no redundancy)
    safety_multiplier = macro_penalty * liquidity_penalty

    # ── SEVI = EVI × safety ────────────────────────────────────────
    chop_factor = chop / 50.0 if chop > 0 else 0.0
    evi_score = adjusted_atr_pct * avg_speed * freq_extreme * chop_factor
    sei_score = evi_score * safety_multiplier

    return {
        "atr_pct": atr_pct,
        "adx": adx,
        "choppiness": chop,
        "oscillation_score": oscillation_score,
        "avg_speed": avg_speed,
        "freq_extreme": freq_extreme,
        "kurtosis": kurtosis,
        "evi_score": evi_score,
        "sei_score": sei_score,
        "safety_multiplier": safety_multiplier,
        "macro_penalty": macro_penalty,
        "liquidity_penalty": liquidity_penalty,
        "current_price": current_price,
        "vetoed": False,
        "veto_reason": "",
    }


# ── Prospector ─────────────────────────────────────────────────────

class DorothyProspector:
    """Scans Binance symbols and ranks them for the Dorothy hub."""

    # Minimum 24h volume in USDT to consider (filters dust pairs)
    MIN_VOLUME_USDT = 500_000.0
    # Maximum MIN_NOTIONAL to allow (must fit our 6 USDT quoteOrderQty)
    MAX_MIN_NOTIONAL = 6.0
    # Number of 1h klines to fetch for analysis
    KLINE_LIMIT = 250  # Increased for MA200 computation (SEI v2)
    # Rate-limit: sequential batches to respect Binance frequency limits
    BATCH_SIZE = 3          # kline requests per batch
    BATCH_DELAY_SEC = 0.6   # delay between batches (avoids frequency limit)
    # Max symbols to analyze (after volume filter)
    ANALYSIS_POOL_SIZE = 30
    # Per-call timeout (seconds) to prevent hanging on unresponsive API
    API_CALL_TIMEOUT = 30
    MARGIN_CALL_TIMEOUT = 10  # shorter — most likely to fail without creds

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
        async def _run(fn: Any, timeout: float = self.API_CALL_TIMEOUT) -> Any:
            if _to_thread:
                coro = _to_thread(fn)
            else:
                coro = asyncio.get_event_loop().run_in_executor(None, fn)
            return await asyncio.wait_for(coro, timeout=timeout)

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
            iso_pairs = await _run(
                lambda: client.get_all_isolated_margin_symbols(),
                timeout=self.MARGIN_CALL_TIMEOUT,
            )
            for p in (iso_pairs if isinstance(iso_pairs, list) else []):
                if p.get("isMarginTrade") and p.get("quote") == "USDT":
                    margin_symbols.add(p.get("symbol", ""))
        except asyncio.TimeoutError:
            _LOG.warning("Prospector: margin symbols fetch timed out after %ds — continuing without margin data", self.MARGIN_CALL_TIMEOUT)
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
                scores = compute_oscillation_score(
                    klines,
                    volume_24h_usdt=profile.volume_24h_usdt,
                    spread_pct=profile.avg_spread_pct,
                )

                # Skip vetoed symbols
                if scores.get("vetoed"):
                    profile.error = f"VETOED: {scores.get('veto_reason', '')}"
                    _LOG.debug("Prospector: %s vetoed — %s", profile.symbol, profile.error)
                    return

                profile.atr_pct = scores["atr_pct"]
                profile.adx = scores["adx"]
                profile.choppiness = scores["choppiness"]
                profile.oscillation_score = scores["oscillation_score"]
                profile.avg_speed = scores["avg_speed"]
                profile.freq_extreme = scores["freq_extreme"]
                profile.kurtosis = scores["kurtosis"]
                profile.evi_score = scores["evi_score"]
                profile.sei_score = scores["sei_score"]
                profile.safety_multiplier = scores["safety_multiplier"]
                profile.current_price = scores["current_price"]

            except Exception as e:
                # Log full traceback for debugging
                _LOG.error('Prospector analysis error for %s: %s', profile.symbol, traceback.format_exc())
                profile.error = str(e)[:200]

        # Sequential batched processing
        for batch_start in range(0, len(analyze_pool), self.BATCH_SIZE):
            batch = analyze_pool[batch_start:batch_start + self.BATCH_SIZE]
            batch_num = (batch_start // self.BATCH_SIZE) + 1
            total_batches = (len(analyze_pool) + self.BATCH_SIZE - 1) // self.BATCH_SIZE
            _LOG.info("Prospector: processing batch %d/%d (%d symbols)...", batch_num, total_batches, len(batch))
            # Run batch concurrently (small batch = safe)
            await asyncio.gather(*[_analyze_one(p) for p in batch])
            # Throttle between batches
            if batch_start + self.BATCH_SIZE < len(analyze_pool):
                await asyncio.sleep(self.BATCH_DELAY_SEC)

        # ── Step 5: Rank by SEI (primary) ──────────────────────────
        scored = [p for p in analyze_pool if p.sei_score > 0]
        scored.sort(key=lambda p: p.sei_score, reverse=True)

        result = scored[:top_n]
        self._last_scan = result
        self._last_scan_ts = time.time()

        # Save to Telemetry Vault
        try:
            from runtime.core.telemetry_vault import get_telemetry_vault
            vault = get_telemetry_vault()
            for p in result:
                vault.log_prospector_scan(
                    symbol=p.symbol,
                    evi_score=p.sei_score, # Legacy mapping for telemetry compatibility
                    grade=p.grade,
                    adx=p.adx,
                    choppiness=p.choppiness,
                    avg_speed=p.avg_speed,
                    freq_extreme=p.freq_extreme,
                    kurtosis=p.kurtosis,
                    margin_eligible=p.margin_eligible,
                )
        except Exception as vault_err:
            _LOG.error("Prospector: Failed to save to telemetry vault: %s", vault_err)

        _LOG.info(
            "Prospector: scan complete. Top symbol: %s (SEI=%.4f, grade=%s)",
            result[0].symbol if result else "NONE",
            result[0].sei_score if result else 0,
            result[0].grade if result else "F",
        )

        # Auto-staging for top L0 recommendation
        rec = self.get_recommendation()
        if rec and rec.grade in ("S", "A"):
            try:
                # ── Trigger Visual Verification (Chart-IMG) ────────
                try:
                    from runtime.modules.vmo import get_vmo
                    vmo = get_vmo()
                    # Fire and forget
                    asyncio.create_task(vmo.fetch_triplet(rec.symbol))
                    _LOG.info("Prospector: Triggered VMO visual verification for %s", rec.symbol)
                except Exception as vmo_err:
                    _LOG.error("Prospector: Failed to trigger VMO: %s", vmo_err)

                from runtime.core.bot_coordinator import get_bot_coordinator
                coordinator = get_bot_coordinator()
                # Determine standard loop interval (L0 defaults)
                loop_interval = 450.0 
                # Avoid staging if this symbol is already running in Dorothy
                already_active = any(b.bot_id.endswith(rec.symbol.lower()) for b in coordinator._active.values())
                already_staged = any(s.bot_id.endswith(rec.symbol.lower()) for s in coordinator._staged.values())
                
                if not already_active and not already_staged:
                    bot_id = f"dorothy-{rec.symbol.lower()}-auto"
                    coordinator.stage_bot(
                        bot_id=bot_id,
                        hub_type="dorothy",
                        loop_interval_sec=loop_interval,
                        credential_ref="env_key"  # Default vault reference
                    )
                    _LOG.info("Prospector Auto-Stage: Staged %s based on Grade %s", bot_id, rec.grade)
                else:
                    _LOG.info("Prospector: %s already active/staged, skipping auto-stage", rec.symbol)
            except Exception as auto_err:
                _LOG.error("Prospector: Failed to auto-stage bot: %s", auto_err)
        else:
            if rec:
                _LOG.info("Prospector: Recommendation %s (Grade %s) below auto-stage threshold (S/A)", rec.symbol, rec.grade)
            else:
                _LOG.info("Prospector: No recommendation available for auto-staging")

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
            "╔══════════════════════════════════════════════════════════════════════════════════╗",
            "║          DOROTHY PROSPECTOR — SEVI-M (Safe Electric Volatility Index)            ║",
            "╠══════════════════════════════════════════════════════════════════════════════════╣",
            "║ #  │ Symbol      │  SEVI  │ Safety│ ATR%  │ Speed │ Freq │ CHOP │ Vol(M$)│ Margin║",
            "╠════╪═════════════╪════════╪═══════╪═══════╪═══════╪══════╪══════╪════════╪═══════╣",
        ]
        for i, p in enumerate(data, 1):
            margin_str = "  ✅ " if p.margin_eligible else "  ❌ "
            lines.append(
                f"║ {i:>2} │ {p.symbol:<11} │ {p.sei_score:>6.4f} │ {p.safety_multiplier:>5.2f} │ "
                f"{p.atr_pct:>5.2f} │ {p.avg_speed:>5.3f} │ {p.freq_extreme:>4.2f} │ "
                f"{p.choppiness:>4.1f} │ {p.volume_24h_usdt / 1e6:>5.1f}  │{margin_str}║"
            )
        lines.append(
            "╚══════════════════════════════════════════════════════════════════════════════════╝"
        )

        # Recommendation
        rec = self.get_recommendation()
        if rec:
            lines.append("")
            lines.append(f"🎯 RECOMENDACIÓN: {rec.symbol} (Grade {rec.grade})")
            lines.append(f"   SEI={rec.sei_score:.4f}  EVI={rec.evi_score:.4f}  Safety={rec.safety_multiplier:.2f}")
            lines.append(f"   ATR%={rec.atr_pct:.2f}  Speed={rec.avg_speed:.3f}  Freq={rec.freq_extreme:.2f}")
            lines.append(f"   ADX={rec.adx:.1f}  CHOP={rec.choppiness:.1f}  Kurt={rec.kurtosis:.1f}")
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
