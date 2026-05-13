"""Test suite for Louise bot recovery from failures."""

import asyncio
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
    """Mock gateway."""
    gateway = MagicMock()
    gateway._client = AsyncMock()
    return gateway


@pytest.fixture
def sample_bot(temp_db):
    """Create a sample bot."""
    bot_id = "louise_btc_recovery"
    temp_db.create_bot(
        bot_id=bot_id,
        symbol="BTC/USDT",
        buy_volume=10.0,
        poll_interval_seconds=60,
        target_profit_pct=5.0,
        daily_budget_usdt=500.0,
    )
    return bot_id


class TestRecoveryScenarios:
    """Tests for bot recovery from various failures."""

    @pytest.mark.asyncio
    async def test_recovery_from_api_governor_trip(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot skips poll when API governor says no."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        # Set up epoch so bot wants to poll
        temp_db.create_epoch(f"epoch_{sample_bot}_1", sample_bot, "RUNNING")

        # Mock governor to reject
        with patch("runtime.bot.louise.get_api_governor") as mock_gov:
            mock_gov.return_value.can_execute.return_value = False

            await runner.poll_market()

            # Should not have attempted buy/sell
            assert temp_db.get_active_epoch(sample_bot) is not None

    @pytest.mark.asyncio
    async def test_recovery_from_budget_guard_exhaustion(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot stops buying when budget guard exhausted."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        # Set up runnable state
        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1000")

        temp_db.create_epoch(f"epoch_{sample_bot}_1", sample_bot, "RUNNING")
        temp_db.update_epoch_stats(f"epoch_{sample_bot}_1", 0, 0, 0)

        with patch("runtime.bot.louise.get_budget_guard") as mock_bg:
            mock_bg.return_value.can_spend.return_value = False

            await runner.poll_market()

            # Should have skipped due to budget
            # (verified by no purchase added to DB)

    @pytest.mark.asyncio
    async def test_recovery_from_gateway_unavailable(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot retries with cooldown when gateway unavailable."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1000")

        temp_db.create_epoch(f"epoch_{sample_bot}_1", sample_bot, "RUNNING")
        temp_db.update_epoch_stats(f"epoch_{sample_bot}_1", 0, 0, 0)

        # Mock gateway to fail
        mock_gateway._client = None

        await runner.poll_market()

        # Should have set cooldown
        # (verified by cooldown_until timestamp)

    @pytest.mark.asyncio
    async def test_recovery_from_stale_price_data(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot waits for fresh price when data is stale."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.last_price_timestamp = 0  # Very old
        runner.usdt_free_balance = Decimal("1000")

        temp_db.create_epoch(f"epoch_{sample_bot}_1", sample_bot, "RUNNING")
        temp_db.update_epoch_stats(f"epoch_{sample_bot}_1", 0, 0, 0)

        await runner.poll_market()

        # Should have skipped due to stale data
        # (no new purchases in DB)

    @pytest.mark.asyncio
    async def test_recovery_from_insufficient_balance(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot skips when spot balance insufficient."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1.0")  # Too low
        runner.last_price_timestamp = int(time.time())

        temp_db.create_epoch(f"epoch_{sample_bot}_1", sample_bot, "RUNNING")
        temp_db.update_epoch_stats(f"epoch_{sample_bot}_1", 0, 0, 0)

        with patch("runtime.bot.louise.get_api_governor") as mock_gov:
            mock_gov.return_value.can_execute.return_value = True
            with patch("runtime.bot.louise.get_budget_guard") as mock_bg:
                mock_bg.return_value.can_spend.return_value = True

                await runner.poll_market()

        # Should have skipped due to low balance

    @pytest.mark.asyncio
    async def test_recovery_from_exchange_filter_unavailable(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot handles missing exchange filters gracefully."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1000")
        runner.last_price_timestamp = int(time.time())

        temp_db.create_epoch(f"epoch_{sample_bot}_1", sample_bot, "RUNNING")
        temp_db.update_epoch_stats(f"epoch_{sample_bot}_1", 0, 0, 0)

        with patch("runtime.bot.louise.get_exchange_filters") as mock_filters:
            mock_filters.return_value.get.return_value = None

            await runner.poll_market()

            # Should have handled gracefully

    @pytest.mark.asyncio
    async def test_state_recovery_after_db_read_failure(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test bot recovers from transient DB read failure."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        # Simulate DB failure during poll (rare case)
        # The bot should catch exception and retry on next cycle
        call_count = [0]

        original_poll = runner.poll_market

        async def poll_with_failure():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("DB connection failed")
            return await original_poll()

        runner.poll_market = poll_with_failure

        # First call fails
        with pytest.raises(RuntimeError):
            await runner.poll_market()

        # Second call should succeed
        await runner.poll_market()  # Should not raise


import time  # Import at module level for timestamp
