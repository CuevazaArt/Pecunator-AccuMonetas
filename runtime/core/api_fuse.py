"""API Fuse — Thermal circuit breaker for Binance REST API weight protection.

If the used weight exceeds the configured threshold (default 80%) or any
ban/rate-limit error code is received, the fuse TRIPS and blocks ALL outgoing
REST API calls for a configurable cooldown period (default 5 minutes).

This module is the single source of truth for "should we allow a REST call?"
across the entire PecunatorCore system.

Incident Reference: 2 May 2026 — IP Ban (-1003) caused by unchecked polling.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

_LOG = logging.getLogger("pecunator.core.api_fuse")

# Error codes that trigger an IMMEDIATE fuse trip.
_FATAL_CODES = {-1003, 429, 418, -1015}


class ApiFuse:
    """Global thermal circuit breaker for Binance REST API calls."""

    def __init__(
        self,
        threshold_pct: float = 80.0,
        cooldown_sec: int = 300,
        weight_limit: int = 6000,
    ) -> None:
        self.threshold_pct = max(10.0, min(threshold_pct, 99.0))
        self.cooldown_sec = max(30, cooldown_sec)
        self.weight_limit = max(1, weight_limit)
        self._tripped = False
        self._tripped_at: float = 0.0
        self._trip_reason: str = ""
        self._trip_count: int = 0
        self._lock = threading.Lock()

    # ── Public API ──────────────────────────────────────────────────

    def check_weight(self, used_weight: int) -> bool:
        """Evaluate current weight and trip if above threshold.

        Returns True if the fuse just tripped (or was already tripped).
        """
        if used_weight <= 0:
            return self.is_tripped()
        pct = (used_weight / self.weight_limit) * 100
        if pct >= self.threshold_pct:
            reason = (
                f"Peso API al {pct:.1f}% ({used_weight}/{self.weight_limit}). "
                f"Umbral: {self.threshold_pct}%"
            )
            self._trip(reason)
            return True
        return self.is_tripped()

    def on_error_code(self, code: int, message: str = "") -> bool:
        """If we receive a fatal error code, trip IMMEDIATELY.

        Returns True if the fuse tripped.
        """
        code_i = int(code) if code else 0
        if code_i in _FATAL_CODES:
            reason = f"Error critico Binance: code={code_i} msg={message[:200]}"
            self._trip(reason)
            return True
        return False

    def is_tripped(self) -> bool:
        """Is the fuse currently blocking all REST calls?

        Automatically resets after the cooldown period elapses.
        """
        with self._lock:
            if not self._tripped:
                return False
            elapsed = time.monotonic() - self._tripped_at
            if elapsed >= self.cooldown_sec:
                _LOG.info(
                    "API Fuse auto-reset after %.0fs cooldown (trip #%d: %s)",
                    elapsed,
                    self._trip_count,
                    self._trip_reason,
                )
                self._tripped = False
                return False
            return True

    def remaining_cooldown_sec(self) -> float:
        """Seconds remaining until the fuse auto-resets. 0 if not tripped."""
        with self._lock:
            if not self._tripped:
                return 0.0
            return max(0.0, self.cooldown_sec - (time.monotonic() - self._tripped_at))

    def manual_reset(self) -> None:
        """Force-reset the fuse (use with extreme caution)."""
        with self._lock:
            self._tripped = False
            _LOG.warning("API Fuse manually reset by operator.")

    def status(self) -> dict:
        """Return fuse status for UI / API consumption."""
        with self._lock:
            remaining = 0.0
            if self._tripped:
                remaining = max(
                    0.0, self.cooldown_sec - (time.monotonic() - self._tripped_at)
                )
            return {
                "tripped": self._tripped,
                "reason": self._trip_reason if self._tripped else "",
                "remaining_sec": round(remaining, 1),
                "trip_count": self._trip_count,
                "threshold_pct": self.threshold_pct,
                "cooldown_sec": self.cooldown_sec,
                "weight_limit": self.weight_limit,
            }

    # ── Internal ────────────────────────────────────────────────────

    def _trip(self, reason: str) -> None:
        with self._lock:
            if self._tripped:
                return  # Already tripped, don't reset the timer.
            self._tripped = True
            self._tripped_at = time.monotonic()
            self._trip_reason = reason
            self._trip_count += 1
        _LOG.critical(
            "🚨 API FUSE TRIPPED (#%d): %s — ALL REST CALLS BLOCKED FOR %ds",
            self._trip_count,
            reason,
            self.cooldown_sec,
        )


# ── Singleton ───────────────────────────────────────────────────────

_fuse: Optional[ApiFuse] = None


def get_api_fuse(
    threshold_pct: float = 80.0,
    cooldown_sec: int = 300,
    weight_limit: int = 6000,
) -> ApiFuse:
    """Get or create the global API Fuse singleton."""
    global _fuse
    if _fuse is None:
        _fuse = ApiFuse(
            threshold_pct=threshold_pct,
            cooldown_sec=cooldown_sec,
            weight_limit=weight_limit,
        )
    return _fuse
