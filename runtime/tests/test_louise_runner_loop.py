"""Test suite for LouiseBotRunner main loop execution."""

import asyncio
import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from runtime.bot.louise import LouiseBotRunner
from runtime.core.louise_db import LouiseDB
from runtime.core.event_bus import EventBus


@pytest.fixture
def temp_db(tmp_path):
    """Temporary Louise DB for testing."""
    db_path = str(tmp_path / "louise_test.sqlite")
    return LouiseDB(db_path=db_path)


@pytest.fixture
def event_bus():
    """Mock event bus."""
    return MagicMock(spec=EventBus)


@pytest.fixture
def mock_gateway():
    """Mock gateway with AsyncMock client."""
    gateway = MagicMock()
    gateway._client = AsyncMock()
    return gateway


@pytest.fixture
def sample_bot(temp_db):
    """Create a sample bot in DB."""
    bot_id = "louise_btc_test"
    temp_db.create_bot(
        bot_id=bot_id,
        symbol="BTC/USDT",
        buy_volume=10.0,
        poll_interval_seconds=1,
        target_profit_pct=5.0,
        daily_budget_usdt=500.0,
        subaccount="bluechip",
        status="RUNNING",
        max_position_size_usdt=5000.0,
        max_purchases_per_epoch=20,
    )
    return bot_id


class TestRunnerMainLoop:
    """Tests for runner main loop execution."""

    @pytest.mark.asyncio
    async def test_runner_cycles_at_interval(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner cycles at configured poll_interval_seconds."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        # Mock poll_market to track calls
        poll_count = []
        original_poll = runner.poll_market

        async def mock_poll(*args, **kwargs):
            poll_count.append(time.time())
            await original_poll(*args, **kwargs)

        runner.poll_market = mock_poll

        # Run for 3 seconds with 1-second interval
        task = asyncio.create_task(runner._main_loop())
        await asyncio.sleep(3.5)
        runner._running = False

        await asyncio.sleep(0.5)  # Let task finish

        # Should have ~3 cycles (first immediate, then 2 more)
        assert len(poll_count) >= 2, f"Expected at least 2 polls, got {len(poll_count)}"

    @pytest.mark.asyncio
    async def test_runner_stops_on_shutdown_flag(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner stops when shutdown flag is set."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        with patch("runtime.api.lifespan.is_shutdown_requested", return_value=False):
            task = asyncio.create_task(runner._main_loop())
            await asyncio.sleep(0.5)

            # Set shutdown flag
            with patch("runtime.api.lifespan.is_shutdown_requested", return_value=True):
                runner._running = False
                await asyncio.sleep(0.5)

        # Task should complete without error
        assert task.done()

    @pytest.mark.asyncio
    async def test_runner_handles_cancellation(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner handles CancelledError gracefully."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        task = asyncio.create_task(runner._main_loop())
        await asyncio.sleep(0.2)

        # Cancel the task
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_runner_continues_after_poll_error(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner retries after error in poll_market."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        poll_count = []
        original_poll = runner.poll_market
        fail_once = [True]

        async def mock_poll_with_error(*args, **kwargs):
            poll_count.append(time.time())
            if fail_once[0]:
                fail_once[0] = False
                raise RuntimeError("Simulated poll error")
            await original_poll(*args, **kwargs)

        runner.poll_market = mock_poll_with_error

        task = asyncio.create_task(runner._main_loop())
        await asyncio.sleep(2.5)  # 2+ cycles with 1s interval
        runner._running = False

        await asyncio.sleep(0.5)

        # Should have retried even after error
        assert len(poll_count) >= 2, f"Expected at least 2 polls despite error, got {len(poll_count)}"

    @pytest.mark.asyncio
    async def test_runner_preserves_state_between_cycles(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner state (price, balance) persists between cycles."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        # Set initial state
        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1000")

        # Simulate a cycle
        await runner.poll_market()

        # State should persist
        assert runner.current_price == Decimal("50000")
        assert runner.usdt_free_balance == Decimal("1000")

    @pytest.mark.asyncio
    async def test_runner_respects_running_flag(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner respects _running flag for start/stop."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        assert runner._running is False
        await runner.start()
        assert runner._running is True
        assert runner._task is not None

        # Give task time to run
        await asyncio.sleep(0.2)

        # Task should still be running
        assert not runner._task.done()
