"""API Fuse — Thermal circuit breaker for Binance REST API weight protection.

If the used weight exceeds the configured threshold (default 80%) or any
ban/rate-limit error code is received, the fuse TRIPS and blocks ALL outgoing
REST API calls for a configurable cooldown period (default 5 minutes).

Backoff Escalation (the key safety feature):
    If the weight is STILL high when the fuse resets, or if it trips again
    within a short window after the previous reset, the cooldown DOUBLES
    on each consecutive trip. This prevents the "reset → immediate re-trip"
    loop that can still lead to IP bans.

    Trip #1 → base_cooldown     (e.g. 300s = 5 min)
    Trip #2 → 600s              (10 min, if re-tripped within grace window)
    Trip #3 → 1200s             (20 min)
    ...
    Trip #N → max_cooldown_sec  (default 3600s = 1 hour ceiling)

    The streak counter resets if the fuse was clear for > grace_window_sec
    (default 120s = 2 min) before the next trip.

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

# How long after a reset before we consider the next trip a "fresh" incident
# (streak counter resets). If re-tripped within this window, streak escalates.
_GRACE_WINDOW_SEC = 120.0


class ApiFuse:
    """Global thermal circuit breaker with exponential backoff for Binance REST."""

    def __init__(
        self,
        threshold_pct: float = 80.0,
        cooldown_sec: int = 300,
        weight_limit: int = 6000,
        max_cooldown_sec: int = 3600,
    ) -> None:
        self.threshold_pct = max(10.0, min(threshold_pct, 99.0))
        self.base_cooldown_sec = max(30, cooldown_sec)
        self.weight_limit = max(1, weight_limit)
        self.max_cooldown_sec = max(self.base_cooldown_sec, max_cooldown_sec)

        self._tripped = False
        self._tripped_at: float = 0.0
        self._reset_at: float = 0.0          # When the fuse last auto-reset
        self._current_cooldown: int = self.base_cooldown_sec
        self._trip_reason: str = ""
        self._trip_count: int = 0            # Total lifetime trip count
        self._consecutive_streak: int = 0   # Trips in the current escalation run
        self._lock = threading.Lock()

    # ── Public API ──────────────────────────────────────────────────

    def check_weight(self, used_weight: int) -> bool:
        """Evaluate current weight. If ≥ threshold, trip (with backoff escalation).

        IMPORTANT: also called immediately after a fuse reset to detect
        "still high" conditions BEFORE allowing the first REST call.

        Returns True if fuse is (or just became) tripped.
        """
        if used_weight <= 0:
            # Endpoint didn't return weight header — can't evaluate.
            # Return current trip state without re-evaluating thresholds.
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
        """If we receive a fatal error code, trip IMMEDIATELY (max escalation).

        Returns True if the fuse tripped.
        """
        code_i = int(code) if code else 0
        if code_i in _FATAL_CODES:
            reason = f"Error critico Binance: code={code_i} msg={message[:200]}"
            # Fatal errors jump straight to max cooldown regardless of streak.
            self._trip(reason, force_max=True)
            return True
        return False

    def is_tripped(self) -> bool:
        """Is the fuse currently blocking all REST calls?

        Automatically resets after the current cooldown period elapses.
        After reset, consecutive trip count is preserved until grace window passes.
        """
        with self._lock:
            if not self._tripped:
                return False
            elapsed = time.monotonic() - self._tripped_at
            if elapsed >= self._current_cooldown:
                self._reset_at = time.monotonic()
                self._tripped = False
                _LOG.info(
                    "API Fuse auto-reset after %.0fs cooldown "
                    "(trip #%d, streak=%d, next_cooldown_if_retripped=%ds): %s",
                    elapsed,
                    self._trip_count,
                    self._consecutive_streak,
                    self._next_escalated_cooldown(),
                    self._trip_reason,
                )
                try:
                    from runtime.core.alert_dispatcher import get_alert_dispatcher
                    get_alert_dispatcher().info("FUSE_RESET", f"Auto-reset after {elapsed:.0f}s (trip #{self._trip_count})")
                except Exception:
                    pass
                return False
            return True

    def remaining_cooldown_sec(self) -> float:
        """Seconds remaining until the fuse auto-resets. 0 if not tripped."""
        with self._lock:
            if not self._tripped:
                return 0.0
            return max(
                0.0,
                self._current_cooldown - (time.monotonic() - self._tripped_at),
            )

    def manual_reset(self) -> None:
        """Force-reset the fuse AND clear the escalation streak.

        Use with extreme caution — only when you have verified that the
        underlying cause of the high weight has been resolved.
        """
        with self._lock:
            self._tripped = False
            self._consecutive_streak = 0
            self._current_cooldown = self.base_cooldown_sec
            self._reset_at = time.monotonic()
            _LOG.warning(
                "API Fuse manually reset by operator. Escalation streak cleared."
            )

    def status(self) -> dict:
        """Return fuse status for UI / API consumption."""
        with self._lock:
            remaining = 0.0
            if self._tripped:
                remaining = max(
                    0.0,
                    self._current_cooldown - (time.monotonic() - self._tripped_at),
                )
            time_since_reset = (
                round(time.monotonic() - self._reset_at, 1)
                if self._reset_at > 0 else None
            )
            return {
                "tripped": self._tripped,
                "reason": self._trip_reason if self._tripped else "",
                "remaining_cooldown_sec": round(remaining, 1),
                "trip_count": self._trip_count,
                "consecutive_streak": self._consecutive_streak,
                "current_cooldown_sec": self._current_cooldown,
                "next_cooldown_sec": self._next_escalated_cooldown(),
                "base_cooldown_sec": self.base_cooldown_sec,
                "max_cooldown_sec": self.max_cooldown_sec,
                "threshold_pct": self.threshold_pct,
                "weight_limit": self.weight_limit,
                "seconds_since_last_reset": time_since_reset,
            }

    # ── Internal ────────────────────────────────────────────────────

    def _next_escalated_cooldown(self) -> int:
        """Calculate what the cooldown would be IF the fuse trips right now."""
        # This is called inside the lock, safe.
        # If we're within the grace window since last reset, streak is still hot.
        in_grace = (
            self._reset_at > 0
            and (time.monotonic() - self._reset_at) < _GRACE_WINDOW_SEC
        )
        if in_grace or self._consecutive_streak == 0:
            next_streak = self._consecutive_streak + 1
        else:
            next_streak = 1  # Grace elapsed, fresh streak
        return min(
            self.base_cooldown_sec * (2 ** (next_streak - 1)),
            self.max_cooldown_sec,
        )

    def _trip(self, reason: str, *, force_max: bool = False) -> None:
        with self._lock:
            if self._tripped:
                return  # Already tripped — don't reset the timer mid-cooldown.

            now = time.monotonic()

            # Determine whether this trip is part of an escalating streak.
            in_grace_window = (
                self._reset_at > 0
                and (now - self._reset_at) < _GRACE_WINDOW_SEC
            )
            if in_grace_window or self._consecutive_streak == 0:
                # Still hot — escalate.
                self._consecutive_streak += 1
            else:
                # Grace window elapsed — fresh incident, reset streak.
                self._consecutive_streak = 1

            if force_max:
                self._current_cooldown = self.max_cooldown_sec
            else:
                # Exponential backoff: base * 2^(streak-1), capped at max.
                self._current_cooldown = min(
                    self.base_cooldown_sec * (2 ** (self._consecutive_streak - 1)),
                    self.max_cooldown_sec,
                )

            self._tripped = True
            self._tripped_at = now
            self._trip_reason = reason
            self._trip_count += 1

        _LOG.critical(
            "🚨 API FUSE TRIPPED (#%d, streak=%d): %s "
            "— ALL REST CALLS BLOCKED FOR %ds (base=%ds, max=%ds)",
            self._trip_count,
            self._consecutive_streak,
            reason,
            self._current_cooldown,
            self.base_cooldown_sec,
            self.max_cooldown_sec,
        )
        try:
            from runtime.core.alert_dispatcher import get_alert_dispatcher
            get_alert_dispatcher().critical(
                "FUSE_TRIPPED",
                f"Trip #{self._trip_count} (streak={self._consecutive_streak}): {reason}. Blocked {self._current_cooldown}s.",
            )
        except Exception:
            pass


# ── Singleton ───────────────────────────────────────────────────────

_fuse: Optional[ApiFuse] = None


def get_api_fuse(
    threshold_pct: float = 80.0,
    cooldown_sec: int = 300,
    weight_limit: int = 6000,
    max_cooldown_sec: int = 3600,
) -> ApiFuse:
    """Get or create the global API Fuse singleton."""
    global _fuse
    if _fuse is None:
        _fuse = ApiFuse(
            threshold_pct=threshold_pct,
            cooldown_sec=cooldown_sec,
            weight_limit=weight_limit,
            max_cooldown_sec=max_cooldown_sec,
        )
    return _fuse
