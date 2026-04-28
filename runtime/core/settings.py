"""Process configuration from environment (no secrets defaulted here)."""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_RUNTIME_DIR = Path(__file__).resolve().parent.parent / "data"


def data_dir() -> Path:
    raw = os.environ.get("PECUNATOR_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_RUNTIME_DIR.resolve()


def http_host() -> str:
    """Bind address for NiceGUI. Default loopback; set PECUNATOR_HOST only if you accept LAN exposure."""
    return os.environ.get("PECUNATOR_HOST", "127.0.0.1").strip() or "127.0.0.1"


def http_port() -> int:
    try:
        return int(os.environ.get("PECUNATOR_PORT", "8080"))
    except ValueError:
        return 8080


def binance_credentials_from_env() -> tuple[str, str] | None:
    """
    Optional non-interactive bootstrap. Keys live in the process environment only.
    Prefer the encrypted vault for daily use.
    """
    key = os.environ.get("PECUNATOR_BINANCE_API_KEY", "").strip()
    sec = os.environ.get("PECUNATOR_BINANCE_API_SECRET", "").strip()
    if key and sec:
        return key, sec
    return None
