"""Unit tests for WeightGovernor — zone-based API throttling.

Validates:
  - Zone computation (GREEN / YELLOW / RED) at threshold boundaries.
  - Permission gate returns correct wait durations.
  - Bot registration / unregistration tracking.
  - Estimated weight-per-minute calculation.
  - Thread-safety of update_weight under concurrent access.
"""

import threading
import time

import pytest

from runtime.core.weight_governor import WeightGovernor


# ── Zone computation ────────────────────────────────────────────────

class TestZoneComputation:
    """Verify zone boundaries at 50 % / 80 % of weight limit."""

    def test_green_at_zero(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(0)
        assert g.status()["zone"] == "GREEN"

    def test_green_at_ceiling(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(3000)  # exactly 50 %
        assert g.status()["zone"] == "GREEN"

    def test_yellow_just_above_green(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(3001)
        assert g.status()["zone"] == "YELLOW"

    def test_yellow_at_ceiling(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(4800)  # exactly 80 %
        assert g.status()["zone"] == "YELLOW"

    def test_red_just_above_yellow(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(4801)
        assert g.status()["zone"] == "RED"

    def test_red_at_limit(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(6000)
        assert g.status()["zone"] == "RED"

    def test_red_above_limit(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(9999)
        assert g.status()["zone"] == "RED"


# ── Permission gate ─────────────────────────────────────────────────

class TestPermissionGate:
    """Verify the wait-duration contract returned by request_permission."""

    def test_green_returns_zero(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(1000)
        assert g.request_permission("dorothy_btcusdt") == 0.0

    def test_yellow_returns_positive_wait(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(4000)  # ~66 %
        wait = g.request_permission("dorothy_btcusdt")
        assert 2.0 <= wait <= 30.0

    def test_yellow_proportional_scaling(self):
        g = WeightGovernor(weight_limit=6000)
        # Low-yellow (~51 %)
        g.update_weight(3060)
        low_wait = g.request_permission("bot_a")
        # High-yellow (~79 %)
        g.update_weight(4740)
        high_wait = g.request_permission("bot_b")
        assert high_wait > low_wait

    def test_red_returns_infinity(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(5000)
        wait = g.request_permission("dorothy_btcusdt")
        assert wait == float("inf")


# ── Bot registry ────────────────────────────────────────────────────

class TestBotRegistry:
    """Verify register / unregister tracking."""

    def test_register_and_list(self):
        g = WeightGovernor()
        g.register_bot("dorothy_btcusdt", weight_per_cycle=15, loop_interval_sec=450)
        g.register_bot("elphaba_ethusdt", weight_per_cycle=12, loop_interval_sec=300)
        status = g.status()
        assert status["registered_bots"] == 2
        assert "dorothy_btcusdt" in status["bot_ids"]
        assert "elphaba_ethusdt" in status["bot_ids"]

    def test_unregister(self):
        g = WeightGovernor()
        g.register_bot("bot_a")
        g.register_bot("bot_b")
        g.unregister_bot("bot_a")
        status = g.status()
        assert status["registered_bots"] == 1
        assert "bot_a" not in status["bot_ids"]

    def test_unregister_nonexistent_is_noop(self):
        g = WeightGovernor()
        g.unregister_bot("ghost_bot")  # should not raise


# ── Weight estimation ───────────────────────────────────────────────

class TestWeightEstimation:
    """Verify the estimated_weight_per_min formula."""

    def test_single_bot(self):
        g = WeightGovernor()
        g.register_bot("bot_a", weight_per_cycle=15, loop_interval_sec=60)
        # 15 weight × (60/60) = 15 weight/min
        assert g.status()["estimated_weight_per_min"] == 15.0

    def test_two_bots(self):
        g = WeightGovernor()
        g.register_bot("bot_a", weight_per_cycle=15, loop_interval_sec=60)
        g.register_bot("bot_b", weight_per_cycle=10, loop_interval_sec=300)
        # 15*(60/60) + 10*(60/300) = 15 + 2 = 17
        assert g.status()["estimated_weight_per_min"] == 17.0

    def test_no_bots(self):
        g = WeightGovernor()
        assert g.status()["estimated_weight_per_min"] == 0.0


# ── Observability ───────────────────────────────────────────────────

class TestStatus:
    """Ensure the status dict is well-formed."""

    def test_status_keys(self):
        g = WeightGovernor(weight_limit=6000)
        g.update_weight(100)
        s = g.status()
        for key in ("zone", "current_weight", "weight_limit", "pct",
                     "registered_bots", "bot_ids", "last_update_age_sec",
                     "estimated_weight_per_min"):
            assert key in s, f"Missing key: {key}"

    def test_pct_calculation(self):
        g = WeightGovernor(weight_limit=1000)
        g.update_weight(250)
        assert g.status()["pct"] == 25.0

    def test_last_update_age_is_recent(self):
        g = WeightGovernor()
        g.update_weight(0)
        time.sleep(0.05)
        age = g.status()["last_update_age_sec"]
        assert age is not None
        assert 0.0 < age < 2.0

    def test_negative_weight_clamped(self):
        g = WeightGovernor()
        g.update_weight(-500)
        assert g.status()["current_weight"] == 0


# ── Thread safety ───────────────────────────────────────────────────

class TestThreadSafety:
    """Hammer update_weight from multiple threads — must not crash."""

    def test_concurrent_updates(self):
        g = WeightGovernor(weight_limit=6000)
        errors = []

        def updater(start: int):
            try:
                for i in range(200):
                    g.update_weight(start + i)
                    g.request_permission(f"bot_{start}")
                    g.status()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=updater, args=(i * 100,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread-safety violation: {errors}"
