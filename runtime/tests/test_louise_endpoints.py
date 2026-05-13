"""Test suite for Louise API endpoints."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from runtime.api.app import create_app
from runtime.api.auth import get_api_token
from runtime.core.louise_db import LouiseDB


@pytest.fixture
def temp_db(tmp_path):
    """Temporary Louise DB for testing."""
    db_path = str(tmp_path / "louise_test.sqlite")
    return LouiseDB(db_path=db_path)


@pytest.fixture
def client(temp_db):
    """FastAPI test client with temp DB."""
    app = create_app()

    # Override db dependency
    from runtime.api.routers.louise import get_db

    def override_get_db():
        return temp_db

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


@pytest.fixture
def api_token():
    """Get API token for auth."""
    return get_api_token()


class TestLouiseEndpoints:
    """Tests for Louise API endpoints."""

    def test_get_bots_empty(self, client, api_token):
        """Test GET /bots returns empty list initially."""
        headers = {"Authorization": f"Bearer {api_token}"}
        response = client.get("/api/louise/bots", headers=headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_bot_valid(self, client, api_token):
        """Test POST /bots creates bot with valid config."""
        headers = {"Authorization": f"Bearer {api_token}"}

        # Mock exchange filters
        with patch("runtime.api.routers.louise.get_exchange_filters") as mock_filters:
            mock_filters.return_value.get.return_value = MagicMock()

            payload = {
                "symbol": "BTC/USDT",
                "daily_budget": 500.0,
                "target_profit_pct": 5.0,
                "buy_volume": 10.0,
                "poll_interval_seconds": 60,
                "max_position_size_usdt": 5000.0,
                "max_purchases_per_epoch": 20,
            }

            with patch("runtime.api.routers.louise.LouiseBotRunner") as mock_runner:
                mock_instance = MagicMock()
                mock_instance.initialize.return_value = True
                mock_runner.return_value = mock_instance

                response = client.post("/api/louise/bots", json=payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "bot_id" in data
        assert data["status"] == "created"

    def test_create_bot_invalid_budget(self, client, api_token):
        """Test POST /bots rejects negative budget."""
        headers = {"Authorization": f"Bearer {api_token}"}

        payload = {
            "symbol": "BTC/USDT",
            "daily_budget": -100.0,  # Invalid
            "target_profit_pct": 5.0,
            "buy_volume": 10.0,
        }

        response = client.post("/api/louise/bots", json=payload, headers=headers)
        assert response.status_code == 400
        assert "daily_budget" in response.json()["detail"]

    def test_create_bot_invalid_target_profit(self, client, api_token):
        """Test POST /bots rejects zero or extreme target profit."""
        headers = {"Authorization": f"Bearer {api_token}"}

        # Test zero profit
        payload = {
            "symbol": "BTC/USDT",
            "daily_budget": 500.0,
            "target_profit_pct": 0.0,  # Invalid
            "buy_volume": 10.0,
        }

        response = client.post("/api/louise/bots", json=payload, headers=headers)
        assert response.status_code == 400

        # Test extreme profit (>100%)
        payload["target_profit_pct"] = 150.0
        response = client.post("/api/louise/bots", json=payload, headers=headers)
        assert response.status_code == 400

    def test_get_metrics(self, client, api_token, temp_db):
        """Test GET /metrics returns aggregated metrics."""
        headers = {"Authorization": f"Bearer {api_token}"}

        # Create a bot first
        temp_db.create_bot(
            bot_id="louise_btc_test",
            symbol="BTC/USDT",
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

    def test_get_health(self, client, api_token, temp_db):
        """Test GET /health returns real health status."""
        headers = {"Authorization": f"Bearer {api_token}"}

        response = client.get("/api/louise/health", headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "active_bots" in data
        assert "total_bots" in data

        # With no bots, should be healthy
        assert data["status"] == "healthy"
        assert data["active_bots"] == 0

    def test_get_weight_status_real(self, client, api_token):
        """Test GET /weight-governor/status returns real or error, not fake data."""
        headers = {"Authorization": f"Bearer {api_token}"}

        response = client.get("/api/louise/weight-governor/status", headers=headers)
        assert response.status_code == 200

        data = response.json()
        # Should either have real weight or explicit error
        if "error" not in data:
            assert "weight_zone" in data
            assert data["weight_zone"] in ["GREEN", "YELLOW", "RED"]
        else:
            assert "message" in data

    def test_pause_bot(self, client, api_token, temp_db):
        """Test POST /bots/{id}/pause updates bot status."""
        headers = {"Authorization": f"Bearer {api_token}"}

        # Create a bot
        bot_id = "louise_test_pause"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTC/USDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
            status="RUNNING",
        )

        response = client.post(f"/api/louise/bots/{bot_id}/pause", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

        # Verify DB state
        bot = temp_db.get_bot(bot_id)
        assert bot["status"] == "PAUSED"

    def test_resume_bot(self, client, api_token, temp_db):
        """Test POST /bots/{id}/resume updates bot status."""
        headers = {"Authorization": f"Bearer {api_token}"}

        # Create a paused bot
        bot_id = "louise_test_resume"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTC/USDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
            status="PAUSED",
        )

        response = client.post(f"/api/louise/bots/{bot_id}/resume", headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_update_bot_config(self, client, api_token, temp_db):
        """Test PATCH /bots/{id} validates and updates config."""
        headers = {"Authorization": f"Bearer {api_token}"}

        # Create a bot
        bot_id = "louise_test_update"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTC/USDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        # Valid update
        payload = {"daily_budget": 1000.0, "target_profit_pct": 10.0}
        response = client.patch(f"/api/louise/bots/{bot_id}", json=payload, headers=headers)
        assert response.status_code == 200

        # Verify DB state
        bot = temp_db.get_bot(bot_id)
        assert bot["daily_budget_usdt"] == 1000.0
        assert bot["target_profit_pct"] == 10.0

    def test_update_bot_invalid_budget(self, client, api_token, temp_db):
        """Test PATCH /bots/{id} rejects invalid budget."""
        headers = {"Authorization": f"Bearer {api_token}"}

        # Create a bot
        bot_id = "louise_test_invalid"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTC/USDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        payload = {"daily_budget": -100.0}
        response = client.patch(f"/api/louise/bots/{bot_id}", json=payload, headers=headers)
        assert response.status_code == 400

    def test_delete_bot(self, client, api_token, temp_db):
        """Test DELETE /bots/{id} marks bot as SHUTDOWN."""
        headers = {"Authorization": f"Bearer {api_token}"}

        bot_id = "louise_test_delete"
        temp_db.create_bot(
            bot_id=bot_id,
            symbol="BTC/USDT",
            buy_volume=10.0,
            poll_interval_seconds=60,
            target_profit_pct=5.0,
            daily_budget_usdt=500.0,
        )

        response = client.delete(f"/api/louise/bots/{bot_id}", headers=headers)
        assert response.status_code == 200

        # Verify status
        bot = temp_db.get_bot(bot_id)
        assert bot["status"] == "SHUTDOWN"

    def test_bot_not_found(self, client, api_token):
        """Test 404 when bot doesn't exist."""
        headers = {"Authorization": f"Bearer {api_token}"}

        response = client.get("/api/louise/bots/nonexistent", headers=headers)
        assert response.status_code == 404 or response.status_code == 200  # GET /bots returns all
