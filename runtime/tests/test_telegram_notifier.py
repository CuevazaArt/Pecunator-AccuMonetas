"""Tests for TelegramNotifier — status and balance report formatting and dispatching."""

import os
from unittest.mock import Mock, patch
import pytest

from runtime.core.telegram_notifier import TelegramNotifier, get_telegram_notifier


class TestTelegramNotifier:
    """Test suite for TelegramNotifier."""

    @pytest.fixture(autouse=True)
    def clean_notifier(self):
        """Reset notifier singleton."""
        import runtime.core.telegram_notifier as tn
        tn._notifier = None

    @patch("runtime.core.telegram_notifier.get_alert_dispatcher")
    @patch("runtime.core.telegram_notifier.get_subaccount_registry")
    @patch("runtime.core.telegram_notifier.get_account_monitor")
    @patch("runtime.core.telegram_notifier.LouiseDB")
    @patch("runtime.api.louise_service.get_louise_service")
    def test_send_report_compiles_markdown(
        self, mock_get_svc, mock_db_class, mock_get_monitor, mock_get_registry, mock_get_alerts
    ):
        # Mock Alerts
        mock_alerts = Mock()
        mock_alerts._telegram_token = "mock_token"
        mock_alerts._telegram_chat_id = "mock_chat_id"
        mock_get_alerts.return_value = mock_alerts

        # Mock Registry Accounts
        mock_registry = Mock()
        mock_acct = Mock()
        mock_acct.account_id = "bluechip"
        mock_registry.list_active.return_value = [mock_acct]
        mock_get_registry.return_value = mock_registry

        # Mock Account Monitor Snapshot
        mock_monitor = Mock()
        mock_monitor.get_latest_snapshot.return_value = {
            "total_equity": "1000.50",
            "free_usdt": "250.25",
            "locked_usdt": "750.25"
        }
        mock_get_monitor.return_value = mock_monitor

        # Mock Louise DB Bots
        mock_db = Mock()
        mock_db.get_all_bots.return_value = [
            {
                "bot_id": "louise_btc_1",
                "symbol": "BTCUSDT",
                "status": "RUNNING",
                "buy_volume": 10.0,
                "target_profit_pct": 5.0,
            }
        ]
        mock_db_class.return_value = mock_db

        # Mock Running Bot details
        mock_runner = Mock()
        mock_runner.active_epoch = {
            "num_purchases": 2,
            "total_cost": 20.0,
            "avg_buy_price": 50000.0,
        }
        mock_runner.current_price = 51000.0
        mock_runner.usdt_free_balance = 250.25
        
        mock_svc = Mock()
        mock_svc.runners = {"louise_btc_1": mock_runner}
        mock_get_svc.return_value = mock_svc

        # Execute report
        notifier = TelegramNotifier()
        import asyncio
        asyncio.run(notifier.send_report(force=True))

        # Check alert dispatch call
        mock_alerts._send_telegram_async.assert_called_once()
        sent_msg = mock_alerts._send_telegram_async.call_args[0][0]
        
        # Verify content contains compiled data
        assert "PECUANATOR LOUISE - REPORTE DE ESTADO" in sent_msg
        assert "bluechip" in sent_msg
        assert "$1,000.50" in sent_msg
        assert "$250.25" in sent_msg
        assert "louise_btc_1" in sent_msg
        assert "BTCUSDT" in sent_msg
        assert "RUNNING" in sent_msg
        assert "Compras: `2`" in sent_msg
        assert "Comprometido: `$20.00`" in sent_msg
        assert "Precio Promedio: `$50000.0000`" in sent_msg
        assert "Actual: `$51000.0000`" in sent_msg
        assert "+$0.40" in sent_msg  # PnL: position qty = 20 / 50000 = 0.0004. current value = 0.0004 * 51000 = 20.40. PnL = 20.40 - 20 = 0.40
        assert "+2.00%" in sent_msg  # PnL pct: 0.40 / 20 = 2.0%

    @patch("runtime.core.telegram_notifier.get_alert_dispatcher")
    def test_send_report_skips_without_telegram_credentials(self, mock_get_alerts):
        mock_alerts = Mock()
        mock_alerts._telegram_token = ""
        mock_alerts._telegram_chat_id = ""
        mock_get_alerts.return_value = mock_alerts

        notifier = TelegramNotifier()
        import asyncio
        asyncio.run(notifier.send_report(force=True))

        # Should skip sending
        mock_alerts._send_telegram_async.assert_not_called()

    @patch.dict(os.environ, {"LOUISE_TELEGRAM_NOTIFY_INTERVAL_HOURS": "0"})
    @patch("runtime.core.telegram_notifier.get_alert_dispatcher")
    def test_notifier_loop_does_not_start_when_disabled(self, mock_get_alerts):
        mock_alerts = Mock()
        mock_alerts._telegram_token = "mock_token"
        mock_alerts._telegram_chat_id = "mock_chat_id"
        mock_get_alerts.return_value = mock_alerts

        notifier = TelegramNotifier()
        import asyncio
        asyncio.run(notifier.start())

        assert notifier._running is False
        assert notifier._task is None
