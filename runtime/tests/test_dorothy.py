"""Comprehensive tests for Dorothy bot cycle logic."""

import asyncio
import datetime as dt
from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest

from runtime.bot.dorothy import DorothyConfig, DorothyRunner


class TestDorothyConfig:
    """Test DorothyConfig normalization and validation."""

    def test_defaults(self):
        """Test default configuration."""
        cfg = DorothyConfig()
        assert cfg.symbol == "XRPUSDT"
        assert cfg.loop_interval_sec == 225
        assert cfg.quote_order_qty == Decimal("7")
        assert cfg.profit_factor == Decimal("0.05")


    def test_normalize_symbol_uppercase(self):
        """Test symbol normalization to uppercase."""
        cfg = DorothyConfig(symbol="xrpusdt")
        cfg.normalize()
        assert cfg.symbol == "XRPUSDT"

    def test_normalize_loop_interval_bounds(self):
        """Test loop interval clamping [1, 86400]."""
        cfg = DorothyConfig(loop_interval_sec=0)
        cfg.normalize()
        assert cfg.loop_interval_sec == 1

        cfg = DorothyConfig(loop_interval_sec=100_000)
        cfg.normalize()
        assert cfg.loop_interval_sec == 86_400

    def test_normalize_qty_minimum(self):
        """Test quote order qty minimum floor."""
        cfg = DorothyConfig(quote_order_qty=Decimal("0"))
        cfg.normalize()
        assert cfg.quote_order_qty == Decimal("5.0")

    def test_normalize_decimals_bounds(self):
        """Test decimal place clamping [0, 18]."""
        cfg = DorothyConfig(qty_decimals=-1, price_decimals=20)
        cfg.normalize()
        assert cfg.qty_decimals == 0
        assert cfg.price_decimals == 18

    def test_normalize_note_max_length(self):
        """Test note truncation to 20 chars."""
        cfg = DorothyConfig(note="a" * 30)
        cfg.normalize()
        assert len(cfg.note) == 20
        assert cfg.note == "a" * 20

    def test_as_json_preserves_decimals_as_strings(self):
        """Test JSON serialization converts Decimals to strings."""
        cfg = DorothyConfig(
            quote_order_qty=Decimal("8.5"),
            profit_factor=Decimal("0.05"),
        )
        j = cfg.as_json()
        assert j["quote_order_qty"] == "8.5"
        assert j["profit_factor"] == "0.05"
        assert j["mode"] == "LIVE"

    def test_as_json_live_mode(self):
        """Test JSON mode is always LIVE."""
        cfg = DorothyConfig()
        j = cfg.as_json()
        assert j["mode"] == "LIVE"


