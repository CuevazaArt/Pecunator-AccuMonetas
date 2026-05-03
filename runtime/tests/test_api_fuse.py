"""Tests for runtime.core.api_fuse — using actual API: check_weight, on_error_code, manual_reset."""
from __future__ import annotations

import time
import pytest

from runtime.core.api_fuse import ApiFuse, get_api_fuse


@pytest.fixture()
def fuse():
    """Fresh fuse per test (not the singleton)."""
    f = ApiFuse(weight_limit=6000, threshold_pct=80.0, cooldown_sec=60)
    yield f
    f.manual_reset()


class TestFuseInitial:
    def test_fuse_not_tripped_initially(self, fuse):
        assert not fuse.is_tripped()

    def test_remaining_cooldown_zero_when_not_tripped(self, fuse):
        assert fuse.remaining_cooldown_sec() == 0.0

    def test_status_has_required_fields(self, fuse):
        status = fuse.status()
        assert isinstance(status, dict)
        assert "tripped" in status
        assert "remaining_cooldown_sec" in status
        assert "consecutive_streak" in status


class TestFuseTripping:
    def test_high_weight_trips_fuse(self, fuse):
        # threshold_pct=80 → trips at >80% of 6000 = >4800
        tripped = fuse.check_weight(5000)
        assert tripped is True
        assert fuse.is_tripped()

    def test_weight_below_threshold_does_not_trip(self, fuse):
        tripped = fuse.check_weight(2000)
        assert not tripped
        assert not fuse.is_tripped()

    def test_error_code_1003_trips_fuse(self, fuse):
        fuse.on_error_code(-1003)
        assert fuse.is_tripped()

    def test_error_code_429_trips_fuse(self, fuse):
        fuse.on_error_code(429)
        assert fuse.is_tripped()

    def test_benign_error_does_not_trip(self, fuse):
        fuse.on_error_code(-1121)  # Invalid symbol — not fatal
        assert not fuse.is_tripped()


class TestFuseReset:
    def test_manual_reset_clears_trip(self, fuse):
        fuse.check_weight(5000)
        assert fuse.is_tripped()
        fuse.manual_reset()
        assert not fuse.is_tripped()

    def test_manual_reset_clears_streak(self, fuse):
        fuse.check_weight(5000)
        fuse.manual_reset()
        assert fuse.status()["consecutive_streak"] == 0

    def test_remaining_cooldown_positive_when_tripped(self, fuse):
        fuse.check_weight(5000)
        assert fuse.remaining_cooldown_sec() > 0


class TestFuseSingleton:
    def test_singleton_returns_same_instance(self):
        a = get_api_fuse()
        b = get_api_fuse()
        assert a is b
