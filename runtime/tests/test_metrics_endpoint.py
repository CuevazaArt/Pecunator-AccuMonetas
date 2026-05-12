"""Tests for Prometheus metrics endpoint."""

import pytest
from fastapi.testclient import TestClient

from runtime.api.app import create_app


@pytest.fixture
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


class TestMetricsEndpoint:
    """Test metrics endpoint functionality."""

    def test_metrics_endpoint_returns_prometheus_format(self, client):
        """GET /metrics should return Prometheus text format."""
        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")

    def test_metrics_endpoint_includes_louise_metrics(self, client):
        """Prometheus output should include Louise metrics."""
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # Should include Louise metric names
        assert "louise_bots_active" in content
        assert "louise_epochs_completed_total" in content
        assert "louise_orders_filled_total" in content
        assert "louise_fill_latency_seconds" in content
        assert "louise_pnl_total" in content

    def test_metrics_endpoint_includes_api_metrics(self, client):
        """Prometheus output should include API metrics."""
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # Should include API metric names
        assert "api_requests_total" in content
        assert "api_request_duration_seconds" in content

    def test_metrics_endpoint_includes_risk_control_metrics(self, client):
        """Prometheus output should include risk control metrics."""
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # Should include risk control metric names
        assert "api_fuse_trips_total" in content
        assert "weight_governor_blocks_total" in content
        assert "budget_guard_blocks_total" in content

    def test_metrics_endpoint_includes_gateway_metrics(self, client):
        """Prometheus output should include gateway metrics."""
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # Should include gateway metric names
        assert "websocket_reconnects_total" in content
        assert "gateway_uptime_seconds" in content

    def test_metrics_endpoint_includes_database_metrics(self, client):
        """Prometheus output should include database metrics."""
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # Should include database metric names
        assert "database_query_duration_seconds" in content
        assert "database_queries_total" in content

    def test_metrics_includes_help_text(self, client):
        """Prometheus output should include HELP text for metrics."""
        response = client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # Should include HELP lines (Prometheus format)
        assert "# HELP" in content
        assert "# TYPE" in content

    def test_metrics_endpoint_is_accessible_without_auth(self, client):
        """Metrics endpoint should be accessible without authentication."""
        # Note: TestClient doesn't enforce auth by default, but we can verify
        # the endpoint doesn't require a token by checking response code
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_incremental_calls(self, client):
        """Multiple calls to metrics should return valid format."""
        # First call
        response1 = client.get("/metrics")
        assert response1.status_code == 200

        # Second call
        response2 = client.get("/metrics")
        assert response2.status_code == 200

        # Both should have same metric names
        assert "louise_bots_active" in response1.text
        assert "louise_bots_active" in response2.text
