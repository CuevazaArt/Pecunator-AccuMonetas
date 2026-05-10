"""WeightGovernor — adaptive API weight management with zone-based throttling.

Monitors real-time Binance X-MBX-USED-WEIGHT-1M and enforces three
dynamic throttle zones to prevent IP bans:

  GREEN  (≤50%): Normal operation — all bots run freely.
  YELLOW (50–80%): Throttled — bots receive a proportional wait delay.
  RED    (>80%): Emergency — all non-essential bot cycles are blocked.

Integration points:
  - ``audit_weight_from_client`` in _helpers.py calls ``update_weight()``
    on every Binance REST response to feed real-time telemetry.
  - ``BaseStrategyRunner._loop()`` calls ``request_permission()`` before
    each cycle to get a wait duration (0 = go, >0 = wait, inf = block).
  - ``BaseHubService._start_runner()`` calls ``register_bot()`` and
    ``unregister_bot()`` on lifecycle transitions.

Phase-shifting:
  When multiple bots are registered, the governor assigns staggered
  offsets so their cycles don't converge on the same Binance REST
  window, reducing peak weight spikes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

_LOG = logging.getLogger("pecunator.weight_governor")

# ── Default Binance Spot weight limit ───────────────────────────────
_DEFAULT_WEIGHT_LIMIT = 6000

# Zone thresholds (fraction of limit)
_GREEN_CEILING = 0.50
_YELLOW_CEILING = 0.80


class WeightGovernor:
    """Singleton adaptive API weight throttle.

    Usage::

        from runtime.core.weight_governor import get_weight_governor
        gov = get_weight_governor()

        # Feed real-time weight (called by gateway helpers)
        gov.update_weight(1200)

        # Ask permission before a bot cycle
        wait = gov.request_permission("dorothy_btcusdt")
        if wait == float('inf'):
            # EMERGENCY — skip cycle
            ...
        elif wait > 0:
            await asyncio.sleep(wait)

        # Register/unregister bots for phase-shift tracking
        gov.register_bot("dorothy_btcusdt", weight_per_cycle=15)
        gov.unregister_bot("dorothy_btcusdt")
    """

    def __init__(self, weight_limit: int = _DEFAULT_WEIGHT_LIMIT) -> None:
        self._lock = threading.Lock()
        self._weight_limit = weight_limit
        self._current_weight = 0
        self._last_update_ts = 0.0

        # Registered bots: bot_id -> {weight_per_cycle, loop_interval_sec, registered_at}
        self._bots: dict[str, dict[str, Any]] = {}

    # ── Public properties ───────────────────────────────────────────

    @property
    def weight_limit(self) -> int:
        return self._weight_limit

    # ── Weight telemetry ────────────────────────────────────────────

    def update_weight(self, used_weight_1m: int) -> None:
        """Feed a real-time X-MBX-USED-WEIGHT-1M reading."""
        with self._lock:
            self._current_weight = max(0, int(used_weight_1m))
            self._last_update_ts = time.monotonic()

    # ── Zone computation ────────────────────────────────────────────

    def _pct(self) -> float:
        """Current weight as fraction of limit (0.0–1.0+)."""
        if self._weight_limit <= 0:
            return 0.0
        return self._current_weight / self._weight_limit

    def _zone(self) -> str:
        pct = self._pct()
        if pct <= _GREEN_CEILING:
            return "GREEN"
        elif pct <= _YELLOW_CEILING:
            return "YELLOW"
        return "RED"

    # ── Permission gate ─────────────────────────────────────────────

    def request_permission(self, bot_id: str) -> float:
        """Ask the governor if a bot may proceed with its cycle.

        Returns:
            0.0         — proceed immediately (GREEN zone)
            >0.0        — wait this many seconds before proceeding (YELLOW)
            float('inf') — DO NOT proceed, emergency lockout (RED)
        """
        with self._lock:
            zone = self._zone()
            pct = self._pct()

        if zone == "GREEN":
            return 0.0

        if zone == "RED":
            _LOG.warning(
                "WeightGovernor:RED zone (%.0f%%) — blocking %s",
                pct * 100, bot_id,
            )
            return float("inf")

        # YELLOW: proportional backoff 2–30s based on pressure
        # At 50% → ~2s, at 80% → ~30s
        pressure = (pct - _GREEN_CEILING) / (_YELLOW_CEILING - _GREEN_CEILING)
        wait = 2.0 + pressure * 28.0
        _LOG.info(
            "WeightGovernor:YELLOW (%.0f%%) — throttling %s by %.1fs",
            pct * 100, bot_id, wait,
        )
        return wait

    # ── Bot registry for phase-shift ────────────────────────────────

    def register_bot(
        self,
        bot_id: str,
        weight_per_cycle: int = 15,
        loop_interval_sec: float = 450.0,
    ) -> None:
        """Register a bot for governor tracking."""
        with self._lock:
            self._bots[bot_id] = {
                "weight_per_cycle": weight_per_cycle,
                "loop_interval_sec": loop_interval_sec,
                "registered_at": time.monotonic(),
            }
        _LOG.info(
            "WeightGovernor:registered %s (weight/cycle=%d, loop=%.0fs)",
            bot_id, weight_per_cycle, loop_interval_sec,
        )

    def unregister_bot(self, bot_id: str) -> None:
        """Remove a bot from governor tracking."""
        with self._lock:
            removed = self._bots.pop(bot_id, None)
        if removed:
            _LOG.info("WeightGovernor:unregistered %s", bot_id)

    # ── Status / observability ──────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return a status dict for API endpoints and health checks."""
        with self._lock:
            pct = self._pct()
            zone = self._zone()
            age = time.monotonic() - self._last_update_ts if self._last_update_ts else None
            return {
                "zone": zone,
                "current_weight": self._current_weight,
                "weight_limit": self._weight_limit,
                "pct": round(pct * 100, 1),
                "registered_bots": len(self._bots),
                "bot_ids": list(self._bots.keys()),
                "last_update_age_sec": round(age, 1) if age is not None else None,
                "estimated_weight_per_min": self._estimate_weight_per_min(),
            }

    def _estimate_weight_per_min(self) -> float:
        """Estimate total weight consumed per minute by registered bots."""
        total = 0.0
        for info in self._bots.values():
            w = info.get("weight_per_cycle", 15)
            loop = info.get("loop_interval_sec", 450)
            if loop > 0:
                total += w * (60.0 / loop)
        return round(total, 1)


# ── Singleton ───────────────────────────────────────────────────────

_instance: WeightGovernor | None = None
_instance_lock = threading.Lock()


def get_weight_governor() -> WeightGovernor:
    """Return the global WeightGovernor singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                from runtime.core.settings import api_weight_limit_1m_display
                _instance = WeightGovernor(weight_limit=api_weight_limit_1m_display())
    return _instance
