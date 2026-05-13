"""Test suite for Louise WebSocket fill event handling."""

from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from runtime.bot.louise import LouiseBotRunner
from runtime.core.louise_db import LouiseDB


@pytest.fixture
def temp_db(tmp_path):
    """Temporary Louise DB for testing."""
    db_path = str(tmp_path / "louise_test.sqlite")
    return LouiseDB(db_path=db_path)


@pytest.fixture
def event_bus():
    """Mock event bus."""
    return MagicMock()


@pytest.fixture
def mock_gateway():
    """Mock gateway."""
    return MagicMock()


@pytest.fixture
def sample_bot(temp_db):
    """Create a sample bot with active epoch."""
    bot_id = "louise_btc_fill"
    temp_db.create_bot(
        bot_id=bot_id,
        symbol="BTCUSDT",
        buy_volume=10.0,
        poll_interval_seconds=60,
        target_profit_pct=5.0,
        daily_budget_usdt=500.0,
    )
    epoch_id = f"epoch_{bot_id}_1"
    temp_db.create_epoch(epoch_id, bot_id, "RUNNING")
    temp_db.update_epoch_stats(epoch_id, 0, 0, 0)
    return bot_id


class TestFillHandling:
    """Tests for WebSocket fill event processing."""

    def test_buy_fill_recorded_and_epoch_updated(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test BUY fill updates purchases and epoch stats."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        client_oid = f"l_{sample_bot}_123"
        epoch = temp_db.get_active_epoch(sample_bot)
        runner.pending_orders[client_oid] = {
            "type": "BUY",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
        }

        fill_event = {
            "c": client_oid,
            "X": "FILLED",
            "i": 123456,
            "z": "1.5",       # 1.5 BTC filled
            "Z": "75000",     # 75000 USDT spent
            "p": "50000",
        }

        with patch("runtime.bot.louise.get_budget_guard") as mock_bg:
            mock_bg.return_value.record_spend = MagicMock()
            runner._on_execution_report(fill_event)

        purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
        assert len(purchases) == 1
        assert purchases[0]["volume"] == 1.5
        assert purchases[0]["cost_usdt"] == 75000.0

        updated_epoch = temp_db.get_active_epoch(sample_bot)
        assert updated_epoch["num_purchases"] == 1
        assert abs(updated_epoch["total_cost"] - 75000.0) < 0.01
        assert abs(updated_epoch["avg_buy_price"] - 50000.0) < 0.01

    def test_sell_fill_closes_epoch(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test SELL fill closes epoch with profit/loss."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        epoch = temp_db.get_active_epoch(sample_bot)
        temp_db.add_purchase(
            "pur_1", sample_bot, epoch["epoch_id"], 50000.0, 1.5, 75000.0, "order_123", "FILLED"
        )
        temp_db.update_epoch_stats(epoch["epoch_id"], 1, 75000.0, 50000.0)

        client_oid = f"s_{sample_bot}_456"
        runner.pending_orders[client_oid] = {
            "type": "SELL",
            "epoch_id": epoch["epoch_id"],
            "status": "CLOSED_SUCCESSFUL",
            "current_price": Decimal("52000"),
            "final_value": Decimal("78000"),
            "profit_usdt": Decimal("3000"),
            "profit_pct": Decimal("4"),
        }

        fill_event = {"c": client_oid, "X": "FILLED", "i": 654321}
        runner._on_execution_report(fill_event)

        # Epoch closed → no active epoch for this bot
        assert temp_db.get_active_epoch(sample_bot) is None

    def test_two_buy_fills_accumulate(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test two separate BUY orders accumulate in epoch stats."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        epoch = temp_db.get_active_epoch(sample_bot)

        # First BUY
        oid1 = f"l_{sample_bot}_a"
        runner.pending_orders[oid1] = {"type": "BUY", "epoch_id": epoch["epoch_id"], "epoch": epoch}
        with patch("runtime.bot.louise.get_budget_guard"):
            runner._on_execution_report({
                "c": oid1, "X": "FILLED", "i": 1, "z": "0.5", "Z": "25000", "p": "50000",
            })

        # Refresh epoch for second buy
        epoch_after_1 = temp_db.get_active_epoch(sample_bot)
        oid2 = f"l_{sample_bot}_b"
        runner.pending_orders[oid2] = {"type": "BUY", "epoch_id": epoch_after_1["epoch_id"], "epoch": epoch_after_1}
        with patch("runtime.bot.louise.get_budget_guard"):
            runner._on_execution_report({
                "c": oid2, "X": "FILLED", "i": 2, "z": "1.0", "Z": "50000", "p": "50000",
            })

        purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
        assert len(purchases) == 2
        assert sum(p["volume"] for p in purchases) == 1.5
        assert sum(p["cost_usdt"] for p in purchases) == 75000.0

    def test_fill_for_unknown_order_ignored(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test fill for order not in pending_orders is ignored gracefully."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        fill_event = {
            "c": "unknown_client_oid",
            "X": "FILLED",
            "i": 999999,
            "z": "1.0",
            "Z": "50000",
        }

        runner._on_execution_report(fill_event)  # Should not raise

        epoch = temp_db.get_active_epoch(sample_bot)
        purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
        assert len(purchases) == 0

    def test_fill_rejection_handled(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test REJECTED status is ignored (only FILLED processed)."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        epoch = temp_db.get_active_epoch(sample_bot)
        client_oid = f"l_{sample_bot}_rej"
        runner.pending_orders[client_oid] = {
            "type": "BUY",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
        }

        fill_event = {"c": client_oid, "X": "REJECTED", "i": 333333}
        runner._on_execution_report(fill_event)

        # Order remains pending (will be cleaned up by cancellation logic, not fills)
        assert client_oid in runner.pending_orders
        # No purchase recorded
        purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
        assert len(purchases) == 0

    def test_slippage_recorded_at_actual_price(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that filled cost = actual cost from fill, accounting for slippage."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        epoch = temp_db.get_active_epoch(sample_bot)
        client_oid = f"l_{sample_bot}_slip"
        runner.pending_orders[client_oid] = {
            "type": "BUY",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
        }

        # 1.0 BTC filled at 51000 (slipped 2% above expected 50000)
        fill_event = {
            "c": client_oid,
            "X": "FILLED",
            "i": 444444,
            "z": "1.0",
            "Z": "51000",
            "p": "51000",
        }

        with patch("runtime.bot.louise.get_budget_guard"):
            runner._on_execution_report(fill_event)

        purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
        # price_at_buy = cost / volume = 51000 / 1.0 = 51000
        assert purchases[0]["price_at_buy"] == 51000.0
        assert purchases[0]["cost_usdt"] == 51000.0
