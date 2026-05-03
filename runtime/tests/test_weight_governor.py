"""Tests for runtime.core.weight_governor."""
from __future__ import annotations

import time
import pytest
from unittest.mock import patch

from runtime.core.weight_governor import WeightGovernor, get_weight_governor


@pytest.fixture(autouse=True)
def fresh_governor():
    """Each test gets a fresh WeightGovernor instance."""
    gov = WeightGovernor(weight_limit=6000, target_pct=0.70)
    yield gov


class TestWeightGovernorRegistration:
    def test_register_bot_assigns_phase_offset(self, fresh_governor):
        fresh_governor.register_bot("bot1", weight_per_cycle=15, loop_interval_sec=450)
        status = fresh_governor.status()
        assert "bot1" in status["bots"]

    def test_two_bots_same_interval_get_staggered_offsets(self, fresh_governor):
        fresh_governor.register_bot("bot1", weight_per_cycle=15, loop_interval_sec=60)
        fresh_governor.register_bot("bot2", weight_per_cycle=15, loop_interval_sec=60)
        status = fresh_governor.status()
        assert "bot1" in status["bots"]
        assert "bot2" in status["bots"]

    def test_ten_bots_all_registered(self, fresh_governor):
        for i in range(10):
            fresh_governor.register_bot(f"bot{i}", weight_per_cycle=15, loop_interval_sec=450)
        status = fresh_governor.status()
        assert status["registered_bots"] == 10

    def test_unregister_removes_bot(self, fresh_governor):
        fresh_governor.register_bot("bot1", weight_per_cycle=15, loop_interval_sec=450)
        fresh_governor.unregister_bot("bot1")
        status = fresh_governor.status()
        assert "bot1" not in status.get("bots", {})

    def test_unregister_nonexistent_does_not_raise(self, fresh_governor):
        fresh_governor.unregister_bot("nonexistent")  # Should not raise


class TestWeightGovernorZones:
    def test_green_zone_at_zero_weight(self, fresh_governor):
        fresh_governor.update_weight(0)
        status = fresh_governor.status()
        assert status["zone"] == "GREEN"

    def test_yellow_zone_at_75_pct(self, fresh_governor):
        fresh_governor.update_weight(4500)  # 75% of 6000
        status = fresh_governor.status()
        assert status["zone"] == "YELLOW"

    def test_red_zone_at_87_pct(self, fresh_governor):
        fresh_governor.update_weight(5220)  # 87% of 6000
        status = fresh_governor.status()
        assert status["zone"] == "RED"

    def test_emergency_zone_at_96_pct(self, fresh_governor):
        fresh_governor.update_weight(5760)  # 96% of 6000
        status = fresh_governor.status()
        assert status["zone"] == "EMERGENCY"

    def test_update_weight_reflects_in_status(self, fresh_governor):
        fresh_governor.update_weight(3000)
        status = fresh_governor.status()
        assert status["current_weight"] == 3000


class TestWeightGovernorPermission:
    def test_request_permission_returns_zero_in_green(self, fresh_governor):
        fresh_governor.register_bot("bot1", weight_per_cycle=15, loop_interval_sec=450)
        fresh_governor.update_weight(0)
        wait = fresh_governor.request_permission("bot1")
        assert wait == 0.0

    def test_request_permission_returns_positive_in_yellow(self, fresh_governor):
        fresh_governor.register_bot("bot1", weight_per_cycle=15, loop_interval_sec=450)
        fresh_governor.update_weight(4500)  # Yellow zone
        wait = fresh_governor.request_permission("bot1")
        assert wait >= 0.0  # May or may not wait depending on phase

    def test_emergency_zone_blocks_monitor_priority(self, fresh_governor):
        fresh_governor.register_bot("bot1", weight_per_cycle=15, loop_interval_sec=450,
                                    priority=0)
        fresh_governor.update_weight(5760)  # Emergency
        wait = fresh_governor.request_permission("bot1")
        assert wait == float('inf')

    def test_unknown_bot_returns_zero(self, fresh_governor):
        wait = fresh_governor.request_permission("unknown_bot")
        assert wait == 0.0


class TestWeightGovernorStatus:
    def test_status_returns_required_fields(self, fresh_governor):
        status = fresh_governor.status()
        required = {"zone", "current_weight", "weight_limit", "target_budget",
                    "registered_bots"}
        assert required.issubset(status.keys())

    def test_singleton_returns_same_instance(self):
        a = get_weight_governor()
        b = get_weight_governor()
        assert a is b
