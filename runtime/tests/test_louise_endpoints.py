"""Test suite for Louise API endpoints."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from runtime.api.app import create_app
from runtime.core.louise_db import LouiseDB


@pytest.fixture
def temp_db(tmp_path):
    """Temporary Louise DB for testing."""
    db_path = str(tmp_path / "louise_test.sqlite")
    return LouiseDB(db_path=db_path)


@pytest.fixture
def client(temp_db):
    """FastAPI test client with temp DB.

    Uses PECUNATOR_API_AUTH_DISABLED=1 so we don't need a real token file,
    plus overrides the LouiseDB dependency to point at the temp DB.
    """
    import os
    os.environ["PECUNATOR_API_AUTH_DISABLED"] = "1"

    # Override get_db before app creation so dependency_overrides catch it
    from runtime.api.routers.louise import get_db

    app = create_app()
    app.dependency_overrides[get_db] = lambda: temp_db

    yield TestClient(app)
    os.environ.pop("PECUNATOR_API_AUTH_DISABLED", None)


@pytest.fixture
def headers():
    """Empty headers — auth disabled in test fixture."""
    return {}


class TestLouiseEndpoints:
    """Tests for Louise API endpoints."""

    def test_get_bots_empty(self, client, headers):
        """Test GET /bots returns empty list initially."""
        response = client.get("/api/louise/bots", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_bot_valid(self, client, headers):
        """Test POST /bots creates bot with valid config."""
        payload = {
            "symbol": "BTCUSDT",
            "daily_budget": 500.0,
            "target_profit_pct": 5.0,
            "buy_volume": 10.0,
            "poll_interval_seconds": 60,
            "max_position_size_usdt": 5000.0,
            "max_purchases_per_epoch": 20,
        }

        with patch("runtime.core.exchange_filters.get_exchange_filters") as mock_filters:
            filters_instance = MagicMock()
            filters_instance.get.return_value = MagicMock()  # Symbol exists
            mock_filters.return_value = filters_instance

            with patch("runtime.api.deps.get_ctx") as mock_ctx:
                mock_ctx.return_value = MagicMock()
                with patch("runtime.api._helpers.resolve_pair_for_bot", return_value=("key", "secret")):
                    with patch("runtime.bot.louise.LouiseBotRunner.initialize", return_value=True):
                        response = client.post("/api/louise/bots", json=payload, headers=headers)

        assert response.status_code == 200, f"Got {response.status_code}: {response.text}"
        data = response.json()
        assert "bot_id" in data
        assert data["status"] == "created"

    def test_create_bot_invalid_budget(self, client, headers):
        """Test POST /bots rejects negative budget."""
        payload = {
            "symbol": "BTCUSDT",
            "daily_budget": -100.0,
            "target_profit_pct": 5.0,
            "buy_volume": 10.0,
        }

        response = client.post("/api/louise/bots", json=payload, headers=headers)
        assert response.status_code == 400
        assert "daily_budget" in response.json()["detail"]

    def test_create_bot_invalid_target_profit_zero(self, client, headers):
        """Test POST /bots rejects zero target profit."""
        payload = {
            "symbol": "BTCUSDT",
            "daily_budget": 500.0,
            "target_profit_pct": 0.0,
            "buy_volume": 10.0,
        }
        response = client.post("/api/louise/bots", json=payload, headers=headers)
        assert response.status_code == 400

    def test_create_bot_invalid_target_profit_extreme(self, client, headers):
        """Test POST /bots rejects extreme target profit."""
        payload = {
            "symbol": "BTCUSDT",
            "daily_budget": 500.0,
            "target_profit_pct": 150.0,
            "buy_volume": 10.0,
        }
        response = client.post("/api/louise/bots", json=payload, headers=headers)
        assert response.status_code == 400

    def test_create_bot_invalid_symbol(self, client, headers):
        """Test POST /bots rejects symbol not in exchange filters."""
        payload = {
            "symbol": "FAKE/COIN",
            "daily_budget": 500.0,
            "target_profit_pct": 5.0,
            "buy_volume": 10.0,
        }
        # Mock filters as no match
        with patch("runtime.core.exchange_filters.get_exchange_filters") as mock_filters:
            mock_filters.return_value.get.return_value = None
            response = client.post("/api/louise/bots", json=payload, headers=headers)
        assert response.status_code == 400
        assert "exchange filters" in response.json()["detail"]

    def test_get_metrics(self, client, headers, temp_db):
        """Test GET /metrics returns aggregated metrics."""
        temp_db.create_bot(
            bot_id="louise_btc_test",
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        response = client.get("/api/louise/metrics", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "active_bots" in data
        assert "total_portfolio" in data
        assert "total_unrealized_pnl" in data

    def test_get_health_no_fake_data(self, client, headers, temp_db):
        """Test GET /health returns REAL health status (not hardcoded)."""
        response = client.get("/api/louise/health", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "active_bots" in data
        assert "total_bots" in data
        # Verify it's not the old hardcoded blob
        assert "paused_bots" in data, "Expected new health schema with paused_bots field"

        # With no bots, should be healthy
        assert data["active_bots"] == 0

    def test_get_weight_status_real_or_error(self, client, headers):
        """Test GET /weight-governor/status returns real data OR explicit error (no fake 1050)."""
        response = client.get("/api/louise/weight-governor/status", headers=headers)
        assert response.status_code == 200

        data = response.json()
        # Must be either real with weight_zone OR explicit error — never invented numbers
        if "error" in data:
            assert "message" in data
            assert data.get("current_weight") != 1050  # No fake fallback
        else:
            assert "weight_zone" in data
            assert data["weight_zone"] in ["GREEN", "YELLOW", "RED"]

    def test_get_weight_history_metadata(self, client, headers):
        """Test GET /weight-governor/history returns dict with metadata, not bare list."""
        response = client.get("/api/louise/weight-governor/history", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict), "Should return dict with ready/data fields"
        assert "ready" in data
        assert "data" in data

    def test_pause_bot(self, client, headers, temp_db):
        """Test POST /bots/{id}/pause updates bot status."""
        bot_id = "louise_test_pause"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
            status="RUNNING",
        )

        response = client.post(f"/api/louise/bots/{bot_id}/pause", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

        bot = temp_db.get_bot(bot_id)
        assert bot["status"] == "PAUSED"

    def test_resume_bot(self, client, headers, temp_db):
        """Test POST /bots/{id}/resume updates bot status."""
        bot_id = "louise_test_resume"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
            status="PAUSED",
        )

        response = client.post(f"/api/louise/bots/{bot_id}/resume", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_update_bot_config_valid(self, client, headers, temp_db):
        """Test PATCH /bots/{id} updates with valid params."""
        bot_id = "louise_test_update"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        payload = {"daily_budget": 1000.0, "target_profit_pct": 10.0}
        response = client.patch(f"/api/louise/bots/{bot_id}", json=payload, headers=headers)
        assert response.status_code == 200

        bot = temp_db.get_bot(bot_id)
        assert bot["daily_budget_usdt"] == 1000.0
        assert bot["target_profit_pct"] == 10.0

    def test_update_bot_risk_fields(self, client, headers, temp_db):
        """Test PATCH /bots/{id} can update max_position_size and max_purchases."""
        bot_id = "louise_test_risk_update"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        payload = {"max_position_size_usdt": 10000.0, "max_purchases_per_epoch": 30}
        response = client.patch(f"/api/louise/bots/{bot_id}", json=payload, headers=headers)
        assert response.status_code == 200, response.text

        bot = temp_db.get_bot(bot_id)
        assert bot["max_position_size_usdt"] == 10000.0
        assert bot["max_purchases_per_epoch"] == 30

    def test_update_bot_invalid_budget(self, client, headers, temp_db):
        """Test PATCH /bots/{id} rejects invalid budget."""
        bot_id = "louise_test_invalid"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        payload = {"daily_budget": -100.0}
        response = client.patch(f"/api/louise/bots/{bot_id}", json=payload, headers=headers)
        assert response.status_code == 400

    def test_update_bot_not_found(self, client, headers):
        """Test PATCH /bots/{id} returns 404 for non-existent bot."""
        response = client.patch(
            "/api/louise/bots/nonexistent",
            json={"daily_budget": 100.0},
            headers=headers,
        )
        assert response.status_code == 404

    def test_delete_bot(self, client, headers, temp_db):
        """Test DELETE /bots/{id} marks bot as SHUTDOWN."""
        bot_id = "louise_test_delete"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTCUSDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        response = client.delete(f"/api/louise/bots/{bot_id}", headers=headers)
        assert response.status_code == 200

        bot = temp_db.get_bot(bot_id)
        assert bot["status"] == "SHUTDOWN"

    def test_pause_bot_not_found(self, client, headers):
        """Test 404 when pausing a non-existent bot."""
        response = client.post("/api/louise/bots/nonexistent/pause", headers=headers)
        assert response.status_code == 404
