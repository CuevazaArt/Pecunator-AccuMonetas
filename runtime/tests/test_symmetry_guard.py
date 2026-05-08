"""Tests for SymmetryGuard — symmetric hub pre-flight validator."""
import asyncio
import pytest
from decimal import Decimal
from unittest.mock import MagicMock

from runtime.core.symmetry_guard import SymmetryGuard, HubHealth


def _cfg(symbol="XRPUSDT", qty=Decimal("6"), rungs=3, sl=Decimal("0")):
    """Create a mock config with the needed attrs."""
    c = MagicMock()
    c.symbol = symbol
    c.quote_order_qty = qty
    c.max_rungs_per_symbol = rungs
    c.stop_loss_pct = sl
    return c


# ── Config-only checks (no API calls) ────────────────────────────

class TestConfigOnly:
    def test_matching_configs_clear(self):
        guard = SymmetryGuard()
        h = guard.check_config_only(_cfg(), _cfg())
        assert h.cleared is True
        assert h.blockers == []

    def test_symbol_mismatch_blocks(self):
        guard = SymmetryGuard()
        h = guard.check_config_only(_cfg("XRPUSDT"), _cfg("BTCUSDT"))
        assert h.cleared is False
        assert any("SYMBOL_MISMATCH" in b for b in h.blockers)

    def test_asymmetric_exposure_warns(self):
        guard = SymmetryGuard()
        h = guard.check_config_only(_cfg(qty=Decimal("6")), _cfg(qty=Decimal("10")))
        assert h.cleared is True  # Warning, not blocker
        assert any("EXPOSURE_ASYMMETRIC" in w for w in h.warnings)

    def test_dorothy_stop_loss_warns(self):
        guard = SymmetryGuard()
        h = guard.check_config_only(_cfg(sl=Decimal("0.15")), _cfg())
        assert h.cleared is True
        assert any("STOP_LOSS" in w for w in h.warnings)

    def test_no_stop_loss_no_warning(self):
        guard = SymmetryGuard()
        h = guard.check_config_only(_cfg(sl=Decimal("0")), _cfg())
        assert not any("STOP_LOSS" in w for w in h.warnings)

    def test_exposure_calculation(self):
        guard = SymmetryGuard()
        h = guard.check_config_only(_cfg(qty=Decimal("6"), rungs=3), _cfg(qty=Decimal("6"), rungs=3))
        assert h.dorothy_exposure == Decimal("18")
        assert h.elphaba_exposure == Decimal("18")


# ── Order failure tracking ────────────────────────────────────────

class TestOrderFailureTracking:
    def test_success_resets_counter(self):
        guard = SymmetryGuard()
        guard.record_order_failure("dorothy:XRPUSDT", "timeout")
        guard.record_order_failure("dorothy:XRPUSDT", "timeout")
        guard.record_order_success("dorothy:XRPUSDT")
        assert not guard.is_hub_paused()

    def test_three_failures_pauses_hub(self):
        guard = SymmetryGuard()
        guard.record_order_failure("elphaba:XRPUSDT", "insufficient balance")
        guard.record_order_failure("elphaba:XRPUSDT", "insufficient balance")
        assert not guard.is_hub_paused()
        guard.record_order_failure("elphaba:XRPUSDT", "insufficient balance")
        assert guard.is_hub_paused()
        assert "elphaba:XRPUSDT" in guard.get_pause_reason()
        assert "3 consecutive" in guard.get_pause_reason()

    def test_pause_blocks_config_check(self):
        guard = SymmetryGuard()
        guard.record_order_failure("x", "e")
        guard.record_order_failure("x", "e")
        guard.record_order_failure("x", "e")
        h = guard.check_config_only(_cfg(), _cfg())
        assert h.cleared is False
        assert any("HUB_PAUSED" in b for b in h.blockers)

    def test_reset_unpauses(self):
        guard = SymmetryGuard()
        for _ in range(3):
            guard.record_order_failure("x", "e")
        assert guard.is_hub_paused()
        guard.reset_pause()
        assert not guard.is_hub_paused()
        h = guard.check_config_only(_cfg(), _cfg())
        assert h.cleared is True


# ── HubHealth serialization ───────────────────────────────────────

class TestHubHealth:
    def test_as_json(self):
        h = HubHealth(
            cleared=True,
            spot_usdt_free=Decimal("50"),
            margin_usdt_free=Decimal("20"),
            dorothy_exposure=Decimal("18"),
            elphaba_exposure=Decimal("18"),
            dorothy_symbol="XRPUSDT",
            elphaba_symbol="XRPUSDT",
            ts=1715200000.0,
        )
        j = h.as_json()
        assert j["cleared"] is True
        assert j["spot_usdt_free"] == "50"
        assert j["dorothy_symbol"] == "XRPUSDT"
        assert "ts_iso" in j

    def test_blockers_in_json(self):
        h = HubHealth(blockers=["SYMBOL_MISMATCH: test"])
        j = h.as_json()
        assert len(j["blockers"]) == 1
        assert "SYMBOL_MISMATCH" in j["blockers"][0]


