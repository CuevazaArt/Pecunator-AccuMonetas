"""Test suite for AntiLouise bot — margin SHORT strategy."""

import time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from runtime.bot.anti_louise import AntiLouiseBotRunner
from runtime.core.louise_db import LouiseDB


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def temp_db(tmp_path):
    return LouiseDB(db_path=str(tmp_path / "anti_louise_test.sqlite"))


@pytest.fixture
def event_bus():
    return MagicMock()


@pytest.fixture
def mock_gateway():
    gw = MagicMock()
    gw._client = AsyncMock()
    return gw


@pytest.fixture
def sample_bot(temp_db):
    bot_id = "anti_btc_test"
    temp_db.create_bot(
        bot_id=bot_id,
        symbol="BTCUSDT",
        buy_volume=100.0,
        poll_interval_seconds=60,
        target_profit_pct=5.0,
        daily_budget_usdt=2000.0,
        status="RUNNING",
        bot_type="anti_louise",
    )
    return bot_id


# ── Helpers ───────────────────────────────────────────────────────────

def _patch_guards(gov=True, fuse=False, bg=True):
    """Returns a context manager tuple for the common guard mocks."""
    return (
        patch("runtime.bot.anti_louise.get_api_governor",
              return_value=MagicMock(can_execute=MagicMock(return_value=gov))),
        patch("runtime.bot.anti_louise.get_api_fuse",
              return_value=MagicMock(is_tripped=MagicMock(return_value=fuse))),
        patch("runtime.bot.anti_louise.get_budget_guard",
              return_value=MagicMock(can_spend=MagicMock(return_value=bg),
                                     record_spend=MagicMock())),
        patch("runtime.bot.anti_louise.get_exchange_filters",
              return_value=MagicMock(get=MagicMock(return_value=None))),
        patch("runtime.bot.anti_louise.get_alert_dispatcher",
              return_value=MagicMock()),
    )


# ── Fill handling ─────────────────────────────────────────────────────

