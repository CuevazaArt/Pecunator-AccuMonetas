"""API Governor — Unified multi-service rate limiter and quota manager.

Governs ALL external API services used by Pecunator:
  - Binance REST (weight-based, 6000/min)
  - Chart-Img (daily quota, 50/day, 1/sec rate)
  - Gemini (RPM-based, 15/min free tier)
  - OpenAI (RPM-based, 60/min)

Every outgoing call MUST request a token from the Governor first.
The Governor tracks consumption, enforces rate limits, and logs
every request for forensic analysis.

Priority tiers (for budget allocation):
  P0: Trading operations (40%)
  P1: Market diagnosis / VMO (25%)
  P2: Account monitoring (15%)
  P3: Emergency reserve (10%)
  P4: Data collection / klines (10%)

Incident Reference: 2 May 2026 — Binance IP Ban (-1003).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from runtime.core.db_util import open_db
from runtime.core.exception_zoo import get_exception_zoo

_LOG = logging.getLogger("pecunator.core.api_governor")

# Priority levels
P_TRADING = 0
P_DIAGNOSIS = 1
P_MONITORING = 2
P_EMERGENCY = 3
P_COLLECTION = 4


@dataclass
class ServiceConfig:
    """Configuration for a governed API service."""
    name: str
    limit_type: str          # "weight" | "daily" | "rpm"
    limit_value: int         # Max units per window
    window_seconds: int      # Window duration
    rate_limit_sec: float    # Min seconds between calls (0 = unlimited)
    budget_pct: float = 1.0  # What fraction of limit to actually use (safety margin)
    enabled: bool = True


# Default service configurations
_DEFAULT_SERVICES: dict[str, ServiceConfig] = {
    "binance": ServiceConfig(
        name="binance", limit_type="weight",
        limit_value=6000, window_seconds=60,
        rate_limit_sec=0, budget_pct=0.70,
    ),
    "chart-img": ServiceConfig(
        name="chart-img", limit_type="daily",
        limit_value=50, window_seconds=86400,
        rate_limit_sec=1.0, budget_pct=0.90,
    ),
    "gemini": ServiceConfig(
        name="gemini", limit_type="rpm",
        limit_value=15, window_seconds=60,
        rate_limit_sec=4.5, budget_pct=0.80,
    ),
    "openai": ServiceConfig(
        name="openai", limit_type="rpm",
        limit_value=60, window_seconds=60,
        rate_limit_sec=1.0, budget_pct=0.80,
    ),
}

_DDL = """\
CREATE TABLE IF NOT EXISTS api_usage_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc      TEXT    NOT NULL,
    service     TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    caller      TEXT    NOT NULL DEFAULT '',
    priority    INTEGER NOT NULL DEFAULT 1,
    units_used  INTEGER NOT NULL DEFAULT 1,
    latency_ms  INTEGER,
    success     INTEGER NOT NULL DEFAULT 1,
    error_type  TEXT,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_api_usage_ts ON api_usage_log(ts_utc);
CREATE INDEX IF NOT EXISTS idx_api_usage_svc ON api_usage_log(service, ts_utc);

