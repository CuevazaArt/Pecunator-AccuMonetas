"""Tests for Elphaba (Anti-Dorothy) bearish short bot."""
import asyncio
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from runtime.bot.elphaba import ElphabaConfig, ElphabaRunner


# ── Config Tests ─────────────────────────────────────────────────

class TestElphabaConfig:
    def test_defaults(self):
        c = ElphabaConfig()
        c.normalize()
        assert c.symbol == "XRPUSDT"
        assert c.quote_order_qty == Decimal("7")
        assert c.profit_factor == Decimal("0.05")
        assert c.margin_type == "ISOLATED"
        assert c.max_rungs_per_symbol == 3

    def test_min_quote_order_qty(self):
        c = ElphabaConfig(quote_order_qty=Decimal("1"))
        c.normalize()
        assert c.quote_order_qty >= Decimal("5.0")

    def test_min_profit_factor(self):
        c = ElphabaConfig(profit_factor=Decimal("0.001"))
        c.normalize()
        assert c.profit_factor >= Decimal("0.03")

    def test_margin_type_forced_isolated(self):
        c = ElphabaConfig(margin_type="CROSS")
        c.normalize()
        assert c.margin_type == "ISOLATED"


    def test_as_json(self):
        c = ElphabaConfig()
        c.normalize()
        j = c.as_json()
        assert j["mode"] == "LIVE"
        assert j["execution_mode"] == "MARGIN_SHORT"
        assert j["margin_type"] == "ISOLATED"

    def test_symbol_normalization(self):
        c = ElphabaConfig(symbol="xrpusdt")
        c.normalize()
        assert c.symbol == "XRPUSDT"


# ── Runner Tests ─────────────────────────────────────────────────

def _make_runner():
    log = MagicMock()
    event_log = MagicMock()
    r = ElphabaRunner(log, event_log)
    r.set_credentials("test_key", "test_secret")
    return r


class TestElphabaRunner:
    def test_bot_type(self):
        r = _make_runner()
        assert r.BOT_TYPE == "elphaba"

    def test_bot_key(self):
        r = _make_runner()
        assert r._bot_key() == "elphaba:XRPUSDT"

    def test_loop_log_summary(self):
        r = _make_runner()
        summary = r._loop_log_summary({"decision": "SHORT_AND_COVER", "symbol": "XRPUSDT"})
        assert "elphaba" in summary
        assert "SHORT_AND_COVER" in summary

    def test_apply_config(self):
        r = _make_runner()
        cfg = ElphabaConfig(symbol="BTCUSDT", quote_order_qty=Decimal("10"))
        r.apply_config(cfg)
        assert r.config.symbol == "BTCUSDT"
        assert r.config.quote_order_qty == Decimal("10")

    def test_fuse_tripped(self):
        r = _make_runner()
        with patch("runtime.bot.elphaba.get_api_fuse") as mock_fuse:
            fuse = MagicMock()
            fuse.is_tripped.return_value = True
            fuse.remaining_cooldown_sec.return_value = 42.0
            mock_fuse.return_value = fuse
            result = asyncio.get_event_loop().run_until_complete(r.run_once())
            assert result["decision"] == "FUSE_TRIPPED"



# ── Margin Logic Tests ───────────────────────────────────────────

class TestElphabaMarginLogic:
    """Test the inverse gate logic and margin helpers."""

    def test_tp_price_calculation(self):
        """Take-profit should be BELOW entry (buying back cheaper)."""
        short_price = Decimal("2.50")
        profit_factor = Decimal("0.05")
        tp_price = short_price * (Decimal("1") - profit_factor)
        assert tp_price == Decimal("2.375")
        assert tp_price < short_price

    def test_dca_threshold_rises(self):
        """DCA threshold should be ABOVE anchor (shorting higher into pump)."""
        anchor_buy_price = Decimal("2.375")  # TP price
        profit_factor = Decimal("0.05")
        margin_rise = Decimal("0.03")
        implied_entry = anchor_buy_price / (Decimal("1") - profit_factor)
        threshold = implied_entry * (Decimal("1") + profit_factor + margin_rise)
        assert threshold > implied_entry
        assert threshold > Decimal("2.50")

    def test_liquidation_math(self):
        """At 1x leverage, liquidation should be at ~+81.8% price rise."""
        collateral = Decimal("18")  # 3 rungs × 6 USDT
        entry_price = Decimal("2.40")
        qty = collateral / entry_price
        total_assets = collateral + qty * entry_price  # 2 × collateral
        liq_ml = Decimal("1.1")
        liq_price = total_assets / (liq_ml * qty)
        pct_rise = (liq_price - entry_price) / entry_price
        assert pct_rise > Decimal("0.80")
        assert pct_rise < Decimal("0.83")
