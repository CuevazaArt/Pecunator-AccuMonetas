"""Bot Coordinator — Staged launch & phase-shifted execution for Pecunator.

When a bot is started by the user, it does NOT launch immediately. Instead:

1. The bot enters STAGED status (credentials stored, ready to go).
2. The coordinator analyzes:
   a) Current API weight consumption in the rolling minute.
   b) Where all other bots are in their cycles (phase map).
   c) The new bot's loop_interval_sec.
3. It computes the OPTIMAL launch time — a moment of LOW weight where
   the bot's future cycles will LEAST overlap with existing bots.
4. Once that moment arrives, the bot transitions: STAGED → RUNNING.

Phase-Shift Algorithm:
    Given N existing bots with various intervals and phase offsets,
    the coordinator builds a "weight heatmap" of the next 60 seconds.
    It finds the second with the LOWEST predicted weight and schedules
    the new bot's first cycle there.

    This ensures that as bots accumulate, they naturally distribute
    across the minute — producing the flat, uniform 70% consumption
    curve the system needs.

Execution Sliding:
    During operation, if the governor detects weight building up (yellow/red),
    it can add "jitter" (1-10s delay) to a bot's next sleep, shifting it
    away from other bots that accidentally aligned.

Incident Reference: 2 May 2026 — IP Ban caused by unchecked polling.
"""

from __future__ import annotations

import asyncio
import logging
import time
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

_LOG = logging.getLogger("pecunator.core.bot_coordinator")


@dataclass
class StagedBot:
    """A bot waiting to be launched at the optimal moment.

    Credentials are intentionally NOT stored here — they are resolved
    from the vault at actual launch time by the caller.
    """
    bot_id: str
    hub_type: str  # "dorothy", "masha", "thusnelda"
    loop_interval_sec: float
    # credential_ref: optional vault ID for audit tracing (never the raw keys)
    credential_ref: str = ""  # vault credential_id, not the raw key
    staged_at: float = field(default_factory=time.monotonic)
    launch_at: float = 0.0  # Computed optimal launch time (monotonic)
    launch_delay_sec: float = 0.0  # How long to wait before launching
    status: str = "COMPUTING"  # COMPUTING → STAGED → LAUNCHING → DONE


@dataclass
class ActiveBot:
    """A running bot tracked by the coordinator for phase analysis."""
    bot_id: str
    loop_interval_sec: float
    last_cycle_ts: float = 0.0  # time.monotonic of last cycle
    weight_per_cycle: int = 15
    priority: int = 1


