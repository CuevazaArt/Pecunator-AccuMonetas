"""Tests for OrphanGuard — orphaned position detection."""
import asyncio
import pytest
from decimal import Decimal
from unittest.mock import MagicMock

from runtime.core.orphan_guard import OrphanGuard


def _mock_client(
    asset_free="0",
    borrowed="0",
    has_sell_limit=False,
    has_buy_limit=False,
    bot_tag="dorothy-test",
    elphaba_tag="elphaba-test",
):
    client = MagicMock()

    # Spot account
    client.get_account.return_value = {
        "balances": [
            {"asset": "XRP", "free": asset_free, "locked": "0"},
            {"asset": "USDT", "free": "100", "locked": "0"},
        ]
    }

    # Open orders (spot)
    spot_orders = []
    if has_sell_limit:
        spot_orders.append({
            "orderId": 12345,
            "side": "SELL",
            "type": "LIMIT",
            "clientOrderId": f"{bot_tag}-sell-9999",
            "price": "2.50",
            "origQty": "10",
        })
    client.get_open_orders.return_value = spot_orders

    # Isolated margin account
    client.get_isolated_margin_account.return_value = {
        "assets": [{
            "baseAsset": {"borrowed": borrowed, "interest": "0", "free": "0"},
            "quoteAsset": {"free": "20", "netAsset": "20"},
        }]
    }

    # Open margin orders
    margin_orders = []
    if has_buy_limit:
        margin_orders.append({
            "orderId": 67890,
            "side": "BUY",
            "type": "LIMIT",
            "clientOrderId": f"{elphaba_tag}-tp-9999",
            "price": "2.30",
            "origQty": "10",
        })
    client.get_open_margin_orders.return_value = margin_orders

    return client


def _mock_config():
    c = MagicMock()
    c.quote_order_qty = Decimal("6")
    return c


class TestDorothyOrphans:
    def test_no_orphan_when_no_asset(self):
        guard = OrphanGuard()
        client = _mock_client(asset_free="0")
        orphans = asyncio.get_event_loop().run_until_complete(
            guard.scan_dorothy_orphans(
                client, "XRPUSDT", "dorothy-test", _mock_config()
            )
        )
        assert len(orphans) == 0

    def test_no_orphan_when_sell_limit_exists(self):
        guard = OrphanGuard()
        client = _mock_client(asset_free="50", has_sell_limit=True)
        orphans = asyncio.get_event_loop().run_until_complete(
            guard.scan_dorothy_orphans(
                client, "XRPUSDT", "dorothy-test", _mock_config()
            )
        )
        assert len(orphans) == 0

    def test_orphan_detected_asset_without_sell(self):
        guard = OrphanGuard()
        client = _mock_client(asset_free="50", has_sell_limit=False)
        orphans = asyncio.get_event_loop().run_until_complete(
            guard.scan_dorothy_orphans(
                client, "XRPUSDT", "dorothy-test", _mock_config()
            )
        )
        assert len(orphans) == 1
        assert orphans[0]["type"] == "DOROTHY_ORPHAN"
        assert orphans[0]["missing"] == "SELL_LIMIT"


class TestElphabaOrphans:
    def test_no_orphan_when_no_debt(self):
        guard = OrphanGuard()
        client = _mock_client(borrowed="0")
        orphans = asyncio.get_event_loop().run_until_complete(
            guard.scan_elphaba_orphans(
                client, "XRPUSDT", "elphaba-test"
            )
        )
        assert len(orphans) == 0

    def test_no_orphan_when_buy_limit_exists(self):
        guard = OrphanGuard()
        client = _mock_client(borrowed="25", has_buy_limit=True)
        orphans = asyncio.get_event_loop().run_until_complete(
            guard.scan_elphaba_orphans(
                client, "XRPUSDT", "elphaba-test"
            )
        )
        assert len(orphans) == 0

    def test_orphan_detected_debt_without_cover(self):
        guard = OrphanGuard()
        client = _mock_client(borrowed="25", has_buy_limit=False)
        orphans = asyncio.get_event_loop().run_until_complete(
            guard.scan_elphaba_orphans(
                client, "XRPUSDT", "elphaba-test"
            )
        )
        assert len(orphans) == 1
        assert orphans[0]["type"] == "ELPHABA_ORPHAN"
        assert orphans[0]["missing"] == "BUY_LIMIT_COVER"
        assert orphans[0]["borrowed"] == "25"


class TestCombinedScan:
    def test_healthy_hub(self):
        guard = OrphanGuard()
        client = _mock_client(asset_free="0", borrowed="0")
        result = asyncio.get_event_loop().run_until_complete(
            guard.scan_all(
                client, "XRPUSDT", "dorothy-test", "elphaba-test", _mock_config()
            )
        )
        assert result["healthy"] is True
        assert result["orphans_found"] == 0

    def test_both_orphans_detected(self):
        guard = OrphanGuard()
        client = _mock_client(
            asset_free="50", has_sell_limit=False,
            borrowed="25", has_buy_limit=False,
        )
        result = asyncio.get_event_loop().run_until_complete(
            guard.scan_all(
                client, "XRPUSDT", "dorothy-test", "elphaba-test", _mock_config()
            )
        )
        assert result["healthy"] is False
        assert result["orphans_found"] == 2

    def test_scan_interval_respected(self):
        guard = OrphanGuard()
        # After a scan, needs_scan should return False
        client = _mock_client()
        asyncio.get_event_loop().run_until_complete(
            guard.scan_all(
                client, "XRPUSDT", "dorothy-test", "elphaba-test", _mock_config()
            )
        )
        assert guard.needs_scan() is False