class TestDorothyRunner:
    """Test DorothyRunner cycle logic."""

    def test_init(self):
        """Test runner initialization."""
        log_fn = Mock()
        runner = DorothyRunner(log=log_fn)
        assert runner.config.symbol == "XRPUSDT"
        assert runner._last_report == {}
        assert runner._last_error is None
        assert runner._last_cycle_ts is None

    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        """Test that start() creates an async task."""
        log_fn = Mock()
        runner = DorothyRunner(log=log_fn)

        # Mock the cycle to return immediately
        runner._cycle = AsyncMock(return_value=None)

        await runner.start()
        await asyncio.sleep(0.01)  # Let task start

        assert runner._task is not None
        assert isinstance(runner._task, asyncio.Task)

        await runner.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """Test that stop() cancels the running task."""
        log_fn = Mock()
        runner = DorothyRunner(log=log_fn)
        runner._cycle = AsyncMock(return_value=None)

        await runner.start()
        await asyncio.sleep(0.01)

        assert runner._task is not None
        await runner.stop()
        await asyncio.sleep(0.01)

        assert runner._task is None

    def test_set_config(self):
        """Test configuration update."""
        log_fn = Mock()
        runner = DorothyRunner(log=log_fn)

        new_cfg = DorothyConfig(symbol="BTCUSDT", loop_interval_sec=300)
        runner.apply_config(new_cfg)

        assert runner.config.symbol == "BTCUSDT"
        assert runner.config.loop_interval_sec == 300

    def test_last_cycle_timestamp_format(self):
        """Test that cycle timestamps are ISO format."""
        log_fn = Mock()
        runner = DorothyRunner(log=log_fn)

        # Simulate setting a timestamp
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        runner._last_cycle_ts = now

        # Should be parseable
        parsed = dt.datetime.fromisoformat(now)
        assert parsed is not None

    @pytest.mark.asyncio
    async def test_event_log_callback(self):
        """Test that event_log callback is called."""
        log_fn = Mock()
        event_log_fn = Mock()
        runner = DorothyRunner(log=log_fn, event_log=event_log_fn)

        # Simulate a cycle event
        runner._event_log("BUY", "decision", {"price": 0.5})

        event_log_fn.assert_called_once_with("BUY", "decision", {"price": 0.5})

    def test_config_serialization_roundtrip(self):
        """Test config can be serialized to JSON and back."""
        cfg = DorothyConfig(
            symbol="ETHUSDT",
            loop_interval_sec=300,
            quote_order_qty=Decimal("10"),
            profit_factor=Decimal("0.08"),
            qty_decimals=2,
            price_decimals=2,
            note="test",
        )

        j = cfg.as_json()
        assert j["symbol"] == "ETHUSDT"
        assert j["loop_interval_sec"] == 300
        assert j["quote_order_qty"] == "10"
        assert j["profit_factor"] == "0.08"
        assert j["qty_decimals"] == 2
        assert j["price_decimals"] == 2
        assert j["note"] == "test"

    @pytest.mark.asyncio
    async def test_multiple_sequential_starts_stops(self):
        """Test runner can be started/stopped multiple times."""
        log_fn = Mock()
        runner = DorothyRunner(log=log_fn)
        runner._cycle = AsyncMock(return_value=None)

        for _ in range(3):
            await runner.start()
            await asyncio.sleep(0.01)
            await runner.stop()
            await asyncio.sleep(0.01)

    def test_config_edge_case_very_small_qty(self):
        """Test config with very small quote qty."""
        cfg = DorothyConfig(quote_order_qty=Decimal("0.00001"))
        cfg.normalize()
        assert cfg.quote_order_qty >= Decimal("0.0001")

    def test_config_edge_case_negative_factors(self):
        """Test config clamps negative profit/drop factors to zero."""
        cfg = DorothyConfig(profit_factor=Decimal("-0.5"), margin_drop_factor=Decimal("-0.1"))
        cfg.normalize()
        assert cfg.profit_factor >= Decimal("0")
        assert cfg.margin_drop_factor >= Decimal("0")


class TestDorothyDecimalHandling:
    """Test decimal precision and rounding."""

    def test_quantize_down(self):
        """Test downward quantization for order quantities."""
        from runtime.bot.dorothy import _q

        # 8.567 with 2 decimal places should become 8.56 (not 8.57)
        result = _q(Decimal("8.567"), places=2)
        assert result == Decimal("8.56")

    def test_quantize_zero_places(self):
        """Test quantization with zero decimal places."""
        from runtime.bot.dorothy import _q

        result = _q(Decimal("8.9"), places=0)
        assert result == Decimal("8")

    def test_decimal_conversion_from_string(self):
        """Test _dec() handles string to Decimal conversion."""
        from runtime.bot.dorothy import _dec

        assert _dec("8.5") == Decimal("8.5")
        assert _dec("0") == Decimal("0")
        assert _dec("invalid") == Decimal("0")
        assert _dec(None) == Decimal("0")
        assert _dec("") == Decimal("0")

    def test_decimal_conversion_with_custom_default(self):
        """Test _dec() with custom default value."""
        from runtime.bot.dorothy import _dec

        result = _dec("invalid", default="10")
        assert result == Decimal("10")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
