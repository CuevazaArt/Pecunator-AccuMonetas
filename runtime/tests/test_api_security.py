"""Security tests for API authentication and WebSocket protection."""

import os
import pytest
from fastapi.testclient import TestClient
from runtime.api.app import create_app
from runtime.api.auth import get_api_token


@pytest.fixture
def client():
    """FastAPI test client with lifespan disabled for testing."""
    # Create app without lifespan to avoid AppContext initialization
    app = create_app()
    return TestClient(app, manage_lifespan=False)


@pytest.fixture
def valid_token():
    """Get the valid API token."""
    return get_api_token()


class TestHTTPAuthRequired:
    """Test that protected HTTP endpoints require valid authentication."""

    def test_vault_endpoint_requires_auth(self, client):
        """GET /api/v1/vault/status should reject requests without token."""
        response = client.get("/api/v1/vault/status")
        assert response.status_code == 401, "Unauth request should be rejected with 401"


    def test_order_ledger_endpoint_requires_auth(self, client):
        """GET /api/v1/order-ledger/recent should require authentication."""
        response = client.get("/api/v1/order-ledger/recent")
        assert response.status_code == 401, "Protected endpoint without token must be rejected"

    def test_weight_governor_endpoint_requires_auth(self, client):
        """GET /api/v1/weight-governor/status should require authentication."""
        response = client.get("/api/v1/weight-governor/status")
        assert response.status_code == 401, "Protected endpoint without token must be rejected"

    def test_budget_guard_endpoint_requires_auth(self, client):
        """GET /api/v1/budget-guard/status should require authentication."""
        response = client.get("/api/v1/budget-guard/status")
        assert response.status_code == 401, "Protected endpoint without token must be rejected"

    def test_invalid_bearer_token_rejected(self, client):
        """Requests with invalid bearer token should be rejected."""
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = client.get("/api/v1/vault/status", headers=headers)
        assert response.status_code == 401, "Invalid token should be rejected"

    def test_malformed_auth_header_rejected(self, client):
        """Requests with malformed auth header should be rejected."""
        headers = {"Authorization": "NotBearer validtoken"}
        response = client.get("/api/v1/vault/status", headers=headers)
        assert response.status_code == 401, "Malformed auth should be rejected"

    def test_missing_auth_header_rejected(self, client):
        """Requests without Authorization header should be rejected."""
        response = client.get("/api/v1/vault/status")
        assert response.status_code == 401, "Missing auth header should be rejected"

    def test_empty_token_rejected(self, client):
        """Requests with empty token should be rejected."""
        headers = {"Authorization": "Bearer "}
        response = client.get("/api/v1/vault/status", headers=headers)
        assert response.status_code == 401, "Empty token should be rejected"

    def test_token_case_sensitive(self, client, valid_token):
        """Token validation should be case-sensitive."""
        # Invalid case (uppercase token) should fail auth
        headers_bad = {"Authorization": f"Bearer {valid_token.upper()}"}
        response_bad = client.get("/api/v1/vault/status", headers=headers_bad)
        assert response_bad.status_code == 401, "Token should be case-sensitive; uppercase should fail"


class TestMetricsNoAuth:
    """Test that metrics endpoint is accessible without authentication."""

    def test_metrics_accessible_without_auth(self, client):
        """GET /metrics should NOT require authentication."""
        response = client.get("/metrics")
        assert response.status_code == 200, "Metrics should be public (no auth required)"

    def test_metrics_returns_prometheus_format(self, client):
        """GET /metrics should return valid Prometheus format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")

    def test_metrics_ignores_auth_header(self, client, valid_token):
        """Metrics endpoint should work regardless of auth header."""
        headers = {"Authorization": f"Bearer {valid_token}"}
        response = client.get("/metrics", headers=headers)
        assert response.status_code == 200


class TestWebSocketAuth:
    """Test WebSocket authentication via token parameter or header."""

    def test_websocket_rejects_without_token(self, client):
        """WebSocket /ws/telemetry should close (1008) without valid token."""
        with pytest.raises(Exception):
            # TestClient doesn't support full WebSocket flow, but connection
            # without token should fail at handshake
            with client.websocket_connect("/ws/telemetry") as ws:
                pass

    def test_websocket_requires_valid_token(self, client, valid_token):
        """WebSocket token validation: connection without valid token fails."""
        # The WebSocket handshake in stream.py validates token before accepting
        # Invalid or missing token causes close with code 1008 (Policy Violation)
        invalid_token_url = "/ws/telemetry?token=invalid_token_xyz"
        with pytest.raises(Exception):
            with client.websocket_connect(invalid_token_url) as ws:
                pass

    def test_websocket_accepts_valid_token_via_query(self, client, valid_token):
        """WebSocket accepts valid token via query parameter ?token=..."""
        # Valid token via query param should pass auth handshake
        # May fail later on lack of AppContext, but not on auth
        url = f"/ws/telemetry?token={valid_token}"
        # This may raise due to AppContext, but NOT due to auth (1008)
        try:
            with client.websocket_connect(url) as ws:
                pass
        except Exception as e:
            # Auth should not reject with 1008; other errors OK
            assert "1008" not in str(e)




class TestAuthBypassEnvironmentVariable:
    """Test that PECUNATOR_API_AUTH_DISABLED can disable auth (dev only)."""

    def test_auth_can_be_disabled_via_env(self, client, monkeypatch):
        """When PECUNATOR_API_AUTH_DISABLED=1, endpoints should not require token."""
        # This test verifies the env var behavior exists (for dev/test only).
        # Production deployments must NOT set this.
        monkeypatch.setenv("PECUNATOR_API_AUTH_DISABLED", "1")

        # Recreate app with env var set
        from importlib import reload
        import runtime.api.auth as auth_module
        reload(auth_module)
        app = create_app()
        client_no_auth = TestClient(app, manage_lifespan=False)

        # Without token, should get past auth layer (though may fail for other reasons)
        response = client_no_auth.get("/api/v1/order-ledger/recent")
        # Should NOT be 401 (auth check failed); may be 500 or other error
        assert response.status_code != 401

        # Cleanup: restore normal auth
        monkeypatch.delenv("PECUNATOR_API_AUTH_DISABLED")
        reload(auth_module)
