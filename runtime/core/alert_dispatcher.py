"""M3: Alert Dispatcher — centralized alert system for critical events.

Publishes alerts to multiple channels: file, console, Telegram, email.
Implements deduplication, retry logic, and startup validation.

Usage:
    from runtime.core.alert_dispatcher import get_alert_dispatcher
    get_alert_dispatcher().critical("FUSE_TRIPPED", "API weight at 95%")
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.core.alerts")


class AlertDispatcher:
    """Dispatches critical alerts to configured channels with deduplication and retry."""

    # Alert severity levels
    CRITICAL = "CRITICAL"  # Fuse trip, orphan detected, hub pause
    WARNING = "WARNING"    # High weight, recovery attempt
    INFO = "INFO"          # Successful recovery, rebalance

    # Deduplication window (seconds) — don't send same alert twice within this period
    DEDUP_WINDOW = 300

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._alerts: list[dict[str, Any]] = []
        self._max_history = 100
        self._data_dir = data_dir
        self._alert_log_path: Optional[Path] = None
        if data_dir:
            self._alert_log_path = Path(data_dir) / "alerts.log"

        # Deduplication tracking: {alert_key: last_sent_timestamp}
        self._dedup_cache: dict[str, float] = {}

        # Telegram config
        self._telegram_token = os.environ.get("PECUNATOR_ALERT_TELEGRAM_TOKEN", "").strip()
        self._telegram_chat_id = os.environ.get("PECUNATOR_ALERT_TELEGRAM_CHAT_ID", "").strip()

        # Email config (optional)
        self._email_enabled = os.environ.get("PECUNATOR_ALERT_EMAIL_ENABLED", "").lower() == "1"
        self._email_smtp_host = os.environ.get("PECUNATOR_ALERT_EMAIL_SMTP_HOST", "")
        self._email_smtp_port = int(os.environ.get("PECUNATOR_ALERT_EMAIL_SMTP_PORT", "587"))
        self._email_from = os.environ.get("PECUNATOR_ALERT_EMAIL_FROM", "")
        self._email_to = os.environ.get("PECUNATOR_ALERT_EMAIL_TO", "")
        self._email_password = os.environ.get("PECUNATOR_ALERT_EMAIL_PASSWORD", "")

        # Validate config on startup
        self._validate_config()

    def _validate_config(self) -> None:
        """Warn if telegram or email configured incorrectly."""
        if self._telegram_token and not self._telegram_chat_id:
            _LOG.warning("PECUNATOR_ALERT_TELEGRAM_TOKEN set but "
                        "PECUNATOR_ALERT_TELEGRAM_CHAT_ID missing — "
                        "Telegram alerts disabled")
        if not self._telegram_token and self._telegram_chat_id:
            _LOG.warning("PECUNATOR_ALERT_TELEGRAM_CHAT_ID set but "
                        "PECUNATOR_ALERT_TELEGRAM_TOKEN missing — "
                        "Telegram alerts disabled")
        if self._email_enabled and not all(
            [self._email_smtp_host, self._email_from, self._email_to,
             self._email_password]
        ):
            _LOG.warning("Email alerts enabled but "
                        "PECUNATOR_ALERT_EMAIL_* vars incomplete — "
                        "Email alerts disabled")
        if self._telegram_token and self._telegram_chat_id:
            _LOG.info("Telegram alerts enabled (chat_id=%s...)", self._telegram_chat_id[:8])
        if self._email_enabled and all([self._email_smtp_host, self._email_from, self._email_to]):
            _LOG.info("Email alerts enabled (to=%s)", self._email_to)

    def _should_dedup(self, code: str, level: str) -> bool:
        """Check if alert should be deduplicated (sent too recently)."""
        key = f"{level}:{code}"
        last_sent = self._dedup_cache.get(key, 0)
        if time.time() - last_sent < self.DEDUP_WINDOW:
            return True
        self._dedup_cache[key] = time.time()
        return False

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

    def _send_telegram_async(self, text: str) -> None:
        """Send Telegram alert with retry logic (3 attempts, 2s backoff)."""
        if not self._telegram_token or not self._telegram_chat_id:
            return

        def _post_with_retry() -> None:
            import httpx
            url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
            payload = {"chat_id": self._telegram_chat_id, "text": text}

            for attempt in range(3):
                try:
                    with httpx.Client(timeout=5) as client:
                        resp = client.post(url, json=payload)
                        if resp.status_code == 200:
                            return
                        elif resp.status_code == 429:
                            # Rate limited, wait and retry
                            retry_after = int(resp.headers.get("Retry-After", 2))
                            _LOG.warning("Telegram rate limited, retry after %ds", retry_after)
                            time.sleep(retry_after)
                        else:
                            _LOG.warning("Telegram API error %d: %s", resp.status_code, resp.text[:100])
                            break
                except Exception as e:
                    _LOG.warning("Telegram send attempt %d failed: %s", attempt + 1, e)
                    if attempt < 2:
                        time.sleep(2 ** (attempt + 1))  # Exponential backoff: 2s, 4s
                    continue

        threading.Thread(target=_post_with_retry, daemon=True).start()

    def _send_email_async(self, level: str, code: str, message: str) -> None:
        """Send email alert (async, non-blocking)."""
        if not self._email_enabled:
            return
        if not all([self._email_smtp_host, self._email_from, self._email_to, self._email_password]):
            return

        def _send() -> None:
            try:
                import smtplib
                from email.mime.text import MIMEText

                subject = f"[{level}] Pecunator Alert: {code}"
                body = f"{message}\n\nSent: {datetime.now(timezone.utc).isoformat()}"
                msg = MIMEText(body)
                msg["Subject"] = subject
                msg["From"] = self._email_from
                msg["To"] = self._email_to

                with smtplib.SMTP(self._email_smtp_host, self._email_smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(self._email_from, self._email_password)
                    server.send_message(msg)
            except Exception as e:
                _LOG.warning("Failed to send email alert: %s", e)

        threading.Thread(target=_send, daemon=True).start()

    def _dispatch(
        self,
        level: str,
        code: str,
        message: str,
        payload: Optional[dict] = None,
        silent: bool = False
    ) -> dict[str, Any]:
        ts_utc = datetime.now(timezone.utc).isoformat()
        alert = {
            "level": level,
            "code": code,
            "message": message,
            "ts_utc": ts_utc,
            "ts_mono": time.monotonic(),
            "payload": payload,
            "silent": silent,
        }

        # Store in memory
        self._alerts.append(alert)
        if len(self._alerts) > self._max_history:
            self._alerts = self._alerts[-self._max_history:]

        # Log to Python logger (always)
        log_msg = f"🚨 ALERT [{level}] {code}: {message}"
        if level == self.CRITICAL:
            _LOG.critical(log_msg)
        elif level == self.WARNING:
            _LOG.warning(log_msg)
        else:
            _LOG.info(log_msg)

        # Write to dedicated alert log file (always)
        self._write_to_file(level, code, message)

        # Skip external channels if silent (expected condition, don't alert)
        if silent:
            return alert

        # Check deduplication — skip if same alert sent recently
        if self._should_dedup(code, level):
            _LOG.debug("Alert %s:%s deduplicated (sent < %ds ago)", level, code, self.DEDUP_WINDOW)
            return alert

        # Dispatch to external channels
        formatted_msg = f"[{level}] {code}\n{message}"
        self._send_telegram_async(formatted_msg)
        self._send_email_async(level, code, message)

        return alert

    def critical(self, code: str, message: str, payload: Optional[dict] = None, silent: bool = False) -> dict[str, Any]:
        """Dispatch a CRITICAL alert — fuse trips, orphans, hub pauses."""
        return self._dispatch(self.CRITICAL, code, message, payload, silent=silent)

    def warning(self, code: str, message: str, payload: Optional[dict] = None, silent: bool = False) -> dict[str, Any]:
        """Dispatch a WARNING alert — high weight, recovery attempts."""
        return self._dispatch(self.WARNING, code, message, payload, silent=silent)

    def info(self, code: str, message: str, payload: Optional[dict] = None, silent: bool = False) -> dict[str, Any]:
        """Dispatch an INFO alert — successful recoveries."""
        return self._dispatch(self.INFO, code, message, payload, silent=silent)

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
