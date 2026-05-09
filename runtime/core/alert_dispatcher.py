"""M3: Alert Dispatcher — centralized alert system for critical events.

Publishes alerts to configured channels. Phase 1: log file + console.
Future: Telegram webhook via PECUNATOR_ALERT_TELEGRAM_TOKEN env var.

Usage:
    from runtime.core.alert_dispatcher import get_alert_dispatcher
    get_alert_dispatcher().critical("FUSE_TRIPPED", "API weight at 95%")
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.core.alerts")


class AlertDispatcher:
    """Dispatches critical alerts to configured channels."""

    # Alert severity levels
    CRITICAL = "CRITICAL"  # Fuse trip, orphan detected, hub pause
    WARNING = "WARNING"    # High weight, recovery attempt
    INFO = "INFO"          # Successful recovery, rebalance

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._alerts: list[dict[str, Any]] = []
        self._max_history = 100
        self._data_dir = data_dir
        self._alert_log_path: Optional[Path] = None
        if data_dir:
            self._alert_log_path = Path(data_dir) / "alerts.log"

    def _write_to_file(self, level: str, code: str, message: str) -> None:
        if not self._alert_log_path:
            return
        try:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            line = f"{ts} [{level}] {code}: {message}\n"
            with open(self._alert_log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _dispatch(self, level: str, code: str, message: str, payload: Optional[dict] = None) -> dict[str, Any]:
        ts_utc = datetime.now(timezone.utc).isoformat()
        alert = {
            "level": level,
            "code": code,
            "message": message,
            "ts_utc": ts_utc,
            "ts_mono": time.monotonic(),
            "payload": payload,
        }

        # Store in memory
        self._alerts.append(alert)
        if len(self._alerts) > self._max_history:
            self._alerts = self._alerts[-self._max_history:]

        # Log to Python logger
        log_msg = f"🚨 ALERT [{level}] {code}: {message}"
        if level == self.CRITICAL:
            _LOG.critical(log_msg)
        elif level == self.WARNING:
            _LOG.warning(log_msg)
        else:
            _LOG.info(log_msg)

        # Write to dedicated alert log file
        self._write_to_file(level, code, message)

        return alert

    def critical(self, code: str, message: str, payload: Optional[dict] = None) -> dict[str, Any]:
        """Dispatch a CRITICAL alert — fuse trips, orphans, hub pauses."""
        return self._dispatch(self.CRITICAL, code, message, payload)

    def warning(self, code: str, message: str, payload: Optional[dict] = None) -> dict[str, Any]:
        """Dispatch a WARNING alert — high weight, recovery attempts."""
        return self._dispatch(self.WARNING, code, message, payload)

    def info(self, code: str, message: str, payload: Optional[dict] = None) -> dict[str, Any]:
        """Dispatch an INFO alert — successful recoveries."""
        return self._dispatch(self.INFO, code, message, payload)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent alerts, newest first."""
        return list(reversed(self._alerts[-limit:]))

    def status(self) -> dict[str, Any]:
        """Summary for API/UI consumption."""
        criticals = sum(1 for a in self._alerts if a["level"] == self.CRITICAL)
        return {
            "total_alerts": len(self._alerts),
            "critical_count": criticals,
            "last_alert": self._alerts[-1] if self._alerts else None,
            "alert_log_path": str(self._alert_log_path) if self._alert_log_path else None,
        }


# ── Singleton ───────────────────────────────────────────────────────

_dispatcher: Optional[AlertDispatcher] = None


def get_alert_dispatcher(data_dir: Optional[Path | str] = None) -> AlertDispatcher:
    """Get or create the global AlertDispatcher singleton."""
    global _dispatcher
    if _dispatcher is None:
        if data_dir is None:
            try:
                from runtime.core.settings import data_dir as _data_dir
                data_dir = _data_dir()
            except Exception:
                pass
        _dispatcher = AlertDispatcher(Path(data_dir) if data_dir else None)
    return _dispatcher
