"""Tests for Heikin-Ashi storage in kline_history.

Critical invariant: the HA chain must be continuous across batches.
If the user fetches HA at any point in time, it must match what
would be computed from the full history in one pass — no drift
allowed when ingesting in chunks.
"""

from pathlib import Path

import pytest

from runtime.core.telemetry_vault import TelemetryVault
from runtime.modules.trend_signal import compute_heikin_ashi


@pytest.fixture
def vault(tmp_path):
    return TelemetryVault(tmp_path / "telemetry_vault_test.sqlite")


def _kline(open_time: int, o: float, h: float, lo: float, c: float,
           v: float = 1.0, close_time: int = 0):
    """Build a Binance-style kline row."""
    return [open_time, str(o), str(h), str(lo), str(c), str(v),
            close_time or open_time + 60000, "0", 1]


class TestHAContinuity:

    def test_single_batch_matches_compute_heikin_ashi(self, vault):
        """HA stored in one batch must match the reference compute_heikin_ashi formula."""
        klines = [
            _kline(1000, 100, 110, 95, 105),
            _kline(2000, 105, 120, 100, 115),
            _kline(3000, 115, 125, 108, 118),
            _kline(4000, 118, 122, 110, 113),
            _kline(5000, 113, 116, 105, 108),
        ]

        vault.store_klines_with_ha("BTCUSDT", "1d", klines)
        rows = vault.get_klines("BTCUSDT", "1d", limit=10)
        rows_oldest_first = sorted(rows, key=lambda r: r["open_time"])

        expected = compute_heikin_ashi(klines)
        for got, exp in zip(rows_oldest_first, expected):
            assert abs(got["ha_open"] - exp["ha_open"]) < 1e-9
            assert abs(got["ha_close"] - exp["ha_close"]) < 1e-9
            assert abs(got["ha_high"] - exp["ha_high"]) < 1e-9
            assert abs(got["ha_low"] - exp["ha_low"]) < 1e-9

    def test_split_batches_preserve_chain(self, vault):
        """Storing first half, then second half, must yield same HA as storing all at once."""
        klines = [
            _kline(1000, 100, 110, 95, 105),
            _kline(2000, 105, 120, 100, 115),
            _kline(3000, 115, 125, 108, 118),
            _kline(4000, 118, 122, 110, 113),
            _kline(5000, 113, 116, 105, 108),
            _kline(6000, 108, 112, 100, 104),
        ]

        # Split: first 3, then last 3
        vault.store_klines_with_ha("ETHUSDT", "1d", klines[:3])
        vault.store_klines_with_ha("ETHUSDT", "1d", klines[3:])

        rows = vault.get_klines("ETHUSDT", "1d", limit=10)
        rows_oldest_first = sorted(rows, key=lambda r: r["open_time"])

        expected = compute_heikin_ashi(klines)
        for got, exp in zip(rows_oldest_first, expected):
            assert abs(got["ha_open"] - exp["ha_open"]) < 1e-9, \
                f"chain broken at open_time={got['open_time']}"
            assert abs(got["ha_close"] - exp["ha_close"]) < 1e-9

    def test_upsert_refreshes_unclosed_candle(self, vault):
        """Re-ingesting the same open_time with new OHLC must UPDATE not duplicate."""
        first = _kline(1000, 100, 105, 98, 102)
        vault.store_klines_with_ha("BTCUSDT", "1d", [first])

        # Same open_time, updated high/close (candle still forming)
        updated = _kline(1000, 100, 115, 98, 112)
        vault.store_klines_with_ha("BTCUSDT", "1d", [updated])

        rows = vault.get_klines("BTCUSDT", "1d", limit=10)
        assert len(rows) == 1
        assert float(rows[0]["high"]) == 115.0
        assert float(rows[0]["close"]) == 112.0
        # HA recomputed with new values
        assert abs(rows[0]["ha_close"] - (100 + 115 + 98 + 112) / 4.0) < 1e-9

    def test_is_closed_flag_marks_forming_candle(self, vault):
        """When server_time < close_time, the candle is_closed must be 0."""
        # Candle close_time at 2000, server time at 1500 → still forming
        k = _kline(1000, 100, 105, 98, 102, close_time=2000)
        vault.store_klines_with_ha("BTCUSDT", "1d", [k],
                                    current_server_time_ms=1500)
        rows = vault.get_klines("BTCUSDT", "1d", limit=10)
        assert rows[0]["is_closed"] == 0

        # Same candle, server now past close → marked closed
        vault.store_klines_with_ha("BTCUSDT", "1d", [k],
                                    current_server_time_ms=3000)
        rows = vault.get_klines("BTCUSDT", "1d", limit=10)
        assert rows[0]["is_closed"] == 1

    def test_empty_input_returns_zero(self, vault):
        assert vault.store_klines_with_ha("BTCUSDT", "1d", []) == 0

    def test_bootstrap_uses_canonical_formula(self, vault):
        """First candle's ha_open must use (open + close) / 2 bootstrap formula."""
        k = _kline(1000, 100, 110, 95, 106)
        vault.store_klines_with_ha("BTCUSDT", "1d", [k])
        rows = vault.get_klines("BTCUSDT", "1d", limit=1)
        # ha_open[0] = (100 + 106) / 2 = 103
        assert abs(rows[0]["ha_open"] - 103.0) < 1e-9
        # ha_close[0] = (100 + 110 + 95 + 106) / 4 = 102.75
        assert abs(rows[0]["ha_close"] - 102.75) < 1e-9


