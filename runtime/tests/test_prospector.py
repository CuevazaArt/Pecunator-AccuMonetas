"""Tests for DorothyProspector — symbol scanner and oscillation scoring."""
import pytest
import math
from decimal import Decimal

from runtime.modules.prospector import (
    compute_oscillation_score,
    _compute_atr,
    _compute_adx,
    _compute_choppiness,
    SymbolProfile,
    DorothyProspector,
)


# ── Helper: generate synthetic klines ─────────────────────────────

def _make_klines(prices: list[float], spread_pct: float = 0.02) -> list[list]:
    """Generate synthetic klines from a list of close prices.

    Each kline: [open_time, open, high, low, close, volume, ...]
    """
    klines = []
    for i, close in enumerate(prices):
        open_p = close * (1 - spread_pct / 2)
        high = close * (1 + spread_pct)
        low = close * (1 - spread_pct)
        klines.append([
            i * 3600000,  # open_time (ms)
            str(open_p),
            str(high),
            str(low),
            str(close),
            "1000",  # volume
        ])
    return klines


def _choppy_klines(base: float = 2.0, amplitude: float = 0.10, n: int = 50) -> list[list]:
    """Generate highly oscillatory klines (up-down-up-down)."""
    prices = []
    for i in range(n):
        if i % 2 == 0:
            prices.append(base * (1 + amplitude))
        else:
            prices.append(base * (1 - amplitude))
    return _make_klines(prices, spread_pct=amplitude * 0.5)


def _trending_klines(start: float = 2.0, end: float = 4.0, n: int = 50) -> list[list]:
    """Generate strongly trending klines (steady up)."""
    step = (end - start) / n
    prices = [start + step * i for i in range(n)]
    return _make_klines(prices, spread_pct=0.005)


def _flat_klines(price: float = 2.0, n: int = 50) -> list[list]:
    """Generate flat/stagnant klines."""
    return _make_klines([price] * n, spread_pct=0.001)


# ── ATR tests ─────────────────────────────────────────────────────

class TestATR:
    def test_zero_on_insufficient_data(self):
        assert _compute_atr([1, 2], [0.5, 1], [1, 2], period=14) == 0.0

    def test_positive_for_volatile(self):
        klines = _choppy_klines(amplitude=0.10, n=30)
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        closes = [float(k[4]) for k in klines]
        atr = _compute_atr(highs, lows, closes, period=14)
        assert atr > 0

    def test_higher_for_more_volatile(self):
        k_low = _choppy_klines(amplitude=0.02, n=30)
        k_high = _choppy_klines(amplitude=0.15, n=30)

        def _atr(klines):
            h = [float(k[2]) for k in klines]
            l = [float(k[3]) for k in klines]
            c = [float(k[4]) for k in klines]
            return _compute_atr(h, l, c, 14)

        assert _atr(k_high) > _atr(k_low)


# ── ADX tests ─────────────────────────────────────────────────────

class TestADX:
    def test_trending_has_higher_adx(self):
        k_trend = _trending_klines(2.0, 4.0, n=30)
        k_chop = _choppy_klines(amplitude=0.10, n=30)

        def _adx(klines):
            h = [float(k[2]) for k in klines]
            l = [float(k[3]) for k in klines]
            c = [float(k[4]) for k in klines]
            return _compute_adx(h, l, c, 14)

        adx_trend = _adx(k_trend)
        adx_chop = _adx(k_chop)
        # Trending market should have higher directional strength
        assert adx_trend > adx_chop


# ── Choppiness Index tests ────────────────────────────────────────

