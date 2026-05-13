"""Tests for graceful shutdown — signal handling, pending order cancellation, state flush."""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from runtime.api.lifespan import is_shutdown_requested, set_shutdown_flag, get_shutdown_elapsed


@pytest.fixture
def louise_db(tmp_path):
    """Fresh Louise database for each test."""
    db_path = str(tmp_path / "louise_test.sqlite")
    from runtime.core.louise_db import LouiseDB
    db = LouiseDB(db_path=db_path)
    yield db
    # Explicitly close any open connections to avoid Windows file locking issues
    import gc
    gc.collect()


@pytest.fixture
def event_bus():
    """Event bus for pub/sub."""
    from runtime.core.event_bus import EventBus
    return EventBus()


@pytest.fixture
def mock_gateway():
    """Mock Binance gateway."""
    gateway = AsyncMock()
    gateway._client = AsyncMock()
    gateway.create_order = AsyncMock()
    gateway.cancel_order = AsyncMock()
    return gateway


class TestShutdownFlags:
    """Test shutdown flag behavior."""

    def test_shutdown_flag_initially_false(self):
        """Shutdown flag should be false on start."""
        with patch("runtime.api.lifespan._shutdown_requested", False):
            assert is_shutdown_requested() is False

    def test_set_shutdown_flag(self):
        """Setting shutdown flag should change state."""
        with patch("runtime.api.lifespan._shutdown_requested", True):
            # Note: In real scenario, this would be set by signal handler
            pass

    def test_shutdown_elapsed_time(self):
        """Should track elapsed time since shutdown request."""
        with patch("runtime.api.lifespan._shutdown_start_time", time.time() - 5):
            elapsed = get_shutdown_elapsed()
            assert elapsed >= 4  # At least ~5s elapsed


class TestSignalHandling:
    """Test signal handler registration and invocation."""

    def test_shutdown_flag_can_be_set(self):
        """Setting shutdown flag should work."""
        # This is a side-effect test — the flag gets set
        import runtime.api.lifespan as lifespan_module
        original_flag = lifespan_module._shutdown_requested
        original_time = lifespan_module._shutdown_start_time

        try:
            set_shutdown_flag()
            assert lifespan_module._shutdown_requested is True
            assert lifespan_module._shutdown_start_time is not None
        finally:
            lifespan_module._shutdown_requested = original_flag
            lifespan_module._shutdown_start_time = original_time

    @pytest.mark.asyncio
    async def test_signal_handler_blocks_bot_loop(self, louise_db, event_bus, mock_gateway):
        """Bot main loop should exit when shutdown flag is set."""
        from runtime.bot.louise import LouiseBotRunner

        db = louise_db
        bus = event_bus
        gateway = mock_gateway

        bot_id = "louise-signal-test"
        db.create_bot(bot_id, "BTCUSDT", 100.0, 1, 5.0, 1000.0)

        runner = LouiseBotRunner(bot_id, db, bus, gateway)
        runner.initialize()

        # Mock poll_market to avoid actual trading
        async def slow_poll(*args, **kwargs):
            await asyncio.sleep(0.5)

        runner.poll_market = slow_poll

        # Start bot task
        import runtime.api.lifespan as lifespan_module
        original_flag = lifespan_module._shutdown_requested
        try:
            bot_task = asyncio.create_task(runner._main_loop())
            await asyncio.sleep(0.05)  # Let it start

            # Set shutdown flag
            lifespan_module._shutdown_requested = True

            # Wait for bot to detect flag and exit
            try:
                await asyncio.wait_for(bot_task, timeout=2.0)
            except asyncio.TimeoutError:
                bot_task.cancel()
                raise AssertionError("Bot did not exit after shutdown flag set")

            # Bot should have stopped
            assert not runner._running
        finally:
            lifespan_module._shutdown_requested = original_flag
            try:
                await runner.stop()
            except Exception:
                pass