class TestPnlSnapshotMetrics:

    def test_net_position_computed_correctly(self, tmp_path):
        """record_pnl_snapshot must compute net_position_usdt = realized + unrealized."""
        from runtime.core.louise_db import LouiseDB

        db = LouiseDB(db_path=str(tmp_path / "louise_metrics_test.sqlite"))
        db.create_bot(
            bot_id="metrics_bot",
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        db.record_pnl_snapshot(
            bot_id="metrics_bot",
            bot_type="louise",
            current_price=50000.0,
            avg_entry_price_usdt=49000.0,
            num_entries=2,
            total_committed_usdt=100.0,
            unrealized_pnl_usdt=2.04,
            unrealized_pnl_pct=2.04,
            cumulative_realized_pnl_usdt=15.50,
        )

        latest = db.get_latest_pnl_snapshot("metrics_bot")
        assert latest is not None
        assert abs(latest["net_position_usdt"] - (15.50 + 2.04)) < 1e-6
        # net_position_pct = (17.54 / 100) * 100 = 17.54
        assert abs(latest["net_position_pct"] - 17.54) < 1e-4

    def test_realized_pnl_sums_closed_epochs_only(self, tmp_path):
        """get_total_realized_pnl must sum profit_usdt from non-RUNNING epochs only."""
        from runtime.core.louise_db import LouiseDB

        db = LouiseDB(db_path=str(tmp_path / "louise_realized_test.sqlite"))
        db.create_bot(
            bot_id="realized_bot",
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        # Closed with +$10 profit
        db.create_epoch("ep1", "realized_bot", "RUNNING")
        db.close_epoch("ep1", 51000.0, 105.0, 10.0, 5.0, "CLOSED_SUCCESSFUL")
        # Closed with -$3 profit (small loss)
        db.create_epoch("ep2", "realized_bot", "RUNNING")
        db.close_epoch("ep2", 49000.0, 97.0, -3.0, -3.0, "CLOSED_SUCCESSFUL")
        # Still RUNNING (should NOT count) — leave it RUNNING
        db.create_epoch("ep3", "realized_bot", "RUNNING")

        assert abs(db.get_total_realized_pnl("realized_bot") - 7.0) < 1e-6


class TestDbHelpers:

    def test_get_purchases_by_bot_returns_oldest_first(self, tmp_path):
        from runtime.core.louise_db import LouiseDB

        db = LouiseDB(db_path=str(tmp_path / "louise_purchases_test.sqlite"))
        db.create_bot(
            bot_id="purchases_bot",
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )
        db.create_epoch("ep1", "purchases_bot", "RUNNING")

        # Insert purchases across two epochs
        db.add_purchase("p1", "purchases_bot", "ep1", 50000.0, 0.001, 50.0, "o1", "FILLED")
        db.add_purchase("p2", "purchases_bot", "ep1", 49000.0, 0.001, 49.0, "o2", "FILLED")

        db.close_epoch("ep1", 51000.0, 100.0, 1.0, 1.0, "CLOSED_SUCCESSFUL")
        db.create_epoch("ep2", "purchases_bot", "RUNNING")
        db.add_purchase("p3", "purchases_bot", "ep2", 48000.0, 0.001, 48.0, "o3", "FILLED")

        all_purchases = db.get_purchases_by_bot("purchases_bot")
        assert len(all_purchases) == 3
        # Sorted oldest first
        assert all_purchases[0]["purchase_id"] == "p1"
        assert all_purchases[1]["purchase_id"] == "p2"
        assert all_purchases[2]["purchase_id"] == "p3"

    def test_latest_pnl_snapshot_returns_most_recent(self, tmp_path):
        import time
        from runtime.core.louise_db import LouiseDB

        db = LouiseDB(db_path=str(tmp_path / "louise_latest_test.sqlite"))
        db.create_bot(
            bot_id="latest_bot", symbol="BTCUSDT", buy_volume=10.0,
            poll_interval_seconds=60, target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        db.record_pnl_snapshot(
            bot_id="latest_bot", bot_type="louise", current_price=50000.0,
            unrealized_pnl_usdt=1.0,
        )
        time.sleep(1.05)  # snapshot_at is whole seconds, need different ts
        db.record_pnl_snapshot(
            bot_id="latest_bot", bot_type="louise", current_price=51000.0,
            unrealized_pnl_usdt=5.0,
        )

        latest = db.get_latest_pnl_snapshot("latest_bot")
        assert latest is not None
        assert abs(latest["unrealized_pnl_usdt"] - 5.0) < 1e-6
        assert abs(latest["current_price"] - 51000.0) < 1e-6

    def test_latest_pnl_snapshot_none_when_no_snapshots(self, tmp_path):
        from runtime.core.louise_db import LouiseDB

        db = LouiseDB(db_path=str(tmp_path / "louise_empty_test.sqlite"))
        assert db.get_latest_pnl_snapshot("never_existed_bot") is None
