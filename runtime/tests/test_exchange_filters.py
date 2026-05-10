"""Tests for ExchangeFilterCache — LOT_SIZE / MIN_NOTIONAL universal validation."""

import asyncio
from decimal import Decimal

import pytest

from runtime.core.exchange_filters import (
    ExchangeFilterCache,
    SymbolFilters,
    get_exchange_filters,
)


# ── Fixture: realistic XRPUSDT filters from Binance ────────────────

XRPUSDT_INFO = {
    "filters": [
        {"filterType": "LOT_SIZE", "minQty": "0.10", "maxQty": "9000000.00", "stepSize": "0.10"},
        {"filterType": "PRICE_FILTER", "minPrice": "0.00010", "maxPrice": "10000.00", "tickSize": "0.00010"},
        {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
    ]
}

BIOUSDT_INFO = {
    "filters": [
        {"filterType": "LOT_SIZE", "minQty": "0.1", "maxQty": "90000000.00", "stepSize": "0.1"},
        {"filterType": "PRICE_FILTER", "minPrice": "0.0001", "maxPrice": "1000.00", "tickSize": "0.0001"},
        {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
    ]
}


class TestSymbolFilters:
    def test_parse_xrp_filters(self):
        sf = SymbolFilters("XRPUSDT", XRPUSDT_INFO)
        assert sf.qty_step == Decimal("0.10")
        assert sf.qty_decimals == 1
        assert sf.price_tick == Decimal("0.00010")
        assert sf.price_decimals == 4
        assert sf.min_notional == Decimal("5")
        assert sf.min_qty == Decimal("0.10")

    def test_quantize_qty(self):
        sf = SymbolFilters("XRPUSDT", XRPUSDT_INFO)
        assert sf.quantize_qty(Decimal("4.27")) == Decimal("4.2")
        assert sf.quantize_qty(Decimal("0.15")) == Decimal("0.1")
        assert sf.quantize_qty(Decimal("10.09")) == Decimal("10.0")

    def test_quantize_price(self):
        sf = SymbolFilters("XRPUSDT", XRPUSDT_INFO)
        assert sf.quantize_price(Decimal("1.47483")) == Decimal("1.4748")

    def test_validate_order_ok(self):
        sf = SymbolFilters("XRPUSDT", XRPUSDT_INFO)
        ok, reason = sf.validate_order(Decimal("4.2"), Decimal("1.4748"))
        assert ok is True
        assert reason == ""

    def test_validate_order_min_notional_fail(self):
        sf = SymbolFilters("XRPUSDT", XRPUSDT_INFO)
        ok, reason = sf.validate_order(Decimal("0.1"), Decimal("1.4748"))
        assert ok is False
        assert "minNotional" in reason

    def test_validate_order_min_qty_fail(self):
        sf = SymbolFilters("XRPUSDT", XRPUSDT_INFO)
        ok, reason = sf.validate_order(Decimal("0.01"), Decimal("100.0"))
        assert ok is False
        assert "minQty" in reason

    def test_bio_filters(self):
        sf = SymbolFilters("BIOUSDT", BIOUSDT_INFO)
        assert sf.qty_decimals == 1
        assert sf.price_decimals == 4
        qty = sf.quantize_qty(Decimal("109.6"))
        assert qty == Decimal("109.6")

    def test_empty_filters_uses_defaults(self):
        sf = SymbolFilters("UNKNOWN", {})
        assert sf.qty_decimals == 8
        assert sf.price_decimals == 2
        assert sf.min_notional == Decimal("5")


class TestExchangeFilterCache:
    def test_singleton(self):
        c1 = get_exchange_filters()
        c2 = get_exchange_filters()
        assert c1 is c2

    def test_get_before_load_returns_none(self):
        cache = ExchangeFilterCache()
        assert cache.get("XRPUSDT") is None

    @pytest.mark.asyncio
    async def test_ensure_loaded_with_mock_client(self):
        cache = ExchangeFilterCache()

        class MockClient:
            def get_symbol_info(self, symbol):
                return XRPUSDT_INFO

        sf = await cache.ensure_loaded("XRPUSDT", MockClient())
        assert sf.qty_decimals == 1
        assert sf.price_decimals == 4

        # Second call uses cache
        sf2 = cache.get("XRPUSDT")
        assert sf2 is sf

    def test_invalidate(self):
        cache = ExchangeFilterCache()
        # Manually insert
        sf = SymbolFilters("TESTUSDT", XRPUSDT_INFO)
        cache._cache["TESTUSDT"] = sf
        assert cache.get("TESTUSDT") is sf
        cache.invalidate("TESTUSDT")
        assert cache.get("TESTUSDT") is None
