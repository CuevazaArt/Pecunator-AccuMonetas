"""Tests for v0.11 risk control modules."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path



# ── OrderLedger tests ───────────────────────────────────────────────

class TestOrderLedger:
    def test_record_and_recent(self, tmp_path: Path):
        from runtime.core.order_ledger import OrderLedger

        ledger = OrderLedger(tmp_path)
        row_id = ledger.record(
            bot_id="test-bot", bot_type="dorothy", symbol="XRPUSDT",
            side="BUY", order_type="MARKET", qty="10.5",
            quote_order_qty="8", reason="BUY_AND_SELL",
            execution_mode="SIMULATED",
        )
        assert row_id > 0

        recent = ledger.recent(limit=10)
        assert len(recent) == 1
        assert recent[0]["symbol"] == "XRPUSDT"
        assert recent[0]["side"] == "BUY"
        assert recent[0]["execution_mode"] == "SIMULATED"

    def test_update_binance_response(self, tmp_path: Path):
        from runtime.core.order_ledger import OrderLedger

        ledger = OrderLedger(tmp_path)
        row_id = ledger.record(
            bot_id="test", bot_type="masha", symbol="SOLUSDT",
            side="SELL", order_type="LIMIT", qty="5", price="150.00",
            reason="TAKE_PROFIT", execution_mode="LIVE",
        )
        ledger.update_binance_response(row_id, "12345678", "FILLED")
        recent = ledger.recent(limit=1)
        assert recent[0]["binance_order_id"] == "12345678"
        assert recent[0]["binance_status"] == "FILLED"

    def test_stats(self, tmp_path: Path):
        from runtime.core.order_ledger import OrderLedger

        ledger = OrderLedger(tmp_path)
        ledger.record(bot_id="a", bot_type="dorothy", symbol="X", side="BUY",
                       order_type="MARKET", qty="1", reason="test",
                       execution_mode="SIMULATED")
        ledger.record(bot_id="b", bot_type="dorothy", symbol="Y", side="BUY",
                       order_type="MARKET", qty="1", reason="test",
                       execution_mode="LIVE")
        stats = ledger.stats()
        assert stats["total_orders"] == 2
        assert stats["live_orders"] == 1
        assert stats["simulated_orders"] == 1


# ── RegimeFilter unit tests ────────────────────────────────────────

class TestRegimeFilterHelpers:
    def test_ema_basic(self):
        from runtime.core.regime_filter import _ema

        data = [Decimal(str(i)) for i in range(1, 11)]
        result = _ema(data, 5)
        assert result > 0

    def test_adx_di_insufficient_data(self):
        from runtime.core.regime_filter import _adx_di

        highs = [Decimal("10")] * 5
        lows = [Decimal("9")] * 5
        closes = [Decimal("9.5")] * 5
        adx, plus_di, minus_di = _adx_di(highs, lows, closes, period=14)
        assert adx == Decimal("0")

    def test_vol_zscore_insufficient(self):
        from runtime.core.regime_filter import _vol_zscore

        closes = [Decimal("100")] * 5
        z = _vol_zscore(closes, lookback=20)
        assert z == Decimal("0")


# ── VolSizer tests ──────────────────────────────────────────────────

class TestVolSizer:
    def test_insufficient_data_returns_base(self):
        from runtime.core.vol_sizer import compute_adjusted_qty

        base = Decimal("8")
        closes = [Decimal("100")] * 5
        adj, diag = compute_adjusted_qty(base, closes, lookback=20)
        assert adj == base
        assert diag["adjusted"] == "false"

    def test_adjusts_with_enough_data(self):
        from runtime.core.vol_sizer import compute_adjusted_qty
        import random
        random.seed(42)

        # Simulate 60 days of data with moderate volatility
        base = Decimal("8")
        closes = [Decimal("100")]
        for _ in range(59):
            change = Decimal(str(random.uniform(-0.03, 0.03)))
            closes.append(closes[-1] * (Decimal("1") + change))

        adj, diag = compute_adjusted_qty(base, closes, lookback=20)
        assert diag["adjusted"] == "true"
        # Should be between floor (4) and ceiling (16)
        assert Decimal("4") <= adj <= Decimal("16")


# ── TrailingTP tests ────────────────────────────────────────────────

class TestTrailingTP:
    def test_inactive_below_tp(self):
        from runtime.core.trailing_tp import TrailingTP

        tracker = TrailingTP()
        action = tracker.update("XRPUSDT", Decimal("1.40"), Decimal("1.50"), Decimal("0.02"))
        assert action == "INACTIVE"

    def test_activates_above_tp(self):
        from runtime.core.trailing_tp import TrailingTP

        tracker = TrailingTP()
        action = tracker.update("XRPUSDT", Decimal("1.55"), Decimal("1.50"), Decimal("0.02"))
        assert action == "TRAILING"

    def test_sell_when_trail_stop_hit(self):
        from runtime.core.trailing_tp import TrailingTP

        tracker = TrailingTP(atr_multiplier=Decimal("1.0"))
        # Activate
        tracker.update("XRPUSDT", Decimal("1.55"), Decimal("1.50"), Decimal("0.02"))
        # Price rises
        tracker.update("XRPUSDT", Decimal("1.60"), Decimal("1.50"), Decimal("0.02"))
        # Price drops to trail stop (1.60 - 0.02 = 1.58)
        action = tracker.update("XRPUSDT", Decimal("1.57"), Decimal("1.50"), Decimal("0.02"))
        assert action == "SELL"

    def test_atr_computation(self):
        from runtime.core.trailing_tp import compute_atr

        highs = [Decimal(str(100 + i * 0.5)) for i in range(20)]
        lows = [Decimal(str(99 + i * 0.5)) for i in range(20)]
        closes = [Decimal(str(99.5 + i * 0.5)) for i in range(20)]
        atr = compute_atr(highs, lows, closes, period=14)
        assert atr > 0


# ── BacktestEngine tests ───────────────────────────────────────────

class TestBacktestEngine:
    def test_basic_run(self):
        from runtime.backtest.engine import BacktestEngine, Candle, BacktestStrategy

        class BuyEvery10(BacktestStrategy):
            def on_candle(self, idx, candle, portfolio):
                if idx % 10 == 0 and idx > 0:
                    return [{"side": "BUY", "qty": Decimal("1"), "reason": "test"}]
                if idx % 10 == 5 and portfolio.position_qty > 0:
                    return [{"side": "SELL", "qty": portfolio.position_qty, "reason": "test"}]
                return []

        candles = [
            Candle(timestamp_ms=i * 60000, open=Decimal("100") + Decimal(str(i * 0.1)),
                   high=Decimal("101") + Decimal(str(i * 0.1)),
                   low=Decimal("99") + Decimal(str(i * 0.1)),
                   close=Decimal("100") + Decimal(str(i * 0.1)),
                   volume=Decimal("1000"))
            for i in range(50)
        ]

        engine = BacktestEngine()
        result = engine.run(BuyEvery10(), candles, symbol="TEST")
        summary = result.summary()

        assert summary["candles"] == 50
        assert summary["total_trades"] > 0
        assert len(result.equity_curve) == 50
