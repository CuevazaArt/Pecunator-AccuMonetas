"""Test suite for Louise bot recovery from failures."""

import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
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
    """Mock gateway with async client."""
    gateway = MagicMock()
    gateway._client = AsyncMock()
    return gateway


@pytest.fixture
def sample_bot(temp_db):
    """Create a sample bot in RUNNING status (poll_market requires it)."""
    bot_id = "louise_btc_recovery"
    temp_db.create_bot(
        bot_id=bot_id,
        symbol="BTCUSDT",
        buy_volume=10.0,
        poll_interval_seconds=60,
        target_profit_pct=5.0,
        daily_budget_usdt=500.0,
        status="RUNNING",
    )
    return bot_id


class TestRecoveryScenarios:
    """Tests for bot recovery from various failures."""

    @pytest.mark.asyncio
    async def test_recovery_from_api_governor_trip(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot skips poll when API governor says no."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        # Set runnable state so we reach the governor check
        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1000")
        runner.last_price_timestamp = int(time.time())

        with patch("runtime.bot.louise.get_api_governor") as mock_gov:
            mock_gov.return_value.can_execute.return_value = False
            with patch("runtime.bot.louise.get_api_fuse") as mock_fuse:
                mock_fuse.return_value.is_tripped.return_value = False

                await runner.poll_market()

        # Governor blocked → no epoch created (poll exited before creation)
        assert temp_db.get_active_epoch(sample_bot) is None

    @pytest.mark.asyncio
    async def test_recovery_from_api_fuse_tripped(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot skips poll when API fuse is tripped."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1000")
        runner.last_price_timestamp = int(time.time())

        with patch("runtime.bot.louise.get_api_fuse") as mock_fuse:
            mock_fuse.return_value.is_tripped.return_value = True

            await runner.poll_market()

        # Fuse blocked → no epoch
        assert temp_db.get_active_epoch(sample_bot) is None

    @pytest.mark.asyncio
    async def test_recovery_from_budget_guard_exhaustion(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot stops buying when budget guard exhausted."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1000")
        runner.last_price_timestamp = int(time.time())

        with patch("runtime.bot.louise.get_api_governor") as mock_gov:
            mock_gov.return_value.can_execute.return_value = True
            with patch("runtime.bot.louise.get_api_fuse") as mock_fuse:
                mock_fuse.return_value.is_tripped.return_value = False
                with patch("runtime.bot.louise.get_budget_guard") as mock_bg:
                    mock_bg.return_value.can_spend.return_value = False
                    with patch("runtime.bot.louise.get_exchange_filters") as mock_filt:
                        mock_filt.return_value.get.return_value = None

                        await runner.poll_market()

        # Budget blocked → epoch may exist but no purchase
        epoch = temp_db.get_active_epoch(sample_bot)
        if epoch:
            purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
            assert len(purchases) == 0

    @pytest.mark.asyncio
    async def test_recovery_from_stale_price_data(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot waits for fresh price when data is stale."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.last_price_timestamp = 0  # Ancient
        runner.usdt_free_balance = Decimal("1000")

        await runner.poll_market()

        # Stale → no epoch
        assert temp_db.get_active_epoch(sample_bot) is None

    @pytest.mark.asyncio
    async def test_recovery_from_insufficient_balance(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot skips when spot balance insufficient."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1.0")  # Below min
        runner.last_price_timestamp = int(time.time())

        await runner.poll_market()

        # Insufficient balance → no epoch
        assert temp_db.get_active_epoch(sample_bot) is None

    @pytest.mark.asyncio
    async def test_buy_blocked_when_price_not_below_last_purchase(
        self, sample_bot, temp_db, event_bus, mock_gateway
    ):
        """Price must be strictly below last_purchase_price to trigger a buy.
        When price == last_purchase_price the bot should skip."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.last_purchase_price = Decimal("50000")  # same price → no buy
        runner.usdt_free_balance = Decimal("1000")
        runner.last_price_timestamp = int(time.time())

        epoch_id = f"epoch_{sample_bot}_same"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        temp_db.update_epoch_stats(epoch_id, 1, 50.0, 50000.0)
        runner.active_epoch = temp_db.get_active_epoch(sample_bot)

        buy_called = []
        original_buy = runner._execute_buy

        async def track_buy(*args, **kwargs):
            buy_called.append(True)

        runner._execute_buy = track_buy

        with patch("runtime.bot.louise.get_api_governor") as mock_gov:
            mock_gov.return_value.can_execute.return_value = True
            with patch("runtime.bot.louise.get_api_fuse") as mock_fuse:
                mock_fuse.return_value.is_tripped.return_value = False
                with patch("runtime.bot.louise.get_budget_guard") as mock_bg:
                    mock_bg.return_value.can_spend.return_value = True
                    with patch("runtime.bot.louise.get_exchange_filters") as mock_filt:
                        mock_filt.return_value.get.return_value = None

                        await runner.poll_market()

        assert len(buy_called) == 0, "Buy should not execute when price == last_purchase_price"

    @pytest.mark.asyncio
    async def test_buy_allowed_when_price_below_last_purchase(
        self, sample_bot, temp_db, event_bus, mock_gateway
    ):
        """When current price is strictly below last_purchase_price, the bot buys."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("49000")   # lower than last buy
        runner.last_purchase_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1000")
        runner.last_price_timestamp = int(time.time())

        epoch_id = f"epoch_{sample_bot}_lower"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        temp_db.update_epoch_stats(epoch_id, 1, 50.0, 50000.0)
        runner.active_epoch = temp_db.get_active_epoch(sample_bot)

        buy_called = []

        async def track_buy(*args, **kwargs):
            buy_called.append(True)

        runner._execute_buy = track_buy

        with patch("runtime.bot.louise.get_api_governor") as mock_gov:
            mock_gov.return_value.can_execute.return_value = True
            with patch("runtime.bot.louise.get_api_fuse") as mock_fuse:
                mock_fuse.return_value.is_tripped.return_value = False
                with patch("runtime.bot.louise.get_budget_guard") as mock_bg:
                    mock_bg.return_value.can_spend.return_value = True
                    with patch("runtime.bot.louise.get_exchange_filters") as mock_filt:
                        mock_filt.return_value.get.return_value = None
                        with patch("runtime.bot.louise.get_alert_dispatcher"):

                            await runner.poll_market()

        assert len(buy_called) == 1, "Buy should execute when price < last_purchase_price"
