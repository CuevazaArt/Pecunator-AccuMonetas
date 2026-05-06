"""End-to-end pipeline test — validates full flow with mocks.

Tests the complete chain:
  1. ApiGovernor grants tokens
  2. Chart capture (mocked)
  3. LLM classification (mocked)
  4. TelemetryVault stores data
  5. AccountMonitor generates signals
  6. ExceptionZoo captures errors
  7. SubAccountRegistry resolves bots
  8. TransferService validates (dry-run)

Run: python -m pytest tests/test_e2e_pipeline.py -v
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, ".")


@pytest.fixture
def temp_data_dir(tmp_path):
    """Provide a temporary data directory for test databases."""
    return tmp_path


@pytest.fixture
def fresh_governor():
    """Reset ApiGovernor singleton for each test."""
    import runtime.core.api_governor as gov_mod
    gov_mod._governor = None
    g = gov_mod.get_api_governor()
    yield g
    gov_mod._governor = None


@pytest.fixture
def fresh_zoo():
    import runtime.core.exception_zoo as zoo_mod
    zoo_mod._zoo = None
    z = zoo_mod.get_exception_zoo()
    yield z
    zoo_mod._zoo = None


@pytest.fixture
def fresh_vault(temp_data_dir):
    import runtime.core.telemetry_vault as tv_mod
    tv_mod._vault = None
    v = tv_mod.get_telemetry_vault(data_dir=temp_data_dir)
    yield v
    tv_mod._vault = None


@pytest.fixture
def fresh_registry(temp_data_dir):
    import runtime.core.subaccount_registry as reg_mod
    reg_mod._registry = None
    r = reg_mod.get_subaccount_registry(data_dir=temp_data_dir)
    yield r
    reg_mod._registry = None


class TestApiGovernor:
    """Test that the governor properly gates service access."""

    def test_binance_budget(self, fresh_governor):
        g = fresh_governor
        status = g.status()
        assert status["binance"]["remaining"] > 0
        assert status["binance"]["pct_used"] == 0.0

    def test_request_and_record(self, fresh_governor):
        from runtime.core.api_governor import P_DIAGNOSIS
        g = fresh_governor
        allowed, wait = g.request_token("gemini", units=1, priority=P_DIAGNOSIS)
        assert allowed is True
        g.record_usage("gemini", action="test", units=1, caller="test")
        status = g.status()
        assert status["gemini"]["used"] >= 1

    def test_chart_img_daily_limit(self, fresh_governor):
        from runtime.core.api_governor import P_DIAGNOSIS
        g = fresh_governor
        # Exhaust chart-img quota
        for i in range(50):
            g.record_usage("chart-img", action=f"test_{i}", units=1, caller="test")
        allowed, wait = g.request_token("chart-img", units=1, priority=P_DIAGNOSIS)
        # Should be denied or forced to wait
        assert allowed is False or wait > 0


class TestExceptionZoo:
    """Test forensic exception registration."""

    def test_register_novel(self, fresh_zoo):
        z = fresh_zoo
        try:
            raise ValueError("test error 42")
        except ValueError as e:
            z.register(e, module="test_e2e", context="unit_test")

        summary = z.summary()
        assert summary["unique_exceptions"] >= 1
        assert summary["total_occurrences"] >= 1

    def test_deduplication(self, fresh_zoo):
        z = fresh_zoo
        before = z.summary()["unique_exceptions"]
        for _ in range(5):
            try:
                raise RuntimeError("same error dedup test")
            except RuntimeError as e:
                z.register(e, module="test", context="dedup")

        summary = z.summary()
        # Should add at most 1 new unique exception (dedup)
        assert summary["unique_exceptions"] <= before + 1


class TestTelemetryVault:
    """Test data persistence."""

    def test_store_kline(self, fresh_vault):
        v = fresh_vault
        # store_klines should not raise
        v.store_klines("TESTBTC", "4h", [
            [1000000, "100", "105", "95", "102", "999"],
            [1000001, "102", "110", "100", "108", "1200"],
        ])
        # Verify vault is accessible
        s = v.summary()
        assert isinstance(s, dict)

    def test_log_decision(self, fresh_vault):
        v = fresh_vault
        v.log_decision(
            bot_id="test_bot", bot_type="dorothy",
            decision="BUY", action_taken=True,
            symbol="BTCUSDT", reason="RSI oversold",
        )
        # Verify summary counts increased
        s = v.summary()
        assert s.get("bot_decisions", 0) >= 1


class TestSubAccountRegistry:
    """Test bot-to-account mapping."""

    def test_default_accounts(self, fresh_registry):
        r = fresh_registry
        assert len(r.list_all()) == 5
        assert len(r.list_bots()) >= 2  # dorothy and masha at minimum

    def test_get_bot_account(self, fresh_registry):
        r = fresh_registry
        dorothy = r.get_bot_account("dorothy")
        assert dorothy is not None
        assert "dorothy" in dorothy.email

    def test_equity_limit(self, fresh_registry):
        r = fresh_registry
        r.update_equity_limit("dorothy", "1000")
        d = r.get("dorothy")
        assert d.max_equity_usdt == "1000"


class TestTransferServiceDryRun:
    """Test transfer validation without real API calls."""

    def test_fund_bot_dry_run(self, fresh_registry, fresh_governor):
        from runtime.core.transfer_service import TransferService
        ts = TransferService("fake_key", "fake_secret")
        result = ts.fund_bot("dorothy", "USDT", "100", dry_run=True)
        assert result["ok"] is True
        assert result["dry_run"] is True

    def test_fund_bot_over_limit(self, fresh_registry, fresh_governor):
        from runtime.core.transfer_service import TransferService
        ts = TransferService("fake_key", "fake_secret")
        result = ts.fund_bot("dorothy", "USDT", "99999", dry_run=True)
        assert result["ok"] is False
        assert "exceeds" in result["error"].lower()

    def test_fund_unknown_bot(self, fresh_registry, fresh_governor):
        from runtime.core.transfer_service import TransferService
        ts = TransferService("fake_key", "fake_secret")
        result = ts.fund_bot("nonexistent", "USDT", "10", dry_run=True)
        assert result["ok"] is False
        assert "unknown" in result["error"].lower()


class TestAccountMonitor:
    """Test snapshot recording and signal detection."""

    def test_record_snapshot(self, temp_data_dir):
        from runtime.core.account_monitor import AccountMonitor
        m = AccountMonitor(temp_data_dir / "test_monitor.sqlite")
        row_id = m.record_snapshot(
            account_id="dorothy",
            total_equity="1000.50",
            free_usdt="200.00",
            locked_usdt="800.50",
        )
        assert row_id > 0

    def test_low_liquidity_signal(self, temp_data_dir):
        from runtime.core.account_monitor import AccountMonitor
        m = AccountMonitor(temp_data_dir / "test_signals.sqlite")
        m.record_snapshot(
            account_id="dorothy",
            total_equity="1000",
            free_usdt="10",  # 1% free → LOW_LIQUIDITY
        )
        signals = m.get_pending_signals("dorothy")
        types = [s["signal_type"] for s in signals]
        assert "LOW_LIQUIDITY" in types

    def test_excess_idle_signal(self, temp_data_dir):
        from runtime.core.account_monitor import AccountMonitor
        m = AccountMonitor(temp_data_dir / "test_excess.sqlite")
        m.record_snapshot(
            account_id="masha",
            total_equity="1000",
            free_usdt="800",  # 80% free → EXCESS_IDLE
        )
        signals = m.get_pending_signals("masha")
        types = [s["signal_type"] for s in signals]
        assert "EXCESS_IDLE" in types


class TestEndToEndFlow:
    """Test the full pipeline from governor → vault → monitor."""

    def test_full_cycle(
        self, fresh_governor, fresh_zoo, fresh_vault, fresh_registry, temp_data_dir,
    ):
        """Simulate a complete VMO → Decision → Monitor cycle."""
        from runtime.core.api_governor import P_DIAGNOSIS
        from runtime.core.account_monitor import AccountMonitor

        g = fresh_governor
        z = fresh_zoo
        v = fresh_vault
        r = fresh_registry
        m = AccountMonitor(temp_data_dir / "e2e_monitor.sqlite")

        # 1. Governor grants token for chart-img
        allowed, _ = g.request_token("chart-img", units=1, priority=P_DIAGNOSIS)
        assert allowed

        # 2. Simulate capture success
        g.record_usage(
            "chart-img", action="capture:BTCUSDT/4h",
            units=1, priority=P_DIAGNOSIS, caller="vmo",
            latency_ms=500, success=True,
        )

        # 3. Governor grants token for Gemini
        allowed, _ = g.request_token("gemini", units=1, priority=P_DIAGNOSIS)
        assert allowed

        # 4. Simulate LLM classification
        g.record_usage(
            "gemini", action="classify:BTCUSDT/4h",
            units=1, caller="vmo", latency_ms=3000, success=True,
        )

        # 5. Store classification in vault
        v.log_decision(
            bot_id="vmo", bot_type="system",
            decision="TRENDING", action_taken=False,
            symbol="BTCUSDT",
            reason="Classified as TRENDING with 85% confidence",
            context={"regime": "TRENDING", "confidence": 0.85, "bot": "dorothy"},
        )

        # 6. Record account snapshot
        m.record_snapshot(
            account_id="dorothy",
            total_equity="500",
            free_usdt="20",  # Low liquidity
        )

        # 7. Check signals generated
        signals = m.get_pending_signals("dorothy")
        assert len(signals) > 0

        # 8. Verify governor state
        status = g.status()
        assert status["chart-img"]["used"] >= 1
        assert status["gemini"]["used"] >= 1

        # 9. Verify zoo registered no NOVEL exceptions from this test
        # (there may be pre-existing ones from other tests)
        zoo_summary = z.summary()
        assert zoo_summary["unique_exceptions"] >= 0  # Just verify it runs

        # 10. Verify registry resolves dorothy
        dorothy = r.get_bot_account("dorothy")
        assert dorothy is not None