class TestChoppiness:
    def test_choppy_market_scores_high(self):
        klines = _choppy_klines(amplitude=0.10, n=30)
        h = [float(k[2]) for k in klines]
        l = [float(k[3]) for k in klines]
        c = [float(k[4]) for k in klines]
        chop = _compute_choppiness(h, l, c, 14)
        assert chop > 50  # Choppy should score above 50

    def test_trending_market_scores_lower(self):
        k_chop = _choppy_klines(amplitude=0.10, n=30)
        k_trend = _trending_klines(2.0, 6.0, n=30)

        def _chop(klines):
            h = [float(k[2]) for k in klines]
            l = [float(k[3]) for k in klines]
            c = [float(k[4]) for k in klines]
            return _compute_choppiness(h, l, c, 14)

        assert _chop(k_chop) > _chop(k_trend)


# ── Oscillation Score tests ───────────────────────────────────────

class TestOscillationScore:
    def test_choppy_beats_trending(self):
        """Choppy high-amplitude market should score higher than trending."""
        choppy = compute_oscillation_score(_choppy_klines(amplitude=0.10, n=50))
        trending = compute_oscillation_score(_trending_klines(2.0, 4.0, n=50))
        assert choppy["oscillation_score"] > trending["oscillation_score"]

    def test_flat_market_scores_low(self):
        flat = compute_oscillation_score(_flat_klines(n=50))
        assert flat["oscillation_score"] < 0.5

    def test_insufficient_data_returns_zero(self):
        result = compute_oscillation_score([[0, "1", "1", "1", "1", "1"]] * 5)
        assert result["oscillation_score"] == 0

    def test_high_amplitude_scores_higher(self):
        low_amp = compute_oscillation_score(_choppy_klines(amplitude=0.03, n=50))
        high_amp = compute_oscillation_score(_choppy_klines(amplitude=0.15, n=50))
        assert high_amp["oscillation_score"] > low_amp["oscillation_score"]


# ── SymbolProfile tests ──────────────────────────────────────────

class TestSymbolProfile:
    def test_grade_s(self):
        p = SymbolProfile(oscillation_score=3.5)
        assert p.grade == "S"

    def test_grade_a(self):
        p = SymbolProfile(oscillation_score=2.5)
        assert p.grade == "A"

    def test_grade_f(self):
        p = SymbolProfile(oscillation_score=0.1)
        assert p.grade == "F"

    def test_as_json(self):
        p = SymbolProfile(
            symbol="XRPUSDT",
            oscillation_score=2.5,
            atr_pct=3.0,
            adx=20.0,
            choppiness=65.0,
            margin_eligible=True,
        )
        j = p.as_json()
        assert j["symbol"] == "XRPUSDT"
        assert j["grade"] == "A"
        assert j["margin_eligible"] is True


# ── Prospector recommendation logic ──────────────────────────────

class TestRecommendation:
    def test_prefers_margin_eligible(self):
        prospector = DorothyProspector()
        prospector._last_scan = [
            SymbolProfile(symbol="BTCUSDT", oscillation_score=5.0, margin_eligible=False),
            SymbolProfile(symbol="XRPUSDT", oscillation_score=3.0, margin_eligible=True),
        ]
        rec = prospector.get_recommendation()
        assert rec is not None
        assert rec.symbol == "XRPUSDT"

    def test_fallback_to_best_if_no_margin(self):
        prospector = DorothyProspector()
        prospector._last_scan = [
            SymbolProfile(symbol="BTCUSDT", oscillation_score=5.0, margin_eligible=False),
        ]
        rec = prospector.get_recommendation()
        assert rec is not None
        assert rec.symbol == "BTCUSDT"

    def test_no_scan_returns_none(self):
        prospector = DorothyProspector()
        assert prospector.get_recommendation() is None

    def test_format_report(self):
        prospector = DorothyProspector()
        prospector._last_scan = [
            SymbolProfile(
                symbol="XRPUSDT", oscillation_score=2.5, atr_pct=3.0,
                adx=15.0, choppiness=70.0, volume_24h_usdt=5_000_000,
                margin_eligible=True,
            ),
        ]
        report = prospector.format_report()
        assert "XRPUSDT" in report
        assert "RECOMENDACIÓN" in report
