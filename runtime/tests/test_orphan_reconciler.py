"""Tests for orphan order detection and reconciliation."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock

from runtime.tools.orphan_reconciler import OrphanReconciler, OrphanOrderMeta
from runtime.core.louise_db import LouiseDB


@pytest.fixture
def louise_db(tmp_path):
    """Fresh Louise database for each test."""
    db_path = str(tmp_path / "louise_test.sqlite")
    db = LouiseDB(db_path=db_path)
    yield db
    import gc
    gc.collect()


@pytest.fixture
def mock_gateway():
    """Mock Binance gateway with controllable order responses."""
    gateway = AsyncMock()
    gateway._client = AsyncMock()
    return gateway


class TestOrphanOrderMeta:
    """Test orphan metadata container."""

    def test_orphan_meta_to_dict(self):
        """Orphan metadata should serialize to dict."""
        orphan = OrphanOrderMeta(
            order_id="12345",
            symbol="BTCUSDT",
            side="BUY",
            quantity=Decimal("0.5"),
            price=Decimal("45000"),
            status="FILLED",
            time_ms=1620000000000,
        )

        data = orphan.to_dict()
        assert data["order_id"] == "12345"
        assert data["symbol"] == "BTCUSDT"
        assert data["side"] == "BUY"
        assert data["quantity"] == "0.5"
        assert data["price"] == "45000"
        assert data["status"] == "FILLED"


class TestOrphanScanning:
    """Test orphan detection logic."""

    @pytest.mark.asyncio
    async def test_scan_orphans_none(self, louise_db, mock_gateway):
        """When all Binance orders are in DB, should return no orphans."""
        # Setup: Create bot with epoch and purchase
        bot_id = "louise-orphan-test"
        louise_db.create_bot(bot_id, "BTCUSDT", 100.0, 1, 5.0, 1000.0)

        epoch_id = "epoch_orphan_1"
        louise_db.create_epoch(epoch_id, bot_id)
        louise_db.add_purchase(
            purchase_id="pur_1",
            bot_id=bot_id,
            epoch_id=epoch_id,
            price_at_buy=45000.0,
            volume=0.5,
            cost_usdt=22500.0,
            order_id="12345",
            status="FILLED",
        )

        # Mock gateway: return one order that matches purchase
        mock_gateway._client.get_all_orders = AsyncMock(
            return_value=[
                {
                    "orderId": 12345,
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "price": "45000",
                    "origQty": "0.5",
                    "executedQty": "0.5",
                    "status": "FILLED",
                    "time": 1620000000000,
                }
            ]
        )

        reconciler = OrphanReconciler(louise_db, mock_gateway)
        orphans = await reconciler.scan_orphans(symbol="BTCUSDT")

        assert len(orphans) == 0

    @pytest.mark.asyncio
    async def test_scan_orphans_found(self, louise_db, mock_gateway):
        """When Binance has orders not in DB, should return orphans."""
        # Setup: Create bot with one purchase
        bot_id = "louise-orphan-test"
        louise_db.create_bot(bot_id, "BTCUSDT", 100.0, 1, 5.0, 1000.0)

        epoch_id = "epoch_orphan_1"
        louise_db.create_epoch(epoch_id, bot_id)
        louise_db.add_purchase(
            purchase_id="pur_1",
            bot_id=bot_id,
            epoch_id=epoch_id,
            price_at_buy=45000.0,
            volume=0.5,
            cost_usdt=22500.0,
            order_id="12345",
            status="FILLED",
        )

        # Mock gateway: return two orders, one is orphan
        mock_gateway._client.get_all_orders = AsyncMock(
            return_value=[
                {
                    "orderId": 12345,
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "price": "45000",
                    "origQty": "0.5",
                    "executedQty": "0.5",
                    "status": "FILLED",
                    "time": 1620000000000,
                },
                {
                    "orderId": 99999,
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "price": "44500",
                    "origQty": "0.6",
                    "executedQty": "0.6",
                    "status": "FILLED",
                    "time": 1620000001000,
                },
            ]
        )

        reconciler = OrphanReconciler(louise_db, mock_gateway)
        orphans = await reconciler.scan_orphans(symbol="BTCUSDT")

        assert len(orphans) == 1
        assert orphans[0].order_id == "99999"
        assert orphans[0].quantity == Decimal("0.6")


class TestOrphanAdoption:
    """Test adopting orphaned orders into DB."""

    @pytest.mark.asyncio
    async def test_adopt_orphan(self, louise_db, mock_gateway):
        """Adopting an orphan should insert purchase and update epoch stats."""
        # Setup: Create bot with empty epoch
        bot_id = "louise-adopt-test"
        louise_db.create_bot(bot_id, "BTCUSDT", 100.0, 1, 5.0, 1000.0)

        epoch_id = "epoch_adopt_1"
        louise_db.create_epoch(epoch_id, bot_id)
        louise_db.update_epoch_stats(epoch_id, 0, 0.0, 0.0)

        # Create orphan to adopt
        orphan = OrphanOrderMeta(
            order_id="99999",
            symbol="BTCUSDT",
            side="BUY",
            quantity=Decimal("0.5"),
            price=Decimal("44500"),
            status="FILLED",
            time_ms=1620000001000,
        )

        reconciler = OrphanReconciler(louise_db, mock_gateway)
        success = await reconciler.adopt_orphan(orphan, bot_id, epoch_id)

        assert success is True

        # Verify purchase was inserted
        purchases = louise_db.get_epoch_purchases(epoch_id)
        assert len(purchases) == 1
        assert purchases[0]["order_id"] == "99999"
        assert purchases[0]["volume"] == 0.5
        assert purchases[0]["price_at_buy"] == 44500.0

        # Verify epoch was updated
        epoch = louise_db.get_epoch(epoch_id)
        assert epoch["num_purchases"] == 1
        assert epoch["avg_buy_price"] == 44500.0

    @pytest.mark.asyncio
    async def test_adopt_nonexistent_epoch(self, louise_db, mock_gateway):
        """Adopting into non-existent epoch should fail."""
        orphan = OrphanOrderMeta(
            order_id="99999",
            symbol="BTCUSDT",
            side="BUY",
            quantity=Decimal("0.5"),
            price=Decimal("44500"),
            status="FILLED",
            time_ms=1620000001000,
        )

        reconciler = OrphanReconciler(louise_db, mock_gateway)
        success = await reconciler.adopt_orphan(orphan, "nonexistent_bot", "nonexistent_epoch")

        assert success is False


class TestOrphanCancellation:
    """Test cancelling orphaned orders on Binance."""

    @pytest.mark.asyncio
    async def test_cancel_open_order(self, louise_db, mock_gateway):
        """Cancelling an open orphan should call gateway cancel."""
        orphan = OrphanOrderMeta(
            order_id="99999",
            symbol="BTCUSDT",
            side="BUY",
            quantity=Decimal("0.5"),
            price=Decimal("44500"),
            status="NEW",
            time_ms=1620000001000,
        )

        mock_gateway._client.cancel_order = AsyncMock()

        reconciler = OrphanReconciler(louise_db, mock_gateway)
        success = await reconciler.cancel_orphan(orphan)

        assert success is True
        mock_gateway._client.cancel_order.assert_called_once_with(
            symbol="BTCUSDT",
            origClientOrderId="99999",
        )

    @pytest.mark.asyncio
    async def test_cancel_already_filled(self, louise_db, mock_gateway):
        """Cancelling a FILLED orphan should skip (already done)."""
        orphan = OrphanOrderMeta(
            order_id="99999",
            symbol="BTCUSDT",
            side="BUY",
            quantity=Decimal("0.5"),
            price=Decimal("44500"),
            status="FILLED",
            time_ms=1620000001000,
        )

        mock_gateway._client.cancel_order = AsyncMock()

        reconciler = OrphanReconciler(louise_db, mock_gateway)
        success = await reconciler.cancel_orphan(orphan)

        assert success is True
        mock_gateway._client.cancel_order.assert_not_called()
