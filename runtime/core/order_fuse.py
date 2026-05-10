"""Order Fuse — Circuit breaker for Binance order rate-limit protection.

Monitors X-MBX-ORDER-COUNT-10S against the UID-scoped limit (default 100)
and blocks ALL outgoing order calls if the count exceeds a configurable
threshold (default 70%).

Binance order rate limits (Spot, standard tier):
    - 10 orders / second          (per UID)
    - 100 orders / 10 seconds     (per UID)
    - 200,000 orders / 24 hours   (per UID)

Design mirrors ApiFuse with the same exponential backoff and grace window:

    Trip #1 → base_cooldown     (default 15s — 10s window + margin)
    Trip #2 → 30s
    Trip #3 → 60s
    ...
    Trip #N → max_cooldown_sec  (default 120s ceiling)

The 10s window is much shorter than the 1m weight window, so cooldowns
are correspondingly shorter — the rate limit resets every 10 seconds.

Usage:
    from runtime.core.order_fuse import get_order_fuse

    fuse = get_order_fuse()
    fuse.check_order_count(count_10s)

    # Before placing an order:
    if fuse.is_tripped():
        return  # Skip order placement
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

_LOG = logging.getLogger("pecunator.core.order_fuse")

# Binance error codes related to order rate limits.
_ORDER_RATE_CODES = {-1015}  # "Too many new orders"

# Grace window: how long after a reset before the streak counter clears.
_GRACE_WINDOW_SEC = 30.0  # Shorter than ApiFuse (120s) because 10s windows.


class OrderFuse:
    """Global circuit breaker for Binance order rate limits."""

    def __init__(
        self,
        threshold_pct: float = 70.0,
        cooldown_sec: int = 15,
        order_limit_10s: int = 100,
        max_cooldown_sec: int = 120,
    ) -> None:
        self.threshold_pct = max(10.0, min(threshold_pct, 99.0))
        self.base_cooldown_sec = max(5, cooldown_sec)
        self.order_limit_10s = max(1, order_limit_10s)
        self.max_cooldown_sec = max(self.base_cooldown_sec, max_cooldown_sec)

        self._tripped = False
        self._tripped_at: float = 0.0
        self._reset_at: float = 0.0
        self._current_cooldown: int = self.base_cooldown_sec
        self._trip_reason: str = ""
        self._trip_count: int = 0
        self._consecutive_streak: int = 0
        self._lock = threading.Lock()

    # ── Public API ──────────────────────────────────────────────────

    def check_order_count(self, order_count_10s: int) -> bool:
        """Evaluate current order count. If ≥ threshold, trip.

        Returns True if fuse is (or just became) tripped.
        """
        if order_count_10s <= 0:
            return self.is_tripped()
        pct = (order_count_10s / self.order_limit_10s) * 100
        if pct >= self.threshold_pct:
            reason = (
                f"Order rate al {pct:.1f}% ({order_count_10s}/{self.order_limit_10s}/10s). "
                f"Umbral: {self.threshold_pct}%"
            )
            self._trip(reason)
            return True
        return self.is_tripped()

    def on_error_code(self, code: int, message: str = "") -> bool:
        """If we receive -1015 (Too many new orders), trip IMMEDIATELY."""
        code_i = int(code) if code else 0
        if code_i in _ORDER_RATE_CODES:
            reason = f"Order rate limit error: code={code_i} msg={message[:200]}"
            self._trip(reason, force_max=True)
            return True
        return False

    def is_tripped(self) -> bool:
        """Is the fuse currently blocking order placement?"""
        with self._lock:
            if not self._tripped:
                return False
            elapsed = time.monotonic() - self._tripped_at
            if elapsed >= self._current_cooldown:
                self._reset_at = time.monotonic()
                self._tripped = False
                _LOG.info(
                    "Order Fuse auto-reset after %.0fs cooldown "
                    "(trip #%d, streak=%d): %s",
                    elapsed,
                    self._trip_count,
                    self._consecutive_streak,
                    self._trip_reason,
                )
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
        """Force-reset the fuse AND clear the escalation streak."""
        with self._lock:
            self._tripped = False
            self._consecutive_streak = 0
            self._current_cooldown = self.base_cooldown_sec
            self._reset_at = time.monotonic()
            _LOG.warning(
                "Order Fuse manually reset by operator. Streak cleared."
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
                "base_cooldown_sec": self.base_cooldown_sec,
                "max_cooldown_sec": self.max_cooldown_sec,
                "threshold_pct": self.threshold_pct,
                "order_limit_10s": self.order_limit_10s,
                "seconds_since_last_reset": time_since_reset,
            }

    # ── Internal ────────────────────────────────────────────────────

    def _trip(self, reason: str, *, force_max: bool = False) -> None:
        with self._lock:
            if self._tripped:
                return

            now = time.monotonic()
            in_grace_window = (
                self._reset_at > 0
                and (now - self._reset_at) < _GRACE_WINDOW_SEC
            )
            if in_grace_window or self._consecutive_streak == 0:
                self._consecutive_streak += 1
            else:
                self._consecutive_streak = 1

            if force_max:
                self._current_cooldown = self.max_cooldown_sec
            else:
                self._current_cooldown = min(
                    self.base_cooldown_sec * (2 ** (self._consecutive_streak - 1)),
                    self.max_cooldown_sec,
                )

            self._tripped = True
            self._tripped_at = now
            self._trip_reason = reason
            self._trip_count += 1

        _LOG.critical(
            "🚨 ORDER FUSE TRIPPED (#%d, streak=%d): %s "
            "— ORDER PLACEMENT BLOCKED FOR %ds",
            self._trip_count,
            self._consecutive_streak,
            reason,
            self._current_cooldown,
        )


# ── Singleton ───────────────────────────────────────────────────────

_fuse: Optional[OrderFuse] = None


def get_order_fuse(
    threshold_pct: float = 70.0,
    cooldown_sec: int = 15,
    order_limit_10s: int = 100,
    max_cooldown_sec: int = 120,
) -> OrderFuse:
    """Get or create the global Order Fuse singleton."""
    global _fuse
    if _fuse is None:
        _fuse = OrderFuse(
            threshold_pct=threshold_pct,
            cooldown_sec=cooldown_sec,
            order_limit_10s=order_limit_10s,
            max_cooldown_sec=max_cooldown_sec,
        )
    return _fuse