# ── Preflight with mock client ────────────────────────────────────

class TestPreflight:
    def _mock_client(self, usdt_free="50.0", margin_free="20.0"):
        client = MagicMock()
        client.get_account.return_value = {
            "balances": [
                {"asset": "USDT", "free": usdt_free, "locked": "0"},
                {"asset": "XRP", "free": "100", "locked": "0"},
            ]
        }
        client.get_isolated_margin_account.return_value = {
            "assets": [{
                "quoteAsset": {"free": margin_free, "netAsset": margin_free},
                "baseAsset": {"free": "0", "netAsset": "0"},
            }]
        }
        return client

    def test_sufficient_capital_clears(self):
        guard = SymmetryGuard()
        client = self._mock_client(usdt_free="100.0", margin_free="20.0")
        h = asyncio.get_event_loop().run_until_complete(
            guard.preflight(client, _cfg(), _cfg())
        )
        assert h.cleared is True

    def test_low_spot_capital_blocks(self):
        guard = SymmetryGuard()
        client = self._mock_client(usdt_free="5.0")
        h = asyncio.get_event_loop().run_until_complete(
            guard.preflight(client, _cfg(), _cfg())
        )
        assert h.cleared is False
        assert any("SPOT_CAPITAL_LOW" in b for b in h.blockers)

    def test_symbol_mismatch_blocks_preflight(self):
        guard = SymmetryGuard()
        client = self._mock_client(usdt_free="200.0")
        h = asyncio.get_event_loop().run_until_complete(
            guard.preflight(client, _cfg("XRPUSDT"), _cfg("BTCUSDT"))
        )
        assert h.cleared is False
        assert any("SYMBOL_MISMATCH" in b for b in h.blockers)

    def test_cache_returns_previous(self):
        guard = SymmetryGuard()
        client = self._mock_client(usdt_free="100.0")
        h1 = asyncio.get_event_loop().run_until_complete(
            guard.preflight(client, _cfg(), _cfg())
        )
        h2 = guard.get_cached_health()
        assert h2 is not None
        assert h2.cleared == h1.cleared


# ── Capital Allocator (75/25) ─────────────────────────────────────

class TestCapitalAllocator:
    def test_bullish_75_spot_25_margin(self):
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("100"), "BULLISH")
        assert alloc["cleared"] is True
        assert Decimal(alloc["spot_target"]) == Decimal("75")
        assert Decimal(alloc["margin_target"]) == Decimal("25")

    def test_bearish_25_spot_75_margin(self):
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("100"), "BEARISH")
        assert Decimal(alloc["spot_target"]) == Decimal("25")
        assert Decimal(alloc["margin_target"]) == Decimal("75")

    def test_neutral_50_50(self):
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("100"), "NEUTRAL")
        assert Decimal(alloc["spot_target"]) == Decimal("50")
        assert Decimal(alloc["margin_target"]) == Decimal("50")

    def test_minimum_72_usdt_bullish(self):
        """72 USDT = minimum viable. BULLISH → 54 Spot, 18 Margin."""
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("72"), "BULLISH")
        assert alloc["cleared"] is True
        assert Decimal(alloc["spot_target"]) == Decimal("54")
        assert Decimal(alloc["margin_target"]) == Decimal("18")

    def test_minimum_72_usdt_bearish(self):
        """72 USDT BEARISH → 18 Spot, 54 Margin."""
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("72"), "BEARISH")
        assert Decimal(alloc["spot_target"]) == Decimal("18")
        assert Decimal(alloc["margin_target"]) == Decimal("54")

    def test_floor_enforced_at_18(self):
        """Even with small capital, both sides get >= 18."""
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("40"), "BULLISH")
        # 40 × 0.75 = 30, 40 × 0.25 = 10 < 18 → floor kicks in
        assert Decimal(alloc["margin_target"]) >= Decimal("18")

    def test_insufficient_capital_blocks(self):
        """Below 36 USDT (18×2) → not cleared."""
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("30"), "BULLISH")
        assert alloc["cleared"] is False
        assert "CAPITAL_INSUFFICIENT" in alloc.get("blocker", "")

    def test_ops_capacity_matches(self):
        """100 USDT BULLISH: Spot=75/6=12 ops, Margin=25/6=4 ops."""
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("100"), "BULLISH")
        assert alloc["spot_ops_capacity"] == 12
        assert alloc["margin_ops_capacity"] == 4

    def test_ops_reserve_minimum_3(self):
        """72 USDT: inactive wallet = 18 USDT = 3 operations minimum."""
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("72"), "BULLISH")
        assert alloc["margin_ops_capacity"] >= 3  # 18/6 = 3

    def test_150_usdt_bullish(self):
        guard = SymmetryGuard()
        alloc = guard.compute_allocation(Decimal("150"), "BULLISH")
        assert Decimal(alloc["spot_target"]) == Decimal("112.5")
        assert Decimal(alloc["margin_target"]) == Decimal("37.5")
        assert alloc["spot_ops_capacity"] == 18
        assert alloc["margin_ops_capacity"] == 6

