"""Tests for the console/telemetry endpoints on the Louise router.

Endpoints exercised:
  GET /api/louise/bots/{bot_id}/pnl-history
  GET /api/louise/bots/{bot_id}/purchases
  GET /api/louise/hub/combined-pnl
  GET /api/louise/hub/dual-state
  GET /api/louise/klines/{symbol}
"""

import os
import pytest
from fastapi.testclient import TestClient

from runtime.api.app import create_app
from runtime.core.louise_db import LouiseDB


@pytest.fixture
def temp_db(tmp_path):
    return LouiseDB(db_path=str(tmp_path / "console_test.sqlite"))


@pytest.fixture
def client(temp_db):
    os.environ["PECUNATOR_API_AUTH_DISABLED"] = "1"
    from runtime.api.routers.louise import get_db
    app = create_app()
    app.dependency_overrides[get_db] = lambda: temp_db
    yield TestClient(app)
    os.environ.pop("PECUNATOR_API_AUTH_DISABLED", None)


def _seed_two_bots(db: LouiseDB):
    """Create one Louise long + one AntiLouise short for dual-hub tests."""
    db.create_bot(
        bot_id="louise_btc", symbol="BTCUSDT", buy_volume=10.0,
        poll_interval_seconds=60, target_profit_pct=5.0,
        daily_budget_usdt=500.0, bot_type="louise",
    )
    db.create_bot(
        bot_id="anti_btc", symbol="BTCUSDT", buy_volume=10.0,
        poll_interval_seconds=60, target_profit_pct=5.0,
        daily_budget_usdt=500.0, bot_type="anti_louise",
    )


# ── /bots/{bot_id}/pnl-history ────────────────────────────────────────

class TestPnlHistoryEndpoint:

    def test_404_for_unknown_bot(self, client):
        r = client.get("/api/louise/bots/does_not_exist/pnl-history")
        assert r.status_code == 404

    def test_returns_snapshots_for_existing_bot(self, client, temp_db):
        _seed_two_bots(temp_db)
        temp_db.record_pnl_snapshot(
            bot_id="louise_btc", bot_type="louise", current_price=50000.0,
            avg_entry_price_usdt=49000.0, num_entries=2,
            total_committed_usdt=100.0, unrealized_pnl_usdt=2.04,
            unrealized_pnl_pct=2.04, cumulative_realized_pnl_usdt=10.0,
        )
        r = client.get("/api/louise/bots/louise_btc/pnl-history")
        assert r.status_code == 200
        data = r.json()
        assert data["bot_id"] == "louise_btc"
        assert data["count"] == 1
        snap = data["snapshots"][0]
        assert snap["bot_type"] == "louise"
        assert snap["unrealized_pnl_usdt"] == 2.04
        assert snap["net_position_usdt"] == pytest.approx(12.04, rel=1e-6)


# ── /bots/{bot_id}/purchases ──────────────────────────────────────────

class TestPurchasesEndpoint:

    def test_404_for_unknown_bot(self, client):
        r = client.get("/api/louise/bots/missing/purchases")
        assert r.status_code == 404

    def test_returns_oldest_first(self, client, temp_db):
        _seed_two_bots(temp_db)
        temp_db.create_epoch("ep_a", "louise_btc", "RUNNING")
        temp_db.add_purchase("p1", "louise_btc", "ep_a", 50000.0, 0.001, 50.0, "o1", "FILLED")
        temp_db.add_purchase("p2", "louise_btc", "ep_a", 49000.0, 0.001, 49.0, "o2", "FILLED")

        r = client.get("/api/louise/bots/louise_btc/purchases")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert data["purchases"][0]["purchase_id"] == "p1"
        assert data["purchases"][1]["purchase_id"] == "p2"


# ── /hub/combined-pnl ─────────────────────────────────────────────────