class TestAntiLouiseFillHandling:

    def test_short_open_fill_recorded(self, sample_bot, temp_db, event_bus, mock_gateway):
        """SHORT_OPEN fill must record purchase and update epoch stats."""
        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        epoch_id = f"epoch_{sample_bot}_1"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        temp_db.update_epoch_stats(epoch_id, 0, 0.0, 0.0)
        runner.active_epoch = temp_db.get_active_epoch(sample_bot)
        epoch = runner.active_epoch

        client_oid = f"al_{sample_bot}_111"
        runner.pending_orders[client_oid] = {
            "type": "SHORT_OPEN",
            "epoch_id": epoch_id,
            "epoch": epoch,
        }

        # 0.002 BTC shorted at 50 000 → received 100 USDT
        fill = {"c": client_oid, "X": "FILLED", "i": "ord1",
                "z": "0.002", "Z": "100", "p": "50000"}

        with patch("runtime.bot.anti_louise.get_budget_guard") as mock_bg:
            mock_bg.return_value.record_spend = MagicMock()
            runner._on_execution_report(fill)

        purchases = temp_db.get_purchases_by_epoch(epoch_id)
        assert len(purchases) == 1
        assert abs(purchases[0]["price_at_buy"] - 50000.0) < 0.01
        assert abs(purchases[0]["cost_usdt"] - 100.0) < 0.01

        updated = temp_db.get_active_epoch(sample_bot)
        assert updated["num_purchases"] == 1
        assert abs(updated["total_cost"] - 100.0) < 0.01
        assert abs(updated["avg_buy_price"] - 50000.0) < 0.01

    def test_short_open_updates_last_short_price(self, sample_bot, temp_db, event_bus, mock_gateway):
        """last_short_price must be updated to actual fill price."""
        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()
        assert runner.last_short_price == Decimal("0")

        epoch_id = f"epoch_{sample_bot}_lsp"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        temp_db.update_epoch_stats(epoch_id, 0, 0.0, 0.0)
        runner.active_epoch = temp_db.get_active_epoch(sample_bot)

        client_oid = f"al_{sample_bot}_lsp"
        runner.pending_orders[client_oid] = {
            "type": "SHORT_OPEN",
            "epoch_id": epoch_id,
            "epoch": runner.active_epoch,
        }

        fill = {"c": client_oid, "X": "FILLED", "i": "ord2",
                "z": "0.002", "Z": "100", "p": "50000"}

        with patch("runtime.bot.anti_louise.get_budget_guard") as mock_bg:
            mock_bg.return_value.record_spend = MagicMock()
            runner._on_execution_report(fill)

        assert runner.last_short_price == Decimal("50000")

    def test_cover_fill_closes_epoch(self, sample_bot, temp_db, event_bus, mock_gateway):
        """SHORT_COVER fill must close the epoch."""
        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        epoch_id = f"epoch_{sample_bot}_cov"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        temp_db.update_epoch_stats(epoch_id, 1, 100.0, 50000.0)
        runner.active_epoch = temp_db.get_active_epoch(sample_bot)

        client_oid = f"alc_{sample_bot}_222"
        runner.pending_orders[client_oid] = {
            "type": "SHORT_COVER",
            "epoch_id": epoch_id,
            "status": "CLOSED_SUCCESSFUL",
            "current_price": Decimal("47500"),
            "final_value": Decimal("95"),
            "profit_usdt": Decimal("5"),
            "profit_pct": Decimal("5.0"),
        }

        fill = {"c": client_oid, "X": "FILLED", "i": "ord3", "z": "0.002", "Z": "95"}
        runner._on_execution_report(fill)

        assert temp_db.get_active_epoch(sample_bot) is None

    def test_unknown_order_ignored(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Fill for unknown client_oid must not raise or modify DB."""
        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner._on_execution_report({
            "c": "ghost_order", "X": "FILLED", "i": "999", "z": "1.0", "Z": "50000"
        })  # must not raise

    def test_rejected_status_ignored(self, sample_bot, temp_db, event_bus, mock_gateway):
        """REJECTED fills must leave pending_orders intact and not record purchase."""
        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        epoch_id = f"epoch_{sample_bot}_rej"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        temp_db.update_epoch_stats(epoch_id, 0, 0.0, 0.0)
        runner.active_epoch = temp_db.get_active_epoch(sample_bot)

        oid = f"al_{sample_bot}_rej"
        runner.pending_orders[oid] = {
            "type": "SHORT_OPEN",
            "epoch_id": epoch_id,
            "epoch": runner.active_epoch,
        }

        runner._on_execution_report({"c": oid, "X": "REJECTED", "i": "0"})

        assert oid in runner.pending_orders
        assert len(temp_db.get_purchases_by_epoch(epoch_id)) == 0


# ── Entry gate (poll_market) ──────────────────────────────────────────

class TestAntiLouiseEntryGate:

    @pytest.mark.asyncio
    async def test_short_blocked_below_last_price(self, sample_bot, temp_db, event_bus, mock_gateway):
        """No new short when current price <= last_short_price (price not rising)."""
        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("50000")
        runner.last_short_price = Decimal("50000")  # same → should not short
        runner.usdt_free_balance = Decimal("2000")
        runner.last_price_timestamp = int(time.time())

        epoch_id = f"epoch_{sample_bot}_gate1"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        temp_db.update_epoch_stats(epoch_id, 1, 100.0, 50000.0)
        runner.active_epoch = temp_db.get_active_epoch(sample_bot)

        short_called = []

        async def track_short(*args, **kwargs):
            short_called.append(True)

        runner._execute_short_open = track_short

        gov_p, fuse_p, bg_p, filt_p, alert_p = _patch_guards()
        with gov_p, fuse_p, bg_p, filt_p, alert_p:
            await runner.poll_market()

        assert len(short_called) == 0

    @pytest.mark.asyncio
    async def test_short_allowed_above_last_price(self, sample_bot, temp_db, event_bus, mock_gateway):
        """New short opens when price rises strictly above last_short_price."""
        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        runner.current_price = Decimal("51000")   # higher than last short
        runner.last_short_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("2000")
        runner.last_price_timestamp = int(time.time())

        epoch_id = f"epoch_{sample_bot}_gate2"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        temp_db.update_epoch_stats(epoch_id, 1, 100.0, 50000.0)
        runner.active_epoch = temp_db.get_active_epoch(sample_bot)

        short_called = []

        async def track_short(*args, **kwargs):
            short_called.append(True)

        runner._execute_short_open = track_short

        gov_p, fuse_p, bg_p, filt_p, alert_p = _patch_guards()
        with gov_p, fuse_p, bg_p, filt_p, alert_p:
            await runner.poll_market()

        assert len(short_called) == 1

    @pytest.mark.asyncio
    async def test_cover_triggered_on_take_profit(self, sample_bot, temp_db, event_bus, mock_gateway):
        """Cover (exit) executes when profit_pct >= target_profit_pct."""
        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        # avg_short=50000, current=47000 → profit = (50000-47000)/50000 * 100 = 6% > 5% target
        runner.current_price = Decimal("47000")
        runner.last_short_price = Decimal("50000")
        runner.usdt_free_balance = Decimal("2000")
        runner.last_price_timestamp = int(time.time())

        epoch_id = f"epoch_{sample_bot}_tp"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        # avg_short=50000, total_received=100 USDT (0.002 BTC shorted)
        temp_db.update_epoch_stats(epoch_id, 1, 100.0, 50000.0)
        runner.active_epoch = temp_db.get_active_epoch(sample_bot)

        cover_called = []

        async def track_cover(*args, **kwargs):
            cover_called.append(True)

        runner._execute_cover = track_cover

        gov_p, fuse_p, bg_p, filt_p, alert_p = _patch_guards()
        with gov_p, fuse_p, bg_p, filt_p, alert_p:
            await runner.poll_market()

        assert len(cover_called) == 1


# ── P&L calculation ───────────────────────────────────────────────────

class TestAntiLouisePnL:

    def test_pnl_positive_when_price_falls(self):
        """Verify P&L formula: profit when price drops below avg short."""
        avg_short = Decimal("50000")
        total_received = Decimal("200")   # 0.004 BTC shorted at avg 50000
        current_price = Decimal("48000")  # price fell

        total_volume = total_received / avg_short
        current_exposure = total_volume * current_price
        profit_usdt = total_received - current_exposure
        profit_pct = (profit_usdt / total_received) * Decimal("100")

        assert profit_usdt > 0
        assert profit_pct > 0
        assert abs(float(profit_pct) - 4.0) < 0.01  # (50000-48000)/50000 * 100

    def test_pnl_negative_when_price_rises(self):
        """Verify P&L formula: loss when price rises above avg short (float loss)."""
        avg_short = Decimal("50000")
        total_received = Decimal("200")
        current_price = Decimal("52000")  # price rose — losing

        total_volume = total_received / avg_short
        current_exposure = total_volume * current_price
        profit_usdt = total_received - current_exposure
        profit_pct = (profit_usdt / total_received) * Decimal("100")

        assert profit_usdt < 0
        assert profit_pct < 0
        assert abs(float(profit_pct) - (-4.0)) < 0.01

    def test_pnl_zero_at_breakeven(self):
        """P&L is zero when current price == avg short price."""
        avg_short = Decimal("50000")
        total_received = Decimal("200")
        current_price = Decimal("50000")

        total_volume = total_received / avg_short
        current_exposure = total_volume * current_price
        profit_usdt = total_received - current_exposure
        assert abs(float(profit_usdt)) < 0.0001


# ── Crash recovery ────────────────────────────────────────────────────

class TestAntiLouiseCrashRecovery:

    def test_last_short_price_restored_from_db(self, sample_bot, temp_db, event_bus, mock_gateway):
        """On initialize, last_short_price is loaded from last DB purchase."""
        epoch_id = f"epoch_{sample_bot}_crash"
        temp_db.create_epoch(epoch_id, sample_bot, "RUNNING")
        temp_db.update_epoch_stats(epoch_id, 1, 100.0, 51000.0)
        temp_db.add_purchase(
            "pur_crash_1", sample_bot, epoch_id,
            51000.0, 0.00196, 100.0, "ord_crash", "FILLED"
        )

        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        assert runner.last_short_price == Decimal("51000.0")

    def test_no_active_epoch_starts_fresh(self, sample_bot, temp_db, event_bus, mock_gateway):
        """With no active epoch, last_short_price stays Decimal('0') on init."""
        runner = AntiLouiseBotRunner(sample_bot, temp_db, event_bus, mock_gateway)
        runner.initialize()

        assert runner.active_epoch is None
        assert runner.last_short_price == Decimal("0")
