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
    """Create a sample bot in DB with very short poll interval."""
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

        poll_count = []

        async def mock_poll(*args, **kwargs):
            poll_count.append(time.time())

        runner.poll_market = mock_poll
        runner._running = True

        task = asyncio.create_task(runner._main_loop())
        await asyncio.sleep(2.5)  # Allow at least 2 cycles with 1s interval
        runner._running = False
        await asyncio.sleep(1.2)  # Let final sleep finish

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert len(poll_count) >= 2, f"Expected at least 2 polls, got {len(poll_count)}"

    @pytest.mark.asyncio
    async def test_runner_stops_on_shutdown_flag(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner stops when shutdown flag is set."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()
        runner._running = True

        with patch("runtime.api.lifespan.is_shutdown_requested", return_value=True):
            task = asyncio.create_task(runner._main_loop())
            # Should exit quickly because shutdown flag is set
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except asyncio.TimeoutError:
                runner._running = False
                task.cancel()
                pytest.fail("Loop did not exit when shutdown flag set")

        assert task.done()

    @pytest.mark.asyncio
    async def test_runner_handles_cancellation(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner exits cleanly when its task is cancelled."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()
        runner._running = True

        task = asyncio.create_task(runner._main_loop())
        await asyncio.sleep(0.2)

        task.cancel()
        # Loop catches CancelledError internally and exits gracefully (no propagation)
        try:
            await task
        except asyncio.CancelledError:
            pass  # Either behaviour is acceptable

        assert task.done()

    @pytest.mark.asyncio
    async def test_runner_continues_after_poll_error(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner retries after error in poll_market."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()
        runner._running = True

        poll_count = []
        fail_once = [True]

        async def mock_poll_with_error(*args, **kwargs):
            poll_count.append(time.time())
            if fail_once[0]:
                fail_once[0] = False
                raise RuntimeError("Simulated poll error")

        runner.poll_market = mock_poll_with_error

        task = asyncio.create_task(runner._main_loop())
        await asyncio.sleep(2.5)
        runner._running = False
        await asyncio.sleep(1.2)

        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        assert len(poll_count) >= 2, f"Expected at least 2 polls despite error, got {len(poll_count)}"

    @pytest.mark.asyncio
    async def test_runner_preserves_state_between_cycles(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner state (price, balance) survives a poll cycle that exits early.

        We use a tripped fuse so the poll returns before any state mutation, then
        verify the explicit state values are still present.
        """
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("1000")
        runner.last_price_timestamp = int(time.time())

        # Tripped fuse → poll exits early before any state mutation
        with patch("runtime.bot.louise.get_api_fuse") as mock_fuse:
            mock_fuse.return_value.is_tripped.return_value = True
            await runner.poll_market()

        assert runner.current_price == Decimal("50000")
        assert runner.usdt_free_balance == Decimal("1000")

    @pytest.mark.asyncio
    async def test_runner_start_sets_task(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Test that runner.start() sets _running=True and creates task."""
        runner = LouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        assert runner._running is False
        await runner.start()
        assert runner._running is True
        assert runner._task is not None

        # Allow loop to enter sleep
        await asyncio.sleep(0.1)

        # Clean shutdown
        runner._running = False
        if runner._task:
            runner._task.cancel()
            try:
                await runner._task
            except asyncio.CancelledError:
                pass
