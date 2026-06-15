"""Tests for hemisphere switches (louise_enabled / anti_louise_enabled)
and Lucky Strike fill classification (is_lucky_fill).
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from runtime.core.louise_db import LouiseDB
from runtime.bot.louise import LouiseBotRunner
from runtime.bot.anti_louise import AntiLouiseBotRunner


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db(tmp_path):
    return LouiseDB(db_path=str(tmp_path / "test.sqlite"))


@pytest.fixture
def event_bus():
    return MagicMock()


@pytest.fixture
def mock_gateway():
    return MagicMock()


def _make_bot(db: LouiseDB, bot_id: str, bot_type: str = "louise") -> str:
    db.create_bot(
        bot_id=bot_id,
        symbol="BTCUSDT",
        buy_volume=10.0,
        poll_interval_seconds=60,
        target_profit_pct=5.0,
        daily_budget_usdt=500.0,
    )
    if bot_type != "louise":
        import sqlite3
        conn = sqlite3.connect(db.db_path)
        conn.execute("UPDATE louise_bots SET bot_type=? WHERE bot_id=?", (bot_type, bot_id))
        conn.commit()
        conn.close()
    return bot_id


def _active_epoch(db: LouiseDB, bot_id: str) -> dict:
    epoch_id = f"epoch_{bot_id}_1"
    db.create_epoch(epoch_id, bot_id, "RUNNING")
    db.update_epoch_stats(epoch_id, 0, 0.0, 0.0)
    return db.get_active_epoch(bot_id)


# ── DB: Hemisphere column defaults ───────────────────────────────────────────

class TestHemisphereDefaults:
    def test_louise_enabled_default_true(self, temp_db):
        _make_bot(temp_db, "bot_001")
        bot = temp_db.get_bot("bot_001")
        assert bool(bot.get("louise_enabled", 1)) is True

    def test_anti_louise_enabled_default_false(self, temp_db):
        _make_bot(temp_db, "bot_002")
        bot = temp_db.get_bot("bot_002")
        assert bool(bot.get("anti_louise_enabled", 0)) is False

    def test_paired_bot_id_default_none(self, temp_db):
        _make_bot(temp_db, "bot_003")
        bot = temp_db.get_bot("bot_003")
        assert bot.get("paired_bot_id") is None


# ── DB: update_bot_hemispheres ────────────────────────────────────────────────

@pytest.mark.skip(reason="update_bot_hemispheres deprecated in v4.0 — AntiLouise removed")
class TestUpdateBotHemispheres:
    def test_enable_anti_louise(self, temp_db):
        _make_bot(temp_db, "bot_010")
        temp_db.update_bot_hemispheres("bot_010", anti_louise_enabled=True)
        bot = temp_db.get_bot("bot_010")
        assert bool(bot.get("anti_louise_enabled")) is True

    def test_disable_louise(self, temp_db):
        _make_bot(temp_db, "bot_011")
        temp_db.update_bot_hemispheres("bot_011", louise_enabled=False)
        bot = temp_db.get_bot("bot_011")
        assert bool(bot.get("louise_enabled")) is False

    def test_partial_update_does_not_reset_other(self, temp_db):
        """Updating only anti_louise_enabled must not touch louise_enabled."""
        _make_bot(temp_db, "bot_012")
        temp_db.update_bot_hemispheres("bot_012", louise_enabled=False)
        temp_db.update_bot_hemispheres("bot_012", anti_louise_enabled=True)
        bot = temp_db.get_bot("bot_012")
        assert bool(bot.get("louise_enabled")) is False
        assert bool(bot.get("anti_louise_enabled")) is True

    def test_both_enabled_simultaneously(self, temp_db):
        _make_bot(temp_db, "bot_013")
        temp_db.update_bot_hemispheres("bot_013", louise_enabled=True, anti_louise_enabled=True)
        bot = temp_db.get_bot("bot_013")
        assert bool(bot.get("louise_enabled")) is True
        assert bool(bot.get("anti_louise_enabled")) is True


# ── DB: update_bot_pair ───────────────────────────────────────────────────────

@pytest.mark.skip(reason="update_bot_pair deprecated in v4.0 — AntiLouise removed")
class TestPairBots:
    def test_pair_sets_paired_bot_id(self, temp_db):
        _make_bot(temp_db, "bot_a")
        _make_bot(temp_db, "bot_b")
        # DB method is unidirectional; router calls it twice for bidirectional
        temp_db.update_bot_pair("bot_a", "bot_b")
        a = temp_db.get_bot("bot_a")
        assert a.get("paired_bot_id") == "bot_b"

    def test_pair_bidirectional_via_two_calls(self, temp_db):
        _make_bot(temp_db, "bot_e")
        _make_bot(temp_db, "bot_f")
        temp_db.update_bot_pair("bot_e", "bot_f")
        temp_db.update_bot_pair("bot_f", "bot_e")
        e = temp_db.get_bot("bot_e")
        f = temp_db.get_bot("bot_f")
        assert e.get("paired_bot_id") == "bot_f"
        assert f.get("paired_bot_id") == "bot_e"

    def test_pair_can_be_cleared(self, temp_db):
        _make_bot(temp_db, "bot_c")
        _make_bot(temp_db, "bot_d")
        temp_db.update_bot_pair("bot_c", "bot_d")
        temp_db.update_bot_pair("bot_c", None)
        c = temp_db.get_bot("bot_c")
        assert c.get("paired_bot_id") is None


# ── DB: is_lucky_fill column ──────────────────────────────────────────────────

class TestIsLuckyFillColumn:
    def test_normal_purchase_is_not_lucky(self, temp_db):
        bot_id = _make_bot(temp_db, "bot_lucky_01")
        epoch = _active_epoch(temp_db, bot_id)
        temp_db.add_purchase(
            "pur_001", bot_id, epoch["epoch_id"], 50000.0, 0.2, 10000.0, "ord1", "FILLED",
            is_lucky_fill=False,
        )
        purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
        assert len(purchases) == 1
        assert bool(purchases[0].get("is_lucky_fill", 0)) is False

    def test_lucky_purchase_is_flagged(self, temp_db):
        bot_id = _make_bot(temp_db, "bot_lucky_02")
        epoch = _active_epoch(temp_db, bot_id)
        temp_db.add_purchase(
            "pur_002", bot_id, epoch["epoch_id"], 45000.0, 0.2, 9000.0, "ord2", "FILLED",
            is_lucky_fill=True,
        )
        purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
        assert bool(purchases[0].get("is_lucky_fill", 0)) is True


# ── Lucky Strike fill classification ─────────────────────────────────────────

def _fill_event(client_oid: str, qty: str = "0.2", cost: str = "10000") -> dict:
    return {"c": client_oid, "X": "FILLED", "i": "order_x", "z": qty, "Z": cost, "p": "50000"}


class TestLuckyStrikeFills:
    """Test that normal fills update last_purchase_price and lucky fills do NOT."""

    def _make_runner(self, db, bot_id, bus, gw):
        runner = LouiseBotRunner(bot_id, db, bus, gw)
        runner.initialize()
        return runner

    def test_normal_fill_updates_last_purchase_price(self, temp_db, event_bus, mock_gateway):
        bot_id = _make_bot(temp_db, "bot_nfill")
        _active_epoch(temp_db, bot_id)
        runner = self._make_runner(temp_db, bot_id, event_bus, mock_gateway)
        runner.active_epoch = temp_db.get_active_epoch(bot_id)

        client_oid = "l_normal_001"
        epoch = runner.active_epoch
        runner.pending_orders[client_oid] = {
            "type": "BUY",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
            "is_lucky_fill": False,
        }

        with patch("runtime.bot.louise.get_budget_guard"):
            runner._on_execution_report(_fill_event(client_oid))

        assert runner.last_purchase_price == Decimal("50000")  # 10000 / 0.2

    def test_lucky_fill_does_not_update_last_purchase_price(self, temp_db, event_bus, mock_gateway):
        bot_id = _make_bot(temp_db, "bot_lfill")
        _active_epoch(temp_db, bot_id)
        runner = self._make_runner(temp_db, bot_id, event_bus, mock_gateway)
        runner.active_epoch = temp_db.get_active_epoch(bot_id)
        runner.last_purchase_price = Decimal("60000")  # prior reference

        client_oid = "l_lucky_001"
        epoch = runner.active_epoch
        runner.pending_orders[client_oid] = {
            "type": "BUY",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
            "is_lucky_fill": True,
        }

        with patch("runtime.bot.louise.get_budget_guard"):
            runner._on_execution_report(_fill_event(client_oid))

        # last_purchase_price must remain at prior value
        assert runner.last_purchase_price == Decimal("60000")

    def test_lucky_fill_still_recorded_in_db(self, temp_db, event_bus, mock_gateway):
        bot_id = _make_bot(temp_db, "bot_lfill_db")
        _active_epoch(temp_db, bot_id)
        runner = self._make_runner(temp_db, bot_id, event_bus, mock_gateway)
        runner.active_epoch = temp_db.get_active_epoch(bot_id)

        client_oid = "l_lucky_002"
        epoch = runner.active_epoch
        runner.pending_orders[client_oid] = {
            "type": "BUY",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
            "is_lucky_fill": True,
        }

        with patch("runtime.bot.louise.get_budget_guard"):
            runner._on_execution_report(_fill_event(client_oid))

        purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
        assert len(purchases) == 1
        assert bool(purchases[0].get("is_lucky_fill", 0)) is True

    def test_lucky_fill_updates_epoch_stats(self, temp_db, event_bus, mock_gateway):
        """Lucky fills still count toward epoch accumulation."""
        bot_id = _make_bot(temp_db, "bot_lfill_epoch")
        _active_epoch(temp_db, bot_id)
        runner = self._make_runner(temp_db, bot_id, event_bus, mock_gateway)
        runner.active_epoch = temp_db.get_active_epoch(bot_id)

        client_oid = "l_lucky_003"
        epoch = runner.active_epoch
        runner.pending_orders[client_oid] = {
            "type": "BUY",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
            "is_lucky_fill": True,
        }

        with patch("runtime.bot.louise.get_budget_guard"):
            runner._on_execution_report(_fill_event(client_oid, qty="0.2", cost="10000"))

        updated = temp_db.get_active_epoch(bot_id)
        assert updated["num_purchases"] == 1
        assert abs(updated["total_cost"] - 10000.0) < 0.01

    def test_lucky_flag_tracked_on_runner(self, temp_db, event_bus, mock_gateway):
        bot_id = _make_bot(temp_db, "bot_lflag")
        _active_epoch(temp_db, bot_id)
        runner = self._make_runner(temp_db, bot_id, event_bus, mock_gateway)
        runner.active_epoch = temp_db.get_active_epoch(bot_id)
        assert runner._last_fill_was_lucky is False

        client_oid = "l_lucky_004"
        epoch = runner.active_epoch
        runner.pending_orders[client_oid] = {
            "type": "BUY",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
            "is_lucky_fill": True,
        }

        with patch("runtime.bot.louise.get_budget_guard"):
            runner._on_execution_report(_fill_event(client_oid))

        assert runner._last_fill_was_lucky is True


# ── AntiLouise Lucky Strike ───────────────────────────────────────────────────

@pytest.mark.skip(reason="AntiLouise deprecated in v4.0")
class TestAntiLouiseLuckyStrike:
    def _make_runner(self, db, bot_id, bus, gw):
        runner = AntiLouiseBotRunner(bot_id, db, bus, gw)
        runner.initialize()
        return runner

    def test_normal_short_updates_last_short_price(self, temp_db, event_bus, mock_gateway):
        bot_id = _make_bot(temp_db, "bot_al_norm", bot_type="anti_louise")
        _active_epoch(temp_db, bot_id)
        runner = self._make_runner(temp_db, bot_id, event_bus, mock_gateway)
        runner.active_epoch = temp_db.get_active_epoch(bot_id)

        client_oid = "al_norm_001"
        epoch = runner.active_epoch
        runner.pending_orders[client_oid] = {
            "type": "SHORT_OPEN",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
            "is_lucky_fill": False,
        }

        with patch("runtime.bot.anti_louise.get_budget_guard"):
            runner._on_execution_report(
                {"c": client_oid, "X": "FILLED", "i": "o1", "z": "0.2", "Z": "10000", "p": "50000"}
            )

        assert runner.last_short_price == Decimal("50000")

    def test_lucky_short_does_not_update_last_short_price(self, temp_db, event_bus, mock_gateway):
        bot_id = _make_bot(temp_db, "bot_al_lucky", bot_type="anti_louise")
        _active_epoch(temp_db, bot_id)
        runner = self._make_runner(temp_db, bot_id, event_bus, mock_gateway)
        runner.active_epoch = temp_db.get_active_epoch(bot_id)
        runner.last_short_price = Decimal("40000")  # prior ref

        client_oid = "al_lucky_001"
        epoch = runner.active_epoch
        runner.pending_orders[client_oid] = {
            "type": "SHORT_OPEN",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
            "is_lucky_fill": True,
        }

        with patch("runtime.bot.anti_louise.get_budget_guard"):
            runner._on_execution_report(
                {"c": client_oid, "X": "FILLED", "i": "o2", "z": "0.2", "Z": "10000", "p": "50000"}
            )

        assert runner.last_short_price == Decimal("40000")

    def test_lucky_short_is_flagged_in_db(self, temp_db, event_bus, mock_gateway):
        bot_id = _make_bot(temp_db, "bot_al_db", bot_type="anti_louise")
        _active_epoch(temp_db, bot_id)
        runner = self._make_runner(temp_db, bot_id, event_bus, mock_gateway)
        runner.active_epoch = temp_db.get_active_epoch(bot_id)

        client_oid = "al_lucky_002"
        epoch = runner.active_epoch
        runner.pending_orders[client_oid] = {
            "type": "SHORT_OPEN",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
            "is_lucky_fill": True,
        }

        with patch("runtime.bot.anti_louise.get_budget_guard"):
            runner._on_execution_report(
                {"c": client_oid, "X": "FILLED", "i": "o3", "z": "0.2", "Z": "10000", "p": "50000"}
            )

        purchases = temp_db.get_purchases_by_epoch(epoch["epoch_id"])
        assert len(purchases) == 1
        assert bool(purchases[0].get("is_lucky_fill", 0)) is True

    def test_lucky_flag_tracked_on_anti_runner(self, temp_db, event_bus, mock_gateway):
        bot_id = _make_bot(temp_db, "bot_al_flag", bot_type="anti_louise")
        _active_epoch(temp_db, bot_id)
        runner = self._make_runner(temp_db, bot_id, event_bus, mock_gateway)
        runner.active_epoch = temp_db.get_active_epoch(bot_id)
        assert runner._last_fill_was_lucky is False

        client_oid = "al_lucky_003"
        epoch = runner.active_epoch
        runner.pending_orders[client_oid] = {
            "type": "SHORT_OPEN",
            "epoch_id": epoch["epoch_id"],
            "epoch": epoch,
            "is_lucky_fill": True,
        }

        with patch("runtime.bot.anti_louise.get_budget_guard"):
            runner._on_execution_report(
                {"c": client_oid, "X": "FILLED", "i": "o4", "z": "0.2", "Z": "10000", "p": "50000"}
            )

        assert runner._last_fill_was_lucky is True


# ── HA-based is_lucky_entry detection ─────────────────────────────────────────

class TestIsLuckyEntry:
    """Unit tests for the HA-extreme detection helper."""

    def _make_runner(self, db, bot_id, bus, gw):
        bot_id = _make_bot(db, bot_id)
        runner = LouiseBotRunner(bot_id, db, bus, gw)
        runner.initialize(subscribe=False)
        runner.current_price = Decimal("50000")
        return runner

    def test_not_lucky_when_vault_has_no_data(self, temp_db, event_bus, mock_gateway):
        runner = self._make_runner(temp_db, "bot_ha_01", event_bus, mock_gateway)
        with patch("runtime.bot.louise.get_telemetry_vault") as mock_vault:
            mock_vault.return_value.get_klines.return_value = []
            assert runner._is_lucky_entry() is False

    def test_not_lucky_when_ha_low_is_none(self, temp_db, event_bus, mock_gateway):
        runner = self._make_runner(temp_db, "bot_ha_02", event_bus, mock_gateway)
        with patch("runtime.bot.louise.get_telemetry_vault") as mock_vault:
            mock_vault.return_value.get_klines.return_value = [
                {"is_closed": 1, "ha_low": None, "ha_high": 52000}
            ]
            assert runner._is_lucky_entry() is False

    def test_not_lucky_when_price_above_ha_low(self, temp_db, event_bus, mock_gateway):
        runner = self._make_runner(temp_db, "bot_ha_03", event_bus, mock_gateway)
        runner.current_price = Decimal("51000")
        with patch("runtime.bot.louise.get_telemetry_vault") as mock_vault:
            mock_vault.return_value.get_klines.return_value = [
                {"is_closed": 1, "ha_low": 49000.0, "ha_high": 55000.0}
            ]
            assert runner._is_lucky_entry() is False

    def test_lucky_when_price_at_ha_low(self, temp_db, event_bus, mock_gateway):
        runner = self._make_runner(temp_db, "bot_ha_04", event_bus, mock_gateway)
        runner.current_price = Decimal("49000")
        with patch("runtime.bot.louise.get_telemetry_vault") as mock_vault:
            mock_vault.return_value.get_klines.return_value = [
                {"is_closed": 1, "ha_low": 49000.0, "ha_high": 55000.0}
            ]
            assert runner._is_lucky_entry() is True

    def test_lucky_when_price_below_ha_low(self, temp_db, event_bus, mock_gateway):
        runner = self._make_runner(temp_db, "bot_ha_05", event_bus, mock_gateway)
        runner.current_price = Decimal("48000")
        with patch("runtime.bot.louise.get_telemetry_vault") as mock_vault:
            mock_vault.return_value.get_klines.return_value = [
                {"is_closed": 1, "ha_low": 49000.0, "ha_high": 55000.0}
            ]
            assert runner._is_lucky_entry() is True

    def test_ignores_open_candle(self, temp_db, event_bus, mock_gateway):
        """An unclosed candle (is_closed=0) must not trigger Lucky Strike."""
        runner = self._make_runner(temp_db, "bot_ha_06", event_bus, mock_gateway)
        runner.current_price = Decimal("40000")
        with patch("runtime.bot.louise.get_telemetry_vault") as mock_vault:
            # Only an open candle; no closed candle available
            mock_vault.return_value.get_klines.return_value = [
                {"is_closed": 0, "ha_low": 42000.0, "ha_high": 55000.0}
            ]
            assert runner._is_lucky_entry() is False

    def test_safe_on_exception(self, temp_db, event_bus, mock_gateway):
        """Vault errors must default to False (never break DCA)."""
        runner = self._make_runner(temp_db, "bot_ha_07", event_bus, mock_gateway)
        with patch("runtime.bot.louise.get_telemetry_vault") as mock_vault:
            mock_vault.side_effect = RuntimeError("vault unavailable")
            assert runner._is_lucky_entry() is False


@pytest.mark.skip(reason="AntiLouise deprecated in v4.0")
class TestAntiLouiseIsLuckyEntry:
    """Mirror tests for AntiLouise HA-high detection."""

    def _make_runner(self, db, bot_id, bus, gw):
        _make_bot(db, bot_id, bot_type="anti_louise")
        runner = AntiLouiseBotRunner(bot_id, db, bus, gw)
        runner.initialize(subscribe=False)
        runner.current_price = Decimal("55000")
        return runner

    def test_lucky_when_price_at_or_above_ha_high(self, temp_db, event_bus, mock_gateway):
        runner = self._make_runner(temp_db, "bot_al_ha_01", event_bus, mock_gateway)
        runner.current_price = Decimal("56000")
        with patch("runtime.bot.anti_louise.get_telemetry_vault") as mock_vault:
            mock_vault.return_value.get_klines.return_value = [
                {"is_closed": 1, "ha_high": 55000.0, "ha_low": 49000.0}
            ]
            assert runner._is_lucky_entry() is True

    def test_not_lucky_when_price_below_ha_high(self, temp_db, event_bus, mock_gateway):
        runner = self._make_runner(temp_db, "bot_al_ha_02", event_bus, mock_gateway)
        runner.current_price = Decimal("54000")
        with patch("runtime.bot.anti_louise.get_telemetry_vault") as mock_vault:
            mock_vault.return_value.get_klines.return_value = [
                {"is_closed": 1, "ha_high": 55000.0, "ha_low": 49000.0}
            ]
            assert runner._is_lucky_entry() is False

    def test_safe_on_exception(self, temp_db, event_bus, mock_gateway):
        runner = self._make_runner(temp_db, "bot_al_ha_03", event_bus, mock_gateway)
        with patch("runtime.bot.anti_louise.get_telemetry_vault") as mock_vault:
            mock_vault.side_effect = RuntimeError("vault down")
            assert runner._is_lucky_entry() is False
