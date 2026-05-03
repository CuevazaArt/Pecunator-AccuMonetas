"""Weight Governor — Central API weight budget manager for Pecunator.

Distributes API call slots across all running bot instances to maintain
uniform ~70% weight consumption, preventing oscillating spikes that
trigger the ApiFuse circuit breaker.

Architecture:
    - Each bot registers with the governor and receives a phase offset.
    - Before each API call cycle, the bot asks for permission.
    - The governor tracks real-time weight usage and can throttle dynamically.
    - Emergency degradation automatically stretches intervals when weight rises.

Target Operating Envelope:
    Green:    0-70%  → normal operation
    Yellow:  70-85%  → monitors paused, intervals +50%
    Red:     85-95%  → all intervals tripled
    Emergency: >95%  → only bots with open positions may call

Incident Reference: 2 May 2026 — IP Ban (-1003) caused by unchecked polling.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.core.weight_governor")


@dataclass
class BotSlot:
    """Tracking info for a registered bot."""
    bot_id: str
    weight_per_cycle: int = 15  # Estimated API weight per cycle
    loop_interval_sec: float = 450.0
    phase_offset_sec: float = 0.0
    priority: int = 1  # 0=idle, 1=monitor, 2=active, 3=trading (has positions)
    last_cycle_ts: float = 0.0
    total_weight_used: int = 0
    cycle_count: int = 0


class WeightGovernor:
    """Central API weight budget manager.

    Coordinates N bot instances to produce smooth, uniform API weight
    consumption at ~target_pct of the Binance limit.
    """

    # Priority levels
    IDLE = 0
    MONITOR = 1
    ACTIVE = 2
    TRADING = 3  # Has open positions — highest priority

    def __init__(
        self,
        weight_limit: int = 6000,
        target_pct: float = 0.70,
        ceiling_pct: float = 0.95,
    ) -> None:
        self.weight_limit = max(1, weight_limit)
        self.target_pct = max(0.1, min(target_pct, 0.99))
        self.ceiling_pct = max(self.target_pct, min(ceiling_pct, 0.99))
        self.target_budget = int(self.weight_limit * self.target_pct)
        self.hard_ceiling = int(self.weight_limit * self.ceiling_pct)

        self._slots: dict[str, BotSlot] = {}
        self._lock = threading.Lock()

        # Real-time weight tracking (updated by ApiFuse audit)
        self._current_weight: int = 0
        self._weight_updated_at: float = 0.0

    # ── Registration ────────────────────────────────────────────────

    def register_bot(
        self,
        bot_id: str,
        weight_per_cycle: int = 15,
        loop_interval_sec: float = 450.0,
        priority: int = 1,
    ) -> None:
        """Register a bot and compute its phase-shifted slot."""
        with self._lock:
            self._slots[bot_id] = BotSlot(
                bot_id=bot_id,
                weight_per_cycle=weight_per_cycle,
                loop_interval_sec=loop_interval_sec,
                priority=priority,
            )
            self._recompute_offsets()
        _LOG.info(
            "Bot %s registered (weight=%d, interval=%ds, priority=%d). "
            "Total bots: %d",
            bot_id, weight_per_cycle, loop_interval_sec, priority,
            len(self._slots),
        )

    def unregister_bot(self, bot_id: str) -> None:
        """Remove a bot from the schedule."""
        with self._lock:
            self._slots.pop(bot_id, None)
            self._recompute_offsets()
        _LOG.info("Bot %s unregistered. Remaining: %d", bot_id, len(self._slots))

    def update_priority(self, bot_id: str, priority: int) -> None:
        """Update a bot's priority (e.g., when it opens a position)."""
        with self._lock:
            slot = self._slots.get(bot_id)
            if slot:
                slot.priority = priority

    # ── Scheduling ──────────────────────────────────────────────────

    def request_permission(self, bot_id: str) -> float:
        """Ask the governor for permission to make API calls.

        Returns:
            0.0 — go ahead immediately
            >0.0 — wait this many seconds before calling
            float('inf') — do NOT call (emergency lockout)
        """
        with self._lock:
            slot = self._slots.get(bot_id)
            if slot is None:
                return 0.0  # Unregistered bot — let it through (legacy)

            throttle = self._compute_throttle()

            # Emergency: only TRADING priority bots may proceed
            if throttle == float('inf') and slot.priority < self.TRADING:
                return float('inf')

            # Apply throttle multiplier to the bot's interval
            now = time.monotonic()
            effective_interval = slot.loop_interval_sec * max(1.0, throttle)
            next_allowed = slot.last_cycle_ts + effective_interval

            if now >= next_allowed:
                return 0.0
            return next_allowed - now

    def report_cycle(self, bot_id: str, weight_used: int) -> None:
        """Report that a bot completed a cycle and consumed weight."""
        with self._lock:
            slot = self._slots.get(bot_id)
            if slot:
                slot.last_cycle_ts = time.monotonic()
                slot.total_weight_used += weight_used
                slot.cycle_count += 1

    def update_weight(self, current_weight: int) -> None:
        """Update the real-time API weight reading (from X-MBX-USED-WEIGHT-1M)."""
        with self._lock:
            self._current_weight = current_weight
            self._weight_updated_at = time.monotonic()

    # ── Status ──────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return governor status for UI/API consumption."""
        with self._lock:
            pct = (self._current_weight / self.weight_limit) * 100 if self.weight_limit > 0 else 0
            zone = self._zone_name(pct)
            throttle = self._compute_throttle()
            return {
                "registered_bots": len(self._slots),
                "current_weight": self._current_weight,
                "weight_limit": self.weight_limit,
                "target_budget": self.target_budget,
                "hard_ceiling": self.hard_ceiling,
                "current_pct": round(pct, 1),
                "zone": zone,
                "throttle_multiplier": round(throttle, 2) if throttle != float('inf') else "LOCKOUT",
                "bots": {
                    bid: {
                        "priority": s.priority,
                        "phase_offset_sec": round(s.phase_offset_sec, 1),
                        "cycle_count": s.cycle_count,
                        "total_weight": s.total_weight_used,
                    }
                    for bid, s in self._slots.items()
                },
            }

    # ── Internal ────────────────────────────────────────────────────

    def _recompute_offsets(self) -> None:
        """Phase-shift all bots to distribute calls uniformly.

        Stagger algorithm:
            Group bots by their loop_interval_sec.
            Within each group of N bots with interval T:
                Bot i gets offset = i * (T / N)
            This guarantees at most 1 bot waking per T/N seconds.
        """
        from collections import defaultdict

        groups: dict[float, list[BotSlot]] = defaultdict(list)
        for slot in self._slots.values():
            groups[slot.loop_interval_sec].append(slot)

        for interval, group in groups.items():
            n = len(group)
            if n == 0:
                continue
            offset_step = interval / n
            # Sort by bot_id for deterministic assignment
            group.sort(key=lambda s: s.bot_id)
            for i, slot in enumerate(group):
                slot.phase_offset_sec = i * offset_step

    def _compute_throttle(self) -> float:
        """Compute the current throttle multiplier based on weight zone.

        Returns:
            1.0 — green zone, normal operation
            1.5 — yellow zone, slow down 50%
            3.0 — red zone, triple intervals
            inf — emergency, lockout (only TRADING bots proceed)
        """
        if self.weight_limit <= 0:
            return 1.0

        pct = (self._current_weight / self.weight_limit) * 100

        if pct < self.target_pct * 100:
            return 1.0  # Green
        elif pct < 85.0:
            return 1.5  # Yellow
        elif pct < self.ceiling_pct * 100:
            return 3.0  # Red
        else:
            return float('inf')  # Emergency

    @staticmethod
    def _zone_name(pct: float) -> str:
        if pct < 70:
            return "GREEN"
        elif pct < 85:
            return "YELLOW"
        elif pct < 95:
            return "RED"
        else:
            return "EMERGENCY"


# ── Singleton ───────────────────────────────────────────────────────

_governor: Optional[WeightGovernor] = None


def get_weight_governor(
    weight_limit: int = 6000,
    target_pct: float = 0.70,
    ceiling_pct: float = 0.95,
) -> WeightGovernor:
    """Get or create the global WeightGovernor singleton."""
    global _governor
    if _governor is None:
        _governor = WeightGovernor(
            weight_limit=weight_limit,
            target_pct=target_pct,
            ceiling_pct=ceiling_pct,
        )
    return _governor
