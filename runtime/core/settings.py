"""Process configuration from environment + persistent JSON gateway settings.

The gateway_settings.json file is the single source of truth for all
polling cadences and safety thresholds. ALL values have safe defaults
and hard floors to prevent IP bans.

Incident Reference: 2 May 2026 — IP Ban (-1003).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

try:
    from dotenv import load_dotenv
    load_dotenv()  # Take environment variables from .env.
except ImportError:
    pass

_DEFAULT_RUNTIME_DIR = Path(__file__).resolve().parent.parent / "data"

_GATEWAY_SETTINGS_FILENAME = "gateway_settings.json"

# Hard floors that CANNOT be overridden by the user.
_MIN_POLL_INTERVAL_SEC = 30.0  # Never poll faster than every 30 seconds.
_MIN_FUSE_COOLDOWN_SEC = 60    # Fuse cooldown minimum 1 minute.

# Safe defaults (used if the JSON file is missing or corrupt).
_DEFAULTS: Dict[str, Any] = {
    "autostart_gateway": False,
    "poll_interval_sec": 60,
    "equity_poll_stride": 10,
    "my_trades_poll_stride": 5,
    "api_fuse_threshold_pct": 80,
    "api_fuse_cooldown_sec": 300,
}


def data_dir() -> Path:
    raw = os.environ.get("PECUNATOR_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return _DEFAULT_RUNTIME_DIR.resolve()


def _gateway_settings_path() -> Path:
    return data_dir() / _GATEWAY_SETTINGS_FILENAME


def load_gateway_settings() -> Dict[str, Any]:
    """Load gateway settings from persistent JSON. Returns safe defaults on any error."""
    path = _gateway_settings_path()
    settings = dict(_DEFAULTS)
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            if isinstance(user, dict):
                settings.update(user)
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            import logging
            logging.getLogger("pecunator.settings").warning(
                "gateway_settings.json corrupt, using defaults: %s", exc
            )
    return settings


def save_gateway_settings(settings: Dict[str, Any]) -> None:
    """Persist gateway settings to JSON (immortal across restarts)."""
    path = _gateway_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = dict(_DEFAULTS)
    merged.update(settings)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)


def api_bind_host() -> str:
    """HTTP API bind address (loopback by default)."""
    return os.environ.get("PECUNATOR_API_HOST", "127.0.0.1").strip() or "127.0.0.1"


def api_bind_port() -> int:
    """HTTP API bind port. Default 8000 (unified with Flutter UI)."""
    try:
        return int(os.environ.get("PECUNATOR_API_PORT", "8000"))
    except ValueError:
        return 8000


def api_bind_host_for_cors_regex() -> str:
    """Origins allowed for CORS (Flutter / local dev)."""
    return r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"


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


def gateway_autostart_enabled() -> bool:
    """Should the gateway auto-start when the backend boots?
    DEFAULT: False — the user MUST manually press ON."""
    s = load_gateway_settings()
    return bool(s.get("autostart_gateway", False))


def account_poll_interval_sec() -> float:
    """
    REST+polling cadence while the gateway runs.
    Hard floor: 30 seconds minimum. Default: 60 seconds.
    NEVER set this below 30s or you risk IP bans.
    """
    s = load_gateway_settings()
    raw = s.get("poll_interval_sec", 60)
    try:
        v = float(raw)
    except (ValueError, TypeError):
        return 60.0
    return max(_MIN_POLL_INTERVAL_SEC, v)


def api_weight_limit_1m_display() -> int:
    """
    Denominator for UI / monitorPesos-style occupancy (default matches Spot exchangeInfo).
    Override if Binance changes your tier or you use a different product.
    """
    raw = os.environ.get("PECUNATOR_API_WEIGHT_LIMIT_1M", "6000").strip()
    try:
        return max(1, int(raw, 10))
    except ValueError:
        return 6000


def my_trades_poll_stride() -> int:
    """How many account poll cycles between myTrades fetches.
    Higher values reduce REST weight. Default: 5 (every 5 cycles = every 5 minutes at 60s poll)."""
    s = load_gateway_settings()
    raw = s.get("my_trades_poll_stride", 5)
    try:
        n = int(raw)
    except (ValueError, TypeError):
        return 5
    return max(1, min(n, 1000))


def equity_base_asset() -> str:
    """Base asset for rolling account equity tracking."""
    return (os.environ.get("PECUNATOR_EQUITY_BASE_ASSET", "USDT").strip().upper() or "USDT")


def equity_avg_window_samples() -> int:
    """Rolling samples for equity average/high-average."""
    raw = os.environ.get("PECUNATOR_EQUITY_AVG_WINDOW", "6").strip()
    try:
        n = int(raw, 10)
    except ValueError:
        return 6
    return max(1, min(n, 300))


def equity_poll_stride() -> int:
    """
    How many account poll cycles between equity conversions (requires get_all_tickers).
    Higher values reduce REST weight significantly. Default: 10.
    """
    s = load_gateway_settings()
    raw = s.get("equity_poll_stride", 10)
    try:
        n = int(raw)
    except (ValueError, TypeError):
        return 10
    return max(1, min(n, 600))


def api_fuse_threshold_pct() -> float:
    """Weight percentage at which the API Fuse trips. Default: 80%."""
    s = load_gateway_settings()
    raw = s.get("api_fuse_threshold_pct", 80)
    try:
        v = float(raw)
    except (ValueError, TypeError):
        return 80.0
    return max(10.0, min(v, 99.0))


def api_fuse_cooldown_sec() -> int:
    """Seconds the fuse stays tripped after activation. Default: 300 (5 min)."""
    s = load_gateway_settings()
    raw = s.get("api_fuse_cooldown_sec", 300)
    try:
        v = int(raw)
    except (ValueError, TypeError):
        return 300
    return max(_MIN_FUSE_COOLDOWN_SEC, v)


# ─── Louise bot tunables ────────────────────────────────────────────
# All previously hardcoded thresholds, now overridable via environment.

def louise_price_staleness_sec() -> int:
    """Maximum age (seconds) for cached price before bot waits for fresh data."""
    raw = os.environ.get("LOUISE_PRICE_STALENESS_SEC", "15").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 15


def louise_min_usdt_balance() -> float:
    """Minimum USDT free balance required for the bot to attempt buys."""
    raw = os.environ.get("LOUISE_MIN_USDT_BALANCE", "8").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 8.0


def louise_cooldown_buy_fail_sec() -> int:
    """Cooldown (seconds) after a BUY execution failure."""
    raw = os.environ.get("LOUISE_COOLDOWN_BUY_FAIL_SEC", "300").strip()
    try:
        return max(10, int(raw))
    except ValueError:
        return 300


def louise_cooldown_gateway_fail_sec() -> int:
    """Cooldown (seconds) after a gateway-unavailable error."""
    raw = os.environ.get("LOUISE_COOLDOWN_GATEWAY_FAIL_SEC", "60").strip()
    try:
        return max(10, int(raw))
    except ValueError:
        return 60


def louise_default_subaccount() -> str:
    """Default subaccount when none is specified at bot creation."""
    return os.environ.get("LOUISE_DEFAULT_SUBACCOUNT", "bluechip").strip() or "bluechip"


def louise_default_max_position_size_usdt() -> float:
    """Default maximum position size (USDT) per epoch."""
    raw = os.environ.get("LOUISE_DEFAULT_MAX_POSITION_SIZE_USDT", "5000").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 5000.0


def louise_default_max_purchases_per_epoch() -> int:
    """Default maximum number of buy fills per epoch before force-sell."""
    raw = os.environ.get("LOUISE_DEFAULT_MAX_PURCHASES_PER_EPOCH", "20").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 20


def louise_default_max_drawdown_pct() -> float:
    """Default max drawdown percent (negative) before stop-loss triggers."""
    raw = os.environ.get("LOUISE_DEFAULT_MAX_DRAWDOWN_PCT", "-10").strip()
    try:
        return float(raw)
    except ValueError:
        return -10.0

