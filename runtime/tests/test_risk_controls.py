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


# ── TrendSignal unit tests (replaced RegimeFilter) ─────────────────

class TestTrendSignalHelpers:
    def test_compute_heikin_ashi_basic(self):
        from runtime.modules.trend_signal import compute_heikin_ashi

        # Simulate 3 raw klines: [open_time, open, high, low, close, ...]
        klines = [
            [0, "100", "110", "95", "105", "1000"],
            [1, "106", "112", "100", "108", "1000"],
            [2, "107", "115", "103", "110", "1000"],
        ]
        ha = compute_heikin_ashi(klines)
        assert len(ha) == 3
        # HA[0] open = (100 + 105) / 2 = 102.5
        assert ha[0]["ha_open"] == 102.5
        # HA[0] close = (100 + 110 + 95 + 105) / 4 = 102.5
        assert ha[0]["ha_close"] == 102.5

    def test_compute_trend_bullish(self):
        from runtime.modules.trend_signal import compute_trend

        ha = [
            {"ha_open": 100.0, "ha_close": 102.0, "ha_high": 103.0, "ha_low": 99.0, "ts": 0},
            {"ha_open": 105.0, "ha_close": 107.0, "ha_high": 108.0, "ha_low": 104.0, "ts": 1},
        ]
        result = compute_trend(ha)
        assert result["signal"] == "BULLISH"
        assert result["ma1"] > result["ma2"]

    def test_compute_trend_bearish(self):
        from runtime.modules.trend_signal import compute_trend

        ha = [
            {"ha_open": 110.0, "ha_close": 108.0, "ha_high": 111.0, "ha_low": 107.0, "ts": 0},
            {"ha_open": 100.0, "ha_close": 98.0, "ha_high": 101.0, "ha_low": 97.0, "ts": 1},
        ]
        result = compute_trend(ha)
        assert result["signal"] == "BEARISH"

    def test_compute_entry_gate_clear(self):
        from runtime.modules.trend_signal import compute_entry_gate

        result = compute_entry_gate(current_price=99.0, candle_open_1h=100.0)
        assert result["gate"] == "CLEAR"

    def test_compute_entry_gate_blocked(self):
        from runtime.modules.trend_signal import compute_entry_gate

        result = compute_entry_gate(current_price=101.0, candle_open_1h=100.0)
        assert result["gate"] == "BLOCKED"


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
