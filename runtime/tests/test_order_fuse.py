"""Tests for OrderFuse — order rate-limit circuit breaker."""

import time
from unittest.mock import patch

from runtime.core.order_fuse import OrderFuse, get_order_fuse


def _fresh() -> OrderFuse:
    return OrderFuse(threshold_pct=70.0, cooldown_sec=15, order_limit_10s=100)


class TestOrderFuseBasic:
    def test_not_tripped_initially(self):
        f = _fresh()
        assert not f.is_tripped()
        assert f.remaining_cooldown_sec() == 0.0

    def test_check_below_threshold(self):
        f = _fresh()
        assert not f.check_order_count(50)
        assert not f.is_tripped()

    def test_check_at_threshold_trips(self):
        f = _fresh()
        assert f.check_order_count(70)  # 70% = threshold
        assert f.is_tripped()

    def test_check_above_threshold_trips(self):
        f = _fresh()
        assert f.check_order_count(85)
        assert f.is_tripped()

    def test_zero_count_no_trip(self):
        f = _fresh()
        assert not f.check_order_count(0)
        assert not f.is_tripped()

    def test_auto_reset_after_cooldown(self):
        f = OrderFuse(threshold_pct=70.0, cooldown_sec=5, order_limit_10s=100)
        f.check_order_count(80)
        assert f.is_tripped()
        time.sleep(1.5)
        assert f.is_tripped()  # Still within cooldown
        f.manual_reset()
        assert not f.is_tripped()  # Manual reset clears

    def test_error_code_1015_trips(self):
        f = _fresh()
        assert f.on_error_code(-1015, "Too many new orders")
        assert f.is_tripped()

    def test_error_code_unrelated_no_trip(self):
        f = _fresh()
        assert not f.on_error_code(-1021, "Timestamp outside recv window")
        assert not f.is_tripped()

    def test_manual_reset(self):
        f = _fresh()
        f.check_order_count(90)
        assert f.is_tripped()
        f.manual_reset()
        assert not f.is_tripped()

    def test_status_dict(self):
        f = _fresh()
        s = f.status()
        assert s["tripped"] is False
        assert s["order_limit_10s"] == 100
        assert s["threshold_pct"] == 70.0

    def test_trip_increments_count(self):
        f = OrderFuse(threshold_pct=70.0, cooldown_sec=5, order_limit_10s=100)
        f.check_order_count(80)
        assert f.status()["trip_count"] == 1
        f.manual_reset()
        f.check_order_count(80)
        assert f.status()["trip_count"] == 2

    def test_escalation_via_error_code(self):
        """Error code -1015 trips with force_max — goes to max cooldown."""
        f = OrderFuse(threshold_pct=70.0, cooldown_sec=5, order_limit_10s=100, max_cooldown_sec=60)
        f.on_error_code(-1015, "Too many new orders")
        assert f.status()["current_cooldown_sec"] == 60  # force_max
        assert f.status()["trip_count"] == 1

    def test_manual_reset_clears_streak(self):
        f = OrderFuse(threshold_pct=70.0, cooldown_sec=5, order_limit_10s=100, max_cooldown_sec=60)
        f.check_order_count(80)
        assert f.status()["consecutive_streak"] == 1
        f.manual_reset()
        assert f.status()["consecutive_streak"] == 0


class TestOrderFuseSingleton:
    def test_singleton_returns_same_instance(self):
        import runtime.core.order_fuse as mod
        mod._fuse = None
        f1 = get_order_fuse()
        f2 = get_order_fuse()
        assert f1 is f2
        mod._fuse = None  # Cleanup
