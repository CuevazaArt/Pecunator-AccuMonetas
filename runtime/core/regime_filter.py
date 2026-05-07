"""T1.1: Regime filter — gate that MUST pass before any bot can BUY.

Conditions (ALL must be true for BUY to be allowed):
1. BTC > EMA200 on 1D timeframe  → only buy in structural uptrends
2. Symbol's ADX(14) on 4H:
   - ADX < 25: ranging/choppy → OK for mean-reversion strategies
   - ADX > 25 AND +DI > -DI: trending UP → OK for momentum
   - ADX > 25 AND -DI > +DI: trending DOWN → BLOCKED
3. Symbol's 20D realized vol z-score < 1.5 → don't buy in vol spikes
4. MACRO SHIELD:
   - Fear & Greed Index < 20 (Extreme Fear) → BLOCKED
   - Activity score < 0.45 (dead zone / illiquid hours) → BLOCKED

POLICY: FAIL-CLOSED. If any guard fails to evaluate (API error, timeout),
the trade is BLOCKED. This is the opposite of fail-open and prevents the
scenario where guard failures simultaneously degrade to "trade permitted".

This filter alone would have prevented the majority of the -$115k losses
documented in audit_report.txt, because:
- XRP, XLM, PENGU were in sustained downtrends (ADX>25, -DI dominant)
- BTC was below EMA200 during the worst accumulation periods
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.core.regime_filter")


def _ema(data: list[Decimal], period: int) -> Decimal:
    """Exponential moving average of the last `period` values."""
    if not data:
        return Decimal("0")
    if len(data) < period:
        return sum(data, Decimal("0")) / Decimal(len(data))
    k = Decimal("2") / (Decimal(period) + Decimal("1"))
    ema = data[0]
    for v in data[1:]:
        ema = v * k + ema * (Decimal("1") - k)
    return ema


def _adx_di(highs: list[Decimal], lows: list[Decimal], closes: list[Decimal],
            period: int = 14) -> tuple[Decimal, Decimal, Decimal]:
    """Compute ADX, +DI, -DI from OHLC data.

    Returns (adx, plus_di, minus_di) as Decimal.
    Requires at least period+1 bars.
    """
    n = len(closes)
    if n < period + 1:
        return Decimal("0"), Decimal("0"), Decimal("0")

    tr_list: list[Decimal] = []
    plus_dm_list: list[Decimal] = []
    minus_dm_list: list[Decimal] = []

    for i in range(1, n):
        high_diff = highs[i] - highs[i - 1]
        low_diff = lows[i - 1] - lows[i]
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)
        plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else Decimal("0")
        minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else Decimal("0")
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)

    if len(tr_list) < period:
        return Decimal("0"), Decimal("0"), Decimal("0")

    # Wilder smoothing
    atr = sum(tr_list[:period], Decimal("0"))
    plus_dm_smooth = sum(plus_dm_list[:period], Decimal("0"))
    minus_dm_smooth = sum(minus_dm_list[:period], Decimal("0"))

    dx_list: list[Decimal] = []
    p = Decimal(period)

    for i in range(period, len(tr_list)):
        atr = atr - (atr / p) + tr_list[i]
        plus_dm_smooth = plus_dm_smooth - (plus_dm_smooth / p) + plus_dm_list[i]
        minus_dm_smooth = minus_dm_smooth - (minus_dm_smooth / p) + minus_dm_list[i]

        plus_di = (plus_dm_smooth / atr * Decimal("100")) if atr > 0 else Decimal("0")
        minus_di = (minus_dm_smooth / atr * Decimal("100")) if atr > 0 else Decimal("0")
        di_sum = plus_di + minus_di
        dx = abs(plus_di - minus_di) / di_sum * Decimal("100") if di_sum > 0 else Decimal("0")
        dx_list.append(dx)

    if not dx_list:
        return Decimal("0"), Decimal("0"), Decimal("0")

    # ADX = smoothed average of DX
    adx = sum(dx_list[:period], Decimal("0")) / p if len(dx_list) >= period else sum(dx_list, Decimal("0")) / Decimal(len(dx_list))
    for i in range(period, len(dx_list)):
        adx = (adx * (p - Decimal("1")) + dx_list[i]) / p

    # Return last +DI / -DI
    if atr > 0:
        final_plus_di = plus_dm_smooth / atr * Decimal("100")
        final_minus_di = minus_dm_smooth / atr * Decimal("100")
    else:
        final_plus_di = Decimal("0")
        final_minus_di = Decimal("0")

    return adx, final_plus_di, final_minus_di


def _vol_zscore(closes: list[Decimal], lookback: int = 20) -> Decimal:
    """Z-score of recent realized volatility vs its own history."""
    if len(closes) < lookback + 10:
        return Decimal("0")  # Not enough data, allow trade

    # Daily returns
    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

    if len(returns) < lookback:
        return Decimal("0")

    # Recent vol (std of last `lookback` returns)
    recent = returns[-lookback:]
    mean_r = sum(recent, Decimal("0")) / Decimal(len(recent))
    var_r = sum((r - mean_r) ** 2 for r in recent) / Decimal(len(recent))
    recent_vol = var_r.sqrt() if var_r > 0 else Decimal("0")

    # Historical vol windows
    vol_samples: list[Decimal] = []
    for start in range(0, len(returns) - lookback, lookback):
        window = returns[start:start + lookback]
        m = sum(window, Decimal("0")) / Decimal(len(window))
        v = sum((r - m) ** 2 for r in window) / Decimal(len(window))
        vol_samples.append(v.sqrt() if v > 0 else Decimal("0"))

    if len(vol_samples) < 2:
        return Decimal("0")

    mean_vol = sum(vol_samples, Decimal("0")) / Decimal(len(vol_samples))
    var_vol = sum((v - mean_vol) ** 2 for v in vol_samples) / Decimal(len(vol_samples))
    std_vol = var_vol.sqrt() if var_vol > 0 else Decimal("0")

    if std_vol <= 0:
        return Decimal("0")

    return (recent_vol - mean_vol) / std_vol


class RegimeFilter:
    """Gate that blocks BUY orders in unfavorable market regimes.

    Usage:
        filter = RegimeFilter()
        allowed, reason = await filter.is_favorable(symbol, client)
        if not allowed:
            return "BLOCKED_REGIME"
    """

    # Cache regime decisions to avoid hammering API.
    # 60s is responsive enough for flash crashes while still saving weight.
    # Previously 300s — reduced after audit identified stale-cache risk.
    CACHE_TTL_SEC = 60

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, bool, str]] = {}
        self._btc_regime_cache: Optional[tuple[float, bool, str]] = None
        self._macro_cache: Optional[tuple[float, bool, str]] = None

    async def is_favorable(
        self,
        symbol: str,
        client: Any,
        *,
        _to_thread: Any = None,
    ) -> tuple[bool, str]:
        """Check if market regime allows buying.

        Returns (allowed: bool, reason: str).
        """
        import asyncio
        if _to_thread is None:
            async def _to_thread(fn):
                return await asyncio.to_thread(fn)

        now = time.time()

        # Check cache
        cached = self._cache.get(symbol)
        if cached and (now - cached[0]) < self.CACHE_TTL_SEC:
            return cached[1], cached[2]

        reasons: list[str] = []
        allowed = True

        # ── Condition 1: BTC > EMA200 on 1D ──────────────────────────
        try:
            btc_ok, btc_reason = await self._check_btc_ema200(client, _to_thread, now)
            if not btc_ok:
                allowed = False
                reasons.append(btc_reason)
        except Exception as e:
            _LOG.warning("regime_filter: BTC EMA200 check failed: %s — FAIL-CLOSED", e)
            allowed = False
            reasons.append(f"FAIL_CLOSED:btc_ema200_error:{e}")

        # ── Condition 2: Symbol ADX/DI on 4H ─────────────────────────
        try:
            adx_ok, adx_reason = await self._check_adx(symbol, client, _to_thread)
            if not adx_ok:
                allowed = False
                reasons.append(adx_reason)
        except Exception as e:
            _LOG.warning("regime_filter: ADX check failed for %s: %s — FAIL-CLOSED", symbol, e)
            allowed = False
            reasons.append(f"FAIL_CLOSED:adx_error:{e}")

        # ── Condition 3: Vol z-score on 1D ────────────────────────────
        try:
            vol_ok, vol_reason = await self._check_vol_zscore(symbol, client, _to_thread)
            if not vol_ok:
                allowed = False
                reasons.append(vol_reason)
        except Exception as e:
            _LOG.warning("regime_filter: vol z-score check failed for %s: %s — FAIL-CLOSED", symbol, e)
            allowed = False
            reasons.append(f"FAIL_CLOSED:vol_error:{e}")

        # ── Condition 4: MACRO SHIELD (Fear & Greed + Activity) ──────
        try:
            macro_ok, macro_reason = await self._check_macro_shield()
            if not macro_ok:
                allowed = False
                reasons.append(macro_reason)
        except Exception as e:
            _LOG.warning("regime_filter: macro shield check failed: %s — FAIL-CLOSED", e)
            allowed = False
            reasons.append(f"FAIL_CLOSED:macro_error:{e}")

        reason_str = "; ".join(reasons) if reasons else "all_conditions_passed"
        self._cache[symbol] = (now, allowed, reason_str)

        if not allowed:
            _LOG.info("regime_filter: BLOCKED %s — %s", symbol, reason_str)

        return allowed, reason_str

    async def _check_btc_ema200(
        self, client: Any, _to_thread: Any, now: float,
    ) -> tuple[bool, str]:
        """BTC must be above its 200-day EMA."""
        # Use cache if fresh
        if self._btc_regime_cache and (now - self._btc_regime_cache[0]) < 3600:
            return self._btc_regime_cache[1], self._btc_regime_cache[2]

        klines = await _to_thread(
            lambda: client.get_klines(symbol="BTCUSDT", interval="1d", limit=210)
        )
        if not isinstance(klines, list) or len(klines) < 200:
            return True, "btc_insufficient_data"

        closes = [Decimal(str(k[4])) for k in klines]
        ema200 = _ema(closes, 200)
        current = closes[-1]
        ok = current > ema200
        reason = f"btc_ema200:{'above' if ok else 'BELOW'}(price={current},ema={ema200:.2f})"
        self._btc_regime_cache = (now, ok, reason)
        return ok, reason

    async def _check_adx(
        self, symbol: str, client: Any, _to_thread: Any,
    ) -> tuple[bool, str]:
        """ADX/DI trend direction check on 4H timeframe."""
        klines = await _to_thread(
            lambda: client.get_klines(symbol=symbol, interval="4h", limit=50)
        )
        if not isinstance(klines, list) or len(klines) < 20:
            return True, "adx_insufficient_data"

        highs = [Decimal(str(k[2])) for k in klines]
        lows = [Decimal(str(k[3])) for k in klines]
        closes = [Decimal(str(k[4])) for k in klines]

        adx, plus_di, minus_di = _adx_di(highs, lows, closes, period=14)

        if adx < 25:
            # Ranging/choppy market — OK for mean-reversion
            return True, f"adx_ranging(adx={adx:.1f})"
        elif plus_di > minus_di:
            # Trending UP — OK
            return True, f"adx_trend_up(adx={adx:.1f},+di={plus_di:.1f},-di={minus_di:.1f})"
        else:
            # Trending DOWN — BLOCKED
            return False, f"adx_trend_DOWN(adx={adx:.1f},+di={plus_di:.1f},-di={minus_di:.1f})"

    async def _check_vol_zscore(
        self, symbol: str, client: Any, _to_thread: Any,
    ) -> tuple[bool, str]:
        """Reject if realized vol is >1.5 standard deviations above its own mean."""
        klines = await _to_thread(
            lambda: client.get_klines(symbol=symbol, interval="1d", limit=90)
        )
        if not isinstance(klines, list) or len(klines) < 30:
            return True, "vol_insufficient_data"

        closes = [Decimal(str(k[4])) for k in klines]
        zscore = _vol_zscore(closes, lookback=20)

        threshold = Decimal("1.5")
        if zscore > threshold:
            return False, f"vol_SPIKE(z={zscore:.2f}>1.5)"
        return True, f"vol_normal(z={zscore:.2f})"

    async def _check_macro_shield(self) -> tuple[bool, str]:
        """Block trading during extreme fear or illiquid dead-zone hours.

        Sources: /api/v1/events/summary (Fear & Greed from alternative.me,
        activity heatmap from statistical model).

        Policy: FAIL-CLOSED — if we can't fetch, block.
        """
        import httpx

        now = time.time()
        # Use cached result if fresh (60s TTL)
        if self._macro_cache and (now - self._macro_cache[0]) < 60:
            return self._macro_cache[1], self._macro_cache[2]

        try:
            async with httpx.AsyncClient(timeout=5.0) as hc:
                resp = await hc.get("http://127.0.0.1:8000/api/v1/events/summary")
                if resp.status_code != 200:
                    return False, "macro:FAIL_CLOSED:api_unavailable"
                data = resp.json()
        except Exception as e:
            # FAIL-CLOSED: if the events API is unreachable, block
            return False, f"macro:FAIL_CLOSED:api_unreachable({e})"

        reasons: list[str] = []
        ok = True

        # Gate 1: Fear & Greed < 20 = EXTREME FEAR → block all buys
        fg = data.get("fear_greed_value")
        if fg is not None and isinstance(fg, (int, float)) and fg < 20:
            ok = False
            reasons.append(f"macro:EXTREME_FEAR(fg={fg})")

        # Gate 2: Activity score < 0.45 = DEAD ZONE → block (spreads too wide)
        activity = data.get("activity_score")
        if activity is not None and isinstance(activity, (int, float)) and activity < 0.45:
            ok = False
            reasons.append(f"macro:DEAD_ZONE(activity={activity})")

        reason = "; ".join(reasons) if reasons else "macro:ok"
        self._macro_cache = (now, ok, reason)
        return ok, reason

    def status(self) -> dict[str, Any]:
        """Return current regime state for all cached symbols."""
        result: dict[str, Any] = {}
        for symbol, (ts, allowed, reason) in self._cache.items():
            result[symbol] = {
                "allowed": allowed,
                "reason": reason,
                "age_sec": int(time.time() - ts),
            }
        if self._btc_regime_cache:
            result["_btc_global"] = {
                "allowed": self._btc_regime_cache[1],
                "reason": self._btc_regime_cache[2],
                "age_sec": int(time.time() - self._btc_regime_cache[0]),
            }
        return result


# ── Singleton ───────────────────────────────────────────────────────

_filter: Optional[RegimeFilter] = None


def get_regime_filter() -> RegimeFilter:
    """Get or create the global RegimeFilter singleton."""
    global _filter
    if _filter is None:
        _filter = RegimeFilter()
    return _filter