class TestCombinedPnlEndpoint:

    def test_aggregates_across_bots(self, client, temp_db):
        _seed_two_bots(temp_db)
        # Louise: +5 unrealized, +20 realized
        temp_db.record_pnl_snapshot(
            bot_id="louise_btc", bot_type="louise", current_price=50000.0,
            total_committed_usdt=100.0, unrealized_pnl_usdt=5.0,
            cumulative_realized_pnl_usdt=20.0,
        )
        # AntiLouise: -3 unrealized, +12 realized
        temp_db.record_pnl_snapshot(
            bot_id="anti_btc", bot_type="anti_louise", current_price=50000.0,
            total_committed_usdt=100.0, unrealized_pnl_usdt=-3.0,
            cumulative_realized_pnl_usdt=12.0,
        )

        r = client.get("/api/louise/hub/combined-pnl")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert set(data["by_bot_id"].keys()) == {"louise_btc", "anti_btc"}
        totals = data["totals"]
        assert totals["cumulative_realized_pnl_usdt"] == pytest.approx(32.0)
        assert totals["unrealized_pnl_usdt"] == pytest.approx(2.0)
        assert totals["net_position_usdt"] == pytest.approx(34.0)


# ── /hub/dual-state ───────────────────────────────────────────────────

class TestDualStateEndpoint:

    def test_returns_state_with_no_bots(self, client):
        r = client.get("/api/louise/hub/dual-state")
        assert r.status_code == 200
        data = r.json()
        assert data["bots"] == []
        assert data["totals"]["net_position_usdt"] == 0.0

    def test_includes_both_bots_with_metadata(self, client, temp_db):
        _seed_two_bots(temp_db)
        temp_db.record_pnl_snapshot(
            bot_id="louise_btc", bot_type="louise", current_price=50000.0,
            total_committed_usdt=100.0, unrealized_pnl_usdt=2.5,
            cumulative_realized_pnl_usdt=10.0,
        )

        r = client.get("/api/louise/hub/dual-state")
        assert r.status_code == 200
        data = r.json()
        assert len(data["bots"]) == 2
        bots_by_id = {b["bot_id"]: b for b in data["bots"]}
        assert bots_by_id["louise_btc"]["bot_type"] == "louise"
        assert bots_by_id["anti_btc"]["bot_type"] == "anti_louise"
        # Louise has a snapshot, anti_btc doesn't
        assert bots_by_id["louise_btc"]["latest_snapshot"]["unrealized_pnl_usdt"] == 2.5
        assert bots_by_id["anti_btc"]["latest_snapshot"] == {}

        # Totals reflect only louise_btc's snapshot
        assert data["totals"]["net_position_usdt"] == pytest.approx(12.5)


# ── /klines/{symbol} ──────────────────────────────────────────────────

class TestKlinesEndpoint:

    def test_returns_empty_when_no_klines(self, client):
        r = client.get("/api/louise/klines/BTCUSDT?interval=1d&limit=10")
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "BTCUSDT"
        assert data["interval"] == "1d"
        assert data["candles"] == []
        assert data["count"] == 0

    def test_returns_ingested_klines(self, client, tmp_path):
        """End-to-end: ingest klines via TelemetryVault, fetch via endpoint."""
        from runtime.core.telemetry_vault import get_telemetry_vault

        # The route uses get_telemetry_vault(data_dir) — get a handle via the singleton
        # The singleton caches by first-call data_dir; reset it for test isolation
        import runtime.core.telemetry_vault as tv_mod
        tv_mod._vault = None
        vault = get_telemetry_vault(tmp_path)

        klines = [
            [1000, "100", "110", "95", "105", "1.0", 2000, "0", 1],
            [2000, "105", "120", "100", "115", "1.0", 3000, "0", 1],
        ]
        vault.store_klines_with_ha("BTCUSDT", "1d", klines)

        # Override the deps.peek_ctx so the route uses our tmp_path
        from runtime.api import deps as _deps
        class _FakeCtx:
            class config:
                data_dir = tmp_path
        original = _deps.peek_ctx
        _deps.peek_ctx = lambda: _FakeCtx()
        try:
            r = client.get("/api/louise/klines/BTCUSDT?interval=1d&limit=10")
        finally:
            _deps.peek_ctx = original

        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        # Each candle has both OHLC and HA fields
        for c in data["candles"]:
            assert "open" in c and "close" in c
            assert "ha_open" in c and "ha_close" in c
            assert c["ha_open"] is not None
            assert c["ha_close"] is not None
