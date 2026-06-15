"""HTTP client for the Pecunator engine REST API."""

from __future__ import annotations

import sys
from typing import Any

import httpx

from cli.config import get_api_url, get_api_token


class EngineError(Exception):
    """Raised when the engine returns an error response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


class LouiseClient:
    """Synchronous HTTP client that talks to the local Pecunator engine API.

    Auto-reads the bearer token from the filesystem or environment.
    """

    def __init__(self, *, base_url: str | None = None, token: str | None = None, timeout: float = 10.0):
        self._base = base_url or get_api_url()
        self._token = token or get_api_token()
        self._timeout = timeout

    # ── Internal helpers ──────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Accept": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Execute an HTTP request and return parsed JSON."""
        url = f"{self._base}{path}"
        try:
            resp = httpx.request(
                method,
                url,
                headers=self._headers(),
                timeout=self._timeout,
                **kwargs,
            )
        except httpx.ConnectError:
            print(
                f"\n  ✗ Cannot connect to engine at {self._base}\n"
                f"    Is the engine running? Start it with: python -m cli engine start\n",
                file=sys.stderr,
            )
            raise SystemExit(1)
        except httpx.TimeoutException:
            print(
                f"\n  ✗ Request timed out ({self._timeout}s) to {url}\n",
                file=sys.stderr,
            )
            raise SystemExit(1)

        if resp.status_code >= 400:
            detail = resp.text
            try:
                body = resp.json()
                detail = body.get("detail", resp.text)
            except Exception:
                pass
            raise EngineError(resp.status_code, detail)

        if resp.status_code == 204:
            return None
        return resp.json()

    def get(self, path: str, **params: Any) -> Any:
        return self._request("GET", path, params=params or None)

    def post(self, path: str, json: Any = None) -> Any:
        return self._request("POST", path, json=json)

    def patch(self, path: str, json: Any = None) -> Any:
        return self._request("PATCH", path, json=json)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    # ── Louise Bot endpoints ──────────────────────────────────────────

    def bot_list(self) -> list[dict[str, Any]]:
        return self.get("/api/louise/bots")

    def bot_create(self, **kwargs: Any) -> dict[str, Any]:
        return self.post("/api/louise/bots", json=kwargs)

    def bot_pause(self, bot_id: str) -> dict[str, Any]:
        return self.post(f"/api/louise/bots/{bot_id}/pause")

    def bot_resume(self, bot_id: str) -> dict[str, Any]:
        return self.post(f"/api/louise/bots/{bot_id}/resume")

    def bot_update(self, bot_id: str, **kwargs: Any) -> dict[str, Any]:
        # Remove None values — PATCH is partial
        payload = {k: v for k, v in kwargs.items() if v is not None}
        return self.patch(f"/api/louise/bots/{bot_id}", json=payload)

    def bot_delete(self, bot_id: str) -> dict[str, Any]:
        return self.delete(f"/api/louise/bots/{bot_id}")

    def bot_pnl_history(self, bot_id: str, limit: int = 2000) -> dict[str, Any]:
        return self.get(f"/api/louise/bots/{bot_id}/pnl-history", limit=limit)

    def bot_purchases(self, bot_id: str, limit: int = 1000) -> dict[str, Any]:
        return self.get(f"/api/louise/bots/{bot_id}/purchases", limit=limit)

    # ── Hub endpoints ─────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        return self.get("/api/louise/health")

    def metrics(self) -> dict[str, Any]:
        return self.get("/api/louise/metrics")

    def weight_status(self) -> dict[str, Any]:
        return self.get("/api/louise/weight-governor/status")

    def hub_combined_pnl(self, limit: int = 4000) -> dict[str, Any]:
        return self.get("/api/louise/hub/combined-pnl", limit=limit)

    def hub_dual_state(self) -> dict[str, Any]:
        return self.get("/api/louise/hub/dual-state")

    def hub_notify(self) -> dict[str, Any]:
        return self.post("/api/louise/notify")

    # ── Gateway endpoints ─────────────────────────────────────────────

    def gateway_snapshot(self) -> dict[str, Any]:
        return self.get("/api/gateway/snapshot")

    def gateway_start(self, api_key: str | None = None, api_secret: str | None = None) -> dict[str, Any]:
        payload: dict[str, str] = {}
        if api_key:
            payload["api_key"] = api_key
        if api_secret:
            payload["api_secret"] = api_secret
        return self.post("/api/gateway/start", json=payload or None)

    def gateway_stop(self) -> dict[str, Any]:
        return self.post("/api/gateway/stop")

    # ── Vault endpoints ───────────────────────────────────────────────

    def vault_status(self) -> dict[str, Any]:
        return self.get("/api/vault/status")

    def vault_credentials(self) -> list[dict[str, Any]]:
        return self.get("/api/vault/credentials")

    def vault_add_credential(self, api_key: str, api_secret: str, label: str | None = None) -> dict[str, Any]:
        payload: dict[str, str] = {"api_key": api_key, "api_secret": api_secret}
        if label:
            payload["label"] = label
        return self.post("/api/vault/credentials", json=payload)