class BotCoordinator:
    """Orchestrates bot launches and execution to produce uniform API weight.

    Usage:
        coordinator = get_bot_coordinator()

        # When user clicks "Start":
        staged = coordinator.stage_bot("bot_123", "dorothy", 450, key, secret)
        # Returns immediately with status=STAGED and launch_delay_sec

        # The coordinator's background loop launches it at the optimal time.

        # When a bot completes a cycle:
        coordinator.report_cycle("bot_123")

        # Compute jitter for next sleep:
        jitter = coordinator.compute_jitter("bot_123")
        # Add jitter to sleep_sec to slide the bot away from congestion
    """

    def __init__(
        self,
        weight_limit: int = 6000,
        target_pct: float = 0.70,
    ) -> None:
        self.weight_limit = max(1, weight_limit)
        self.target_pct = target_pct
        self.target_budget = int(self.weight_limit * self.target_pct)

        self._staged: dict[str, StagedBot] = {}
        self._active: dict[str, ActiveBot] = {}
        self._lock = asyncio.Lock()

        self._current_weight: int = 0
        self._launcher_task: Optional[asyncio.Task[Any]] = None
        self._launcher_stop = asyncio.Event()

        # Callback to actually start the bot runner
        self._start_callbacks: dict[str, Callable[..., Coroutine[Any, Any, None]]] = {}

    # ── Staging ─────────────────────────────────────────────────────

    def stage_bot(
        self,
        bot_id: str,
        hub_type: str,
        loop_interval_sec: float,
        credential_ref: str = "",
    ) -> dict[str, Any]:
        """Stage a bot for coordinated launch.

        Returns immediately with the computed launch delay.
        Credentials are NOT stored here — the caller retains them and
        uses launch_delay_sec to sleep before actually starting the bot.
        """
        delay = self._compute_optimal_delay(loop_interval_sec)

        staged = StagedBot(
            bot_id=bot_id,
            hub_type=hub_type,
            loop_interval_sec=loop_interval_sec,
            credential_ref=credential_ref,  # vault ID only, never raw keys
            launch_delay_sec=delay,
            launch_at=time.monotonic() + delay,
            status="STAGED",
        )
        self._staged[bot_id] = staged

        _LOG.info(
            "Bot %s STAGED for launch in %.1fs (interval=%ds, active_bots=%d)",
            bot_id, delay, loop_interval_sec, len(self._active),
        )

        return {
            "bot_id": bot_id,
            "status": "STAGED",
            "launch_delay_sec": round(delay, 1),
            "launch_at_monotonic": round(staged.launch_at, 1),
            "reason": self._explain_delay(delay, loop_interval_sec),
        }

    def register_callback(
        self,
        hub_type: str,
        callback: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        """Register the actual start function for a hub type."""
        self._start_callbacks[hub_type] = callback

    # ── Active bot tracking ─────────────────────────────────────────

    def register_active(
        self,
        bot_id: str,
        loop_interval_sec: float,
        weight_per_cycle: int = 15,
    ) -> None:
        """Register a bot that's already running (for phase analysis)."""
        self._active[bot_id] = ActiveBot(
            bot_id=bot_id,
            loop_interval_sec=loop_interval_sec,
            weight_per_cycle=weight_per_cycle,
            last_cycle_ts=time.monotonic(),
        )

    def unregister_active(self, bot_id: str) -> None:
        """Remove a stopped bot from tracking."""
        self._active.pop(bot_id, None)
        self._staged.pop(bot_id, None)

    def report_cycle(self, bot_id: str) -> None:
        """Report that a bot just completed a cycle."""
        bot = self._active.get(bot_id)
        if bot:
            bot.last_cycle_ts = time.monotonic()

    def update_weight(self, current_weight: int) -> None:
        """Update real-time API weight."""
        self._current_weight = current_weight

    # ── Jitter (execution sliding) ──────────────────────────────────

    def compute_jitter(self, bot_id: str) -> float:
        """Compute seconds of jitter to add to a bot's sleep.

        This "slides" the bot's next execution away from congestion.

        Returns:
            0.0 — no adjustment needed (green zone)
            1-10s — slight delay to avoid predicted collision
        """
        bot = self._active.get(bot_id)
        if bot is None:
            return 0.0

        # Check weight zone
        weight_pct = (self._current_weight / self.weight_limit) * 100
        if weight_pct < 70:
            return 0.0  # Green — no jitter needed

        # Predict collisions: how many bots will cycle within ±5s of this bot?
        now = time.monotonic()
        my_next = bot.last_cycle_ts + bot.loop_interval_sec
        collision_count = 0

        for other in self._active.values():
            if other.bot_id == bot_id:
                continue
            other_next = other.last_cycle_ts + other.loop_interval_sec
            # Check if their next cycle is within ±5s of ours
            if abs(other_next - my_next) < 5.0:
                collision_count += 1

        if collision_count == 0:
            return 0.0

        # Jitter: shift by 1-10s proportional to collisions and weight pressure
        pressure = min(1.0, weight_pct / 95.0)
        jitter = min(10.0, collision_count * 2.0 * pressure)

        _LOG.debug(
            "Bot %s: adding %.1fs jitter (collisions=%d, weight=%.0f%%)",
            bot_id, jitter, collision_count, weight_pct,
        )
        return jitter

    # ── Background launcher ─────────────────────────────────────────

    def start_launcher(self) -> None:
        """Start the background task that launches staged bots at optimal times."""
        if self._launcher_task is not None and not self._launcher_task.done():
            return
        self._launcher_stop.clear()
        self._launcher_task = asyncio.create_task(self._launcher_loop())
        _LOG.info("Bot Coordinator launcher started.")

    async def stop_launcher(self) -> None:
        """Stop the background launcher."""
        self._launcher_stop.set()
        if self._launcher_task:
            self._launcher_task.cancel()
            await asyncio.gather(self._launcher_task, return_exceptions=True)
        self._launcher_task = None

    async def _launcher_loop(self) -> None:
        """Check staged bots every second. Launch when their time arrives."""
        while not self._launcher_stop.is_set():
            now = time.monotonic()

            # Find staged bots ready to launch
            ready = [
                s for s in list(self._staged.values())
                if s.status == "STAGED" and now >= s.launch_at
            ]

            for staged in ready:
                staged.status = "LAUNCHING"
                callback = self._start_callbacks.get(staged.hub_type)

                if callback:
                    try:
                        # Callback receives only bot_id — credentials resolved
                        # by the hub service from its own vault reference.
                        await callback(staged.bot_id)
                        staged.status = "DONE"
                        self.register_active(
                            staged.bot_id,
                            staged.loop_interval_sec,
                        )
                        _LOG.info(
                            "Bot %s LAUNCHED (was staged for %.1fs)",
                            staged.bot_id,
                            now - staged.staged_at,
                        )
                    except Exception as e:
                        staged.status = "FAILED"
                        _LOG.error("Bot %s launch FAILED: %s", staged.bot_id, e)

                # Clean up completed/failed
                if staged.status in ("DONE", "FAILED"):
                    self._staged.pop(staged.bot_id, None)

            try:
                await asyncio.wait_for(
                    self._launcher_stop.wait(), timeout=1.0
                )
            except asyncio.TimeoutError:
                pass

    # ── Optimal delay computation ───────────────────────────────────

    def _compute_optimal_delay(self, new_interval: float) -> float:
        """Find the optimal delay before launching a new bot.

        Algorithm:
        1. Build a 60-second "heatmap" predicting when active bots will cycle.
        2. Find the second with the LOWEST predicted activity.
        3. Also factor in current weight — if weight is high, wait longer.

        Returns delay in seconds (0-60).
        """
        if not self._active:
            # First bot — check if weight is low enough to start now
            weight_pct = (self._current_weight / self.weight_limit) * 100
            if weight_pct < 50:
                return 0.0  # Green, go now
            # Wait for weight to drop (max 30s)
            return min(30.0, weight_pct / 3.0)

        now = time.monotonic()

        # Build 60-second heatmap: predict bot activity per second
        heatmap = [0.0] * 60

        for bot in self._active.values():
            interval = bot.loop_interval_sec
            if interval <= 0:
                continue

            # Predict when this bot's next cycles will fire
            time_since_last = now - bot.last_cycle_ts
            next_cycle_offset = interval - (time_since_last % interval)

            # Mark each predicted cycle in the heatmap
            t = next_cycle_offset
            while t < 60.0:
                sec_idx = int(t) % 60
                heatmap[sec_idx] += bot.weight_per_cycle
                t += interval

        # Also consider other staged bots
        for staged in self._staged.values():
            if staged.status == "STAGED":
                launch_offset = staged.launch_at - now
                if 0 <= launch_offset < 60:
                    sec_idx = int(launch_offset) % 60
                    heatmap[sec_idx] += 15

        # Find the quietest second
        min_weight = min(heatmap)
        quietest_seconds = [i for i, w in enumerate(heatmap) if w == min_weight]

        # Among quietest seconds, prefer one that creates good phase distribution
        # with the new bot's interval
        best_sec = quietest_seconds[0]
        best_score = float('inf')

        for sec in quietest_seconds:
            # Score: how well does this offset distribute future cycles?
            score = self._phase_collision_score(sec, new_interval)
            if score < best_score:
                best_score = score
                best_sec = sec

        # Add weight pressure delay
        weight_pct = (self._current_weight / self.weight_limit) * 100
        weight_delay = 0.0
        if weight_pct > 70:
            weight_delay = min(15.0, (weight_pct - 70) / 2.0)

        total_delay = max(0.0, best_sec + weight_delay)

        # Cap at 60s — no bot should wait more than a minute
        return min(60.0, total_delay)

    def _phase_collision_score(self, offset_sec: int, new_interval: float) -> float:
        """Score how many future collisions a given offset would create.

        Lower is better. Counts how many active bots would cycle
        within ±3s of the new bot's predicted cycles over the next 10 minutes.
        """
        collisions = 0.0
        now = time.monotonic()

        for bot in self._active.values():
            interval = bot.loop_interval_sec
            if interval <= 0:
                continue

            # Check collisions over next 600 seconds (10 minutes)
            for future_sec in range(0, 600, int(max(1, new_interval))):
                new_cycle = offset_sec + future_sec
                bot_offset = (now - bot.last_cycle_ts) % interval
                bot_cycle = bot_offset + future_sec

                # Normalize to interval boundaries
                new_phase = new_cycle % new_interval
                bot_phase = bot_cycle % interval

                # Check if they'd fire within ±3s of each other
                if abs(new_phase - bot_phase) < 3.0:
                    collisions += 1

        return collisions

    def _explain_delay(self, delay: float, interval: float) -> str:
        """Human-readable explanation of why a delay was chosen."""
        if delay == 0:
            return "Sin delay — zona verde, primer bot o slot óptimo inmediato"
        parts = []
        if self._active:
            parts.append(f"{len(self._active)} bots activos, buscando hueco libre")
        weight_pct = (self._current_weight / self.weight_limit) * 100
        if weight_pct > 70:
            parts.append(f"peso API al {weight_pct:.0f}%, esperando zona verde")
        parts.append(f"intervalo={interval}s, mejor slot en {delay:.1f}s")
        return " · ".join(parts) if parts else "Optimizado"

    # ── Status ──────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return coordinator status for API/UI consumption."""
        now = time.monotonic()
        weight_pct = (self._current_weight / self.weight_limit) * 100

        return {
            "active_bots": len(self._active),
            "staged_bots": len(self._staged),
            "current_weight_pct": round(weight_pct, 1),
            "weight_zone": self._zone_name(weight_pct),
            "staged": {
                bid: {
                    "status": s.status,
                    "hub_type": s.hub_type,
                    "interval_sec": s.loop_interval_sec,
                    "delay_sec": round(s.launch_delay_sec, 1),
                    "remaining_sec": round(max(0, s.launch_at - now), 1),
                    "reason": self._explain_delay(
                        s.launch_delay_sec, s.loop_interval_sec
                    ),
                }
                for bid, s in self._staged.items()
            },
            "active": {
                bid: {
                    "interval_sec": b.loop_interval_sec,
                    "last_cycle_ago_sec": round(now - b.last_cycle_ts, 1),
                    "weight_per_cycle": b.weight_per_cycle,
                    "priority": b.priority,
                }
                for bid, b in self._active.items()
            },
        }

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

_coordinator: Optional[BotCoordinator] = None


def get_bot_coordinator(
    weight_limit: int = 6000,
    target_pct: float = 0.70,
) -> BotCoordinator:
    """Get or create the global BotCoordinator singleton."""
    global _coordinator
    if _coordinator is None:
        _coordinator = BotCoordinator(
            weight_limit=weight_limit,
            target_pct=target_pct,
        )
    return _coordinator
