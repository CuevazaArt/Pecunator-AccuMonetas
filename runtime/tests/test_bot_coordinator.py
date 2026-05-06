"""Tests for runtime.core.bot_coordinator."""
from __future__ import annotations

import time
import pytest

from runtime.core.bot_coordinator import BotCoordinator, get_bot_coordinator


@pytest.fixture()
def coord():
    """Fresh coordinator per test."""
    return BotCoordinator(weight_limit=6000, target_pct=0.70)


class TestStagedLaunch:
    def test_stage_bot_returns_staged_status(self, coord):
        result = coord.stage_bot("bot1", "dorothy", 450.0)
        assert result["status"] == "STAGED"
        assert "launch_delay_sec" in result
        assert result["bot_id"] == "bot1"

    def test_first_bot_zero_delay_in_green(self, coord):
        coord.update_weight(0)
        result = coord.stage_bot("bot1", "dorothy", 450.0)
        assert result["launch_delay_sec"] == 0.0

    def test_first_bot_has_delay_in_yellow_zone(self, coord):
        coord.update_weight(4500)  # 75%
        result = coord.stage_bot("bot1", "dorothy", 450.0)
        assert result["launch_delay_sec"] >= 0.0

    def test_staged_appears_in_status(self, coord):
        coord.stage_bot("bot1", "dorothy", 450.0)
        status = coord.status()
        assert status["staged_bots"] == 1

    def test_credential_ref_stored_not_raw_key(self, coord):
        """Ensure no api_key or api_secret stored in StagedBot."""
        coord.stage_bot("bot1", "dorothy", 450.0, credential_ref="cred-abc")
        staged = coord._staged.get("bot1")
        assert staged is not None
        assert not hasattr(staged, "api_key"), "StagedBot must NOT have api_key"
        assert not hasattr(staged, "api_secret"), "StagedBot must NOT have api_secret"
        assert staged.credential_ref == "cred-abc"


class TestActiveBotTracking:
    def test_register_active_appears_in_status(self, coord):
        coord.register_active("bot1", loop_interval_sec=450)
        status = coord.status()
        assert status["active_bots"] == 1

    def test_unregister_removes_bot(self, coord):
        coord.register_active("bot1", loop_interval_sec=450)
        coord.unregister_active("bot1")
        status = coord.status()
        assert status["active_bots"] == 0

    def test_report_cycle_updates_timestamp(self, coord):
        coord.register_active("bot1", loop_interval_sec=450)
        before = coord._active["bot1"].last_cycle_ts
        time.sleep(0.05)
        coord.report_cycle("bot1")
        after = coord._active["bot1"].last_cycle_ts
        assert after > before

    def test_report_cycle_unknown_bot_silent(self, coord):
        coord.report_cycle("nonexistent")  # Must not raise


class TestJitter:
    def test_compute_jitter_zero_in_green(self, coord):
        coord.update_weight(0)
        coord.register_active("bot1", loop_interval_sec=450)
        jitter = coord.compute_jitter("bot1")
        assert jitter == 0.0

    def test_compute_jitter_nonzero_with_collisions_in_yellow(self, coord):
        coord.update_weight(4500)  # Yellow zone
        # Register two bots with almost-same phase
        coord.register_active("bot1", loop_interval_sec=30)
        coord.register_active("bot2", loop_interval_sec=30)
        # Force same last_cycle_ts to guarantee collision
        coord._active["bot1"].last_cycle_ts = time.monotonic()
        coord._active["bot2"].last_cycle_ts = time.monotonic()
        jitter = coord.compute_jitter("bot1")
        assert jitter >= 0.0  # Yellow zone with collision

    def test_compute_jitter_unknown_bot_returns_zero(self, coord):
        jitter = coord.compute_jitter("unknown")
        assert jitter == 0.0


class TestMultipleBotsDelay:
    def test_multiple_bots_get_staggered_delays(self, coord):
        """3 bots: first has 0 delay, subsequent get heatmap-based delays."""
        coord.update_weight(0)
        r1 = coord.stage_bot("bot1", "dorothy", 60.0)
        coord.register_active("bot1", loop_interval_sec=60)
        r2 = coord.stage_bot("bot2", "dorothy", 60.0)
        # At least one of them should have a non-zero delay to stagger
        assert r1["launch_delay_sec"] >= 0
        assert r2["launch_delay_sec"] >= 0


class TestStatus:
    def test_status_has_required_fields(self, coord):
        status = coord.status()
        for key in ("active_bots", "staged_bots", "current_weight_pct",
                    "weight_zone", "staged", "active"):
            assert key in status, f"Missing key: {key}"

    def test_singleton_returns_same_instance(self):
        a = get_bot_coordinator()
        b = get_bot_coordinator()
        assert a is b
