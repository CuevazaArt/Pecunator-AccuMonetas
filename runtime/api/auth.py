"""Local API bearer token authentication.

On first boot, generates a 32-byte random token and persists it to
``runtime/data/api.token``.  All API endpoints validate this token
via the ``verify_token`` dependency.

The Flutter client reads the token file directly from the filesystem
(same machine), avoiding the need to pass api_key/api_secret in bodies.
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from runtime.core.settings import data_dir

_LOG = logging.getLogger("pecunator.api.auth")
_TOKEN_FILENAME = "api.token"
_cached_token: Optional[str] = None

_security = HTTPBearer(auto_error=False)


def _token_path() -> Path:
    return data_dir() / _TOKEN_FILENAME


def _ensure_token() -> str:
    """Return the API token, creating it on first run."""
    global _cached_token
    if _cached_token is not None:
        return _cached_token

    path = _token_path()
    if path.is_file():
        _cached_token = path.read_text(encoding="utf-8").strip()
        if _cached_token:
            return _cached_token

    # Generate fresh token
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")

    # Best-effort chmod 600 on POSIX
    try:
        os.chmod(path, 0o600)
    except (OSError, AttributeError):
        pass

    _LOG.info("api.token generated at %s", path)
    _cached_token = token
    return token


def get_api_token() -> str:
    """Public accessor for the current token value (used by tests/tools)."""
    return _ensure_token()


async def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> None:
    """FastAPI dependency: reject requests without a valid bearer token.

    Exemptions:
        - ``/docs``, ``/openapi.json``, ``/redoc`` (dev tools)
        - ``/health`` (uptime monitoring)
        - If ``PECUNATOR_API_AUTH_DISABLED=1`` (dev/testing only)
    """
    # Dev override
    if os.environ.get("PECUNATOR_API_AUTH_DISABLED", "").strip() in ("1", "true"):
        return

    # Exempt documentation and health endpoints
    path = request.url.path
    if path in ("/docs", "/openapi.json", "/redoc", "/health"):
        return

    expected = _ensure_token()

    # Check Bearer header
    if credentials and credentials.credentials == expected:
        return

    # Fallback: check X-Api-Token header (for non-browser clients)
    header_token = request.headers.get("x-api-token", "").strip()
    if header_token == expected:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API token. Read runtime/data/api.token.",
    )