CREATE TABLE IF NOT EXISTS api_daily_counters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date_utc    TEXT    NOT NULL,
    service     TEXT    NOT NULL,
    total_calls INTEGER NOT NULL DEFAULT 0,
    total_units INTEGER NOT NULL DEFAULT 0,
    errors      INTEGER NOT NULL DEFAULT 0,
    UNIQUE(date_utc, service)
);
"""


class ApiGovernor:
    """Central governor for all external API consumption."""

    def __init__(
        self,
        db_path: Path,
        services: Optional[dict[str, ServiceConfig]] = None,
    ) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._services = services or dict(_DEFAULT_SERVICES)
        self._lock = threading.Lock()

        # Per-service tracking
        self._last_call_ts: dict[str, float] = {}
        self._window_usage: dict[str, list[tuple[float, int]]] = {}
        self._daily_usage: dict[str, int] = {}
        self._daily_date: str = ""

        self._init_schema()
        self._reset_daily_if_needed()

    def _init_schema(self) -> None:
        conn = open_db(self._path)
        try:
            conn.executescript(_DDL)
        finally:
            conn.close()

    def _reset_daily_if_needed(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._daily_date != today:
            self._daily_date = today
            self._daily_usage = {}

    # ── Token Request ───────────────────────────────────────────────

    def request_token(
        self,
        service: str,
        units: int = 1,
        priority: int = P_DIAGNOSIS,
        caller: str = "",
    ) -> tuple[bool, float]:
        """Request permission to call a service.

        Returns:
            (allowed, wait_seconds)
            allowed=True → proceed immediately
            allowed=False, wait>0 → wait this many seconds then retry
            allowed=False, wait=float('inf') → budget exhausted, do NOT call
        """
        with self._lock:
            cfg = self._services.get(service)
            if cfg is None or not cfg.enabled:
                return True, 0.0  # Unknown service — allow (legacy compat)

            self._reset_daily_if_needed()
            now = time.monotonic()

            # Check rate limit (min seconds between calls)
            if cfg.rate_limit_sec > 0:
                last = self._last_call_ts.get(service, 0.0)
                elapsed = now - last
                if elapsed < cfg.rate_limit_sec:
                    return False, cfg.rate_limit_sec - elapsed

            # Check quota
            effective_limit = int(cfg.limit_value * cfg.budget_pct)

            if cfg.limit_type == "daily":
                used_today = self._daily_usage.get(service, 0)
                if used_today + units > effective_limit:
                    _LOG.warning(
                        "API Governor DENIED %s (daily %d/%d exhausted, caller=%s)",
                        service, used_today, effective_limit, caller,
                    )
                    return False, float('inf')

            elif cfg.limit_type in ("rpm", "weight"):
                # Sliding window check
                window = self._window_usage.get(service, [])
                cutoff = now - cfg.window_seconds
                window = [(ts, u) for ts, u in window if ts > cutoff]
                self._window_usage[service] = window
                current = sum(u for _, u in window)
                if current + units > effective_limit:
                    # Calculate when oldest entry expires
                    if window:
                        wait = window[0][0] + cfg.window_seconds - now
                        return False, max(0.1, wait)
                    return False, float(cfg.window_seconds)

            return True, 0.0

    def record_usage(
        self,
        service: str,
        action: str = "",
        units: int = 1,
        priority: int = P_DIAGNOSIS,
        caller: str = "",
        latency_ms: int = 0,
        success: bool = True,
        error_type: str = "",
        note: str = "",
    ) -> None:
        """Record that a call was made (MUST be called after every API interaction)."""
        now_mono = time.monotonic()
        now_utc = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._last_call_ts[service] = now_mono

            # Update sliding window
            window = self._window_usage.get(service, [])
            window.append((now_mono, units))
            self._window_usage[service] = window

            # Update daily counter
            self._reset_daily_if_needed()
            self._daily_usage[service] = self._daily_usage.get(service, 0) + units

        # Persist to DB (outside lock for performance)
        try:
            conn = open_db(self._path)
            try:
                conn.execute(
                    """
                    INSERT INTO api_usage_log
                        (ts_utc, service, action, caller, priority,
                         units_used, latency_ms, success, error_type, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        now_utc, service[:30], action[:120],
                        caller[:60], priority, units,
                        latency_ms, 1 if success else 0,
                        error_type[:120] if error_type else None,
                        note[:250] if note else None,
                    ),
                )
                # Update daily counter table
                conn.execute(
                    """
                    INSERT INTO api_daily_counters (date_utc, service, total_calls, total_units, errors)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT(date_utc, service)
                    DO UPDATE SET
                        total_calls = total_calls + 1,
                        total_units = total_units + excluded.total_units,
                        errors = errors + excluded.errors
                    """,
                    (
                        self._daily_date, service[:30], units,
                        0 if success else 1,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            zoo = get_exception_zoo()
            zoo.register(exc, module="api_governor", context=f"record_usage:{service}")

    # ── Status ──────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return governor status for all services."""
        with self._lock:
            self._reset_daily_if_needed()
            now = time.monotonic()
            result = {}
            for name, cfg in self._services.items():
                if cfg.limit_type == "daily":
                    used = self._daily_usage.get(name, 0)
                    limit = int(cfg.limit_value * cfg.budget_pct)
                    remaining = max(0, limit - used)
                elif cfg.limit_type in ("rpm", "weight"):
                    window = self._window_usage.get(name, [])
                    cutoff = now - cfg.window_seconds
                    window = [(ts, u) for ts, u in window if ts > cutoff]
                    used = sum(u for _, u in window)
                    limit = int(cfg.limit_value * cfg.budget_pct)
                    remaining = max(0, limit - used)
                else:
                    used, limit, remaining = 0, 0, 0

                result[name] = {
                    "type": cfg.limit_type,
                    "used": used,
                    "limit": limit,
                    "remaining": remaining,
                    "pct_used": round((used / limit) * 100, 1) if limit > 0 else 0,
                    "enabled": cfg.enabled,
                    "rate_limit_sec": cfg.rate_limit_sec,
                }
            return result

    def daily_report(self) -> list[dict[str, Any]]:
        """Return today's usage by service."""
        conn = open_db(self._path)
        try:
            conn.row_factory = sqlite3.Row
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            rows = conn.execute(
                "SELECT * FROM api_daily_counters WHERE date_utc = ?",
                (today,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def purge_old_logs(self, days: int = 30) -> int:
        """Delete usage logs older than N days. Returns rows deleted."""
        conn = open_db(self._path)
        try:
            cur = conn.execute(
                "DELETE FROM api_usage_log WHERE ts_utc < datetime('now', ?)",
                (f"-{days} days",),
            )
            conn.commit()
            _LOG.info("Purged %d old API usage log entries (>%d days)", cur.rowcount, days)
            return cur.rowcount
        finally:
            conn.close()


# ── Singleton ───────────────────────────────────────────────────────

_governor: Optional[ApiGovernor] = None


def get_api_governor(data_dir: Optional[Path] = None) -> ApiGovernor:
    global _governor
    if _governor is None:
        d = data_dir or Path("runtime/data")
        _governor = ApiGovernor(Path(d) / "api_governor.sqlite")
    return _governor