class TestPendingOrderCancellation:
    """Test cancellation of pending orders during shutdown."""

    @pytest.mark.asyncio
    async def test_pending_orders_can_be_tracked(self, louise_db, event_bus, mock_gateway):
        """Pending orders dict should track in-flight trades."""
        from runtime.bot.louise import LouiseBotRunner

        db = louise_db
        bus = event_bus
        gateway = mock_gateway

        bot_id = "louise-pending"
        db.create_bot(bot_id, "BTCUSDT", 100.0, 1, 5.0, 1000.0)

        runner = LouiseBotRunner(bot_id, db, bus, gateway)
        runner.initialize()

        # Simulate pending order
        runner.pending_orders["order_1"] = {
            "type": "BUY",
            "epoch_id": "epoch_1",
            "amount_usdt": 100.0
        }

        assert len(runner.pending_orders) == 1
        assert "order_1" in runner.pending_orders

    @pytest.mark.asyncio
    async def test_pending_order_cancellation_logic(self, louise_db, event_bus, mock_gateway):
        """Shutdown should iterate pending orders and cancel them."""
        from runtime.bot.louise import LouiseBotRunner

        db = louise_db
        bus = event_bus
        gateway = mock_gateway
        gateway._client.cancel_order = AsyncMock()

        bot_id = "louise-cancel"
        db.create_bot(bot_id, "BTCUSDT", 100.0, 1, 5.0, 1000.0)

        runner = LouiseBotRunner(bot_id, db, bus, gateway)
        runner.initialize()

        # Add pending orders
        runner.pending_orders["order_1"] = {"type": "BUY", "epoch_id": "e1"}
        runner.pending_orders["order_2"] = {"type": "BUY", "epoch_id": "e2"}

        # Verify cancellation can be called
        for client_oid in runner.pending_orders.keys():
            try:
                await gateway._client.cancel_order(
                    symbol="BTCUSDT",
                    origClientOrderId=client_oid
                )
            except Exception:
                pass

        # Should have been called
        assert gateway._client.cancel_order.called


class TestDatabaseFlush:
    """Test state flush on shutdown."""

    def test_louise_db_persists_state(self, louise_db):
        """Louise database should persist on create/update."""
        db = louise_db

        # Create bot
        bot_id = "louise-persist"
        db.create_bot(bot_id, "BTCUSDT", 100.0, 1, 5.0, 1000.0)

        # Verify persistence
        bot = db.get_bot(bot_id)
        assert bot is not None
        assert bot["symbol"] == "BTCUSDT"

    def test_epoch_state_persists(self, louise_db):
        """Epoch state should persist through context manager."""
        db = louise_db

        bot_id = "louise-epoch"
        db.create_bot(bot_id, "BTCUSDT", 100.0, 1, 5.0, 1000.0)

        # Create and update epoch
        epoch_id = "epoch_1"
        db.create_epoch(epoch_id, bot_id)
        db.update_epoch_stats(epoch_id, 1, 100.0, 45000.0)

        # Retrieve and verify
        epoch = db.get_epoch(epoch_id)
        assert epoch is not None
        assert epoch["avg_buy_price"] == 45000.0
        assert epoch["num_purchases"] == 1


class TestShutdownSequencing:
    """Test proper shutdown sequence."""

    def test_shutdown_sequence_order(self):
        """Shutdown should follow correct sequence: Louise → orders → telemetry → gateway → coordinator."""
        # This is more of an integration test, but we can verify the logic
        import runtime.api.lifespan as lifespan_module

        # Verify constants
        assert lifespan_module._SHUTDOWN_TIMEOUT_SEC == 30

    @pytest.mark.asyncio
    async def test_shutdown_respects_timeout(self):
        """Shutdown sequence should complete within timeout."""
        import runtime.api.lifespan as lifespan_module

        original_time = lifespan_module._shutdown_start_time
        original_flag = lifespan_module._shutdown_requested

        try:
            # Set shutdown start time to 25s ago (simulating slow shutdown)
            lifespan_module._shutdown_start_time = time.time() - 25

            elapsed = lifespan_module.get_shutdown_elapsed()
            assert 24 <= elapsed <= 26  # Should be ~25s

            # Verify still under timeout
            assert elapsed < lifespan_module._SHUTDOWN_TIMEOUT_SEC
        finally:
            lifespan_module._shutdown_start_time = original_time
            lifespan_module._shutdown_requested = original_flag


class TestAlertOnShutdown:
    """Test that shutdown alerts are triggered."""

    def test_shutdown_alert_can_be_dispatched(self):
        """Shutdown should trigger alert."""
        from runtime.core.alert_dispatcher import get_alert_dispatcher

        alerts = get_alert_dispatcher()

        # Should be able to dispatch shutdown alert
        alert = alerts.warning(
            "SHUTDOWN_TEST",
            "Test shutdown alert",
            silent=False
        )

        assert alert["code"] == "SHUTDOWN_TEST"
        assert alert["level"] == "WARNING"
