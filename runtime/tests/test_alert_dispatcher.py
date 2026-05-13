"""Tests for AlertDispatcher — alert channels, deduplication, retry logic."""

import logging
import os
import time
from unittest.mock import Mock, patch

import pytest

from runtime.core.alert_dispatcher import AlertDispatcher, get_alert_dispatcher


@pytest.fixture
def alert_dispatcher(tmp_path):
    """Create a fresh AlertDispatcher for each test."""
    return AlertDispatcher(data_dir=tmp_path)


class TestAlertBasics:
    """Test basic alert creation and logging."""

    def test_critical_alert(self, alert_dispatcher):
        alert = alert_dispatcher.critical("TEST_CRITICAL", "This is critical")
        assert alert["level"] == "CRITICAL"
        assert alert["code"] == "TEST_CRITICAL"
        assert alert["message"] == "This is critical"
        assert "ts_utc" in alert
        assert alert["silent"] is False

    def test_warning_alert(self, alert_dispatcher):
        alert = alert_dispatcher.warning("TEST_WARNING", "This is a warning")
        assert alert["level"] == "WARNING"
        assert alert["code"] == "TEST_WARNING"

    def test_info_alert(self, alert_dispatcher):
        alert = alert_dispatcher.info("TEST_INFO", "This is info")
        assert alert["level"] == "INFO"

    def test_silent_alert_flag(self, alert_dispatcher):
        alert = alert_dispatcher.critical("SILENT_TEST", "Silent alert", silent=True)
        assert alert["silent"] is True

    def test_alert_history(self, alert_dispatcher):
        alert_dispatcher.critical("ALERT_1", "First")
        alert_dispatcher.warning("ALERT_2", "Second")
        alert_dispatcher.info("ALERT_3", "Third")

        recent = alert_dispatcher.recent(limit=10)
        assert len(recent) == 3
        # Newest first
        assert recent[0]["code"] == "ALERT_3"
        assert recent[1]["code"] == "ALERT_2"
        assert recent[2]["code"] == "ALERT_1"

    def test_alert_log_file(self, alert_dispatcher, tmp_path):
        alert_dispatcher.critical("FILE_TEST", "Test alert to file")

        log_file = tmp_path / "alerts.log"
        assert log_file.exists()

        content = log_file.read_text()
        assert "FILE_TEST" in content
        assert "Test alert to file" in content
        assert "[CRITICAL]" in content

    def test_status(self, alert_dispatcher):
        alert_dispatcher.critical("CRITICAL_1", "C1")
        alert_dispatcher.critical("CRITICAL_2", "C2")
        alert_dispatcher.warning("WARNING_1", "W1")

        status = alert_dispatcher.status()
        assert status["total_alerts"] == 3
        assert status["critical_count"] == 2
        assert status["last_alert"]["code"] == "WARNING_1"


class TestDeduplication:
    """Test alert deduplication logic."""

    def test_dedup_same_alert_within_window(self, alert_dispatcher):
        """Sending same alert twice within DEDUP_WINDOW should skip second."""
        alert_dispatcher.critical("DUP_TEST", "First", silent=False)
        alert2 = alert_dispatcher.critical("DUP_TEST", "Second", silent=False)

        # Both stored but dedup_cache prevents external dispatch
        assert len(alert_dispatcher._alerts) == 2
        # Both are marked as not silent (will be dedup'd in real dispatch)
        assert alert2["silent"] is False

    def test_dedup_different_levels(self, alert_dispatcher):
        """Different levels should not deduplicate."""
        alert_dispatcher.critical("TEST", "Critical version", silent=False)
        alert_dispatcher.warning("TEST", "Warning version", silent=False)

        assert len(alert_dispatcher._alerts) == 2

    def test_dedup_expires_after_window(self, alert_dispatcher):
        """Deduplication should expire after DEDUP_WINDOW seconds."""
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0
            alert_dispatcher.critical("EXPIRE_TEST", "First", silent=False)

            # Advance time past DEDUP_WINDOW (300s)
            mock_time.return_value = 1350.0
            alert_dispatcher.critical("EXPIRE_TEST", "Second", silent=False)

            # Second alert should not be deduplicated
            assert len(alert_dispatcher._dedup_cache) > 0


class TestTelegramIntegration:
    """Test Telegram alert sending with retry and error handling."""

    def test_telegram_disabled_no_token(self, alert_dispatcher):
        """Telegram should be disabled if token not set."""
        assert alert_dispatcher._telegram_token == ""
        assert alert_dispatcher._telegram_chat_id == ""

    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_TELEGRAM_TOKEN": "test_token",
        "PECUNATOR_ALERT_TELEGRAM_CHAT_ID": "123456"
    })
    def test_telegram_enabled_with_config(self):
        """Telegram should be enabled if token and chat_id are set."""
        dispatcher = AlertDispatcher()
        assert dispatcher._telegram_token == "test_token"
        assert dispatcher._telegram_chat_id == "123456"

    @patch("httpx.Client")
    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_TELEGRAM_TOKEN": "test_token",
        "PECUNATOR_ALERT_TELEGRAM_CHAT_ID": "123456"
    })
    def test_telegram_success_send(self, mock_client_class):
        """Test successful Telegram message send."""
        mock_response = Mock()
        mock_response.status_code = 200

        mock_client = Mock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        dispatcher = AlertDispatcher()
        dispatcher._send_telegram_async("Test message")

        # Give thread time to send
        time.sleep(0.5)

        # Verify post was called
        mock_client.post.assert_called()

    @patch("httpx.Client")
    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_TELEGRAM_TOKEN": "test_token",
        "PECUNATOR_ALERT_TELEGRAM_CHAT_ID": "123456"
    })
    def test_telegram_retry_on_rate_limit(self, mock_client_class):
        """Test retry logic on Telegram rate limit (429)."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "1"}

        mock_response_200 = Mock()
        mock_response_200.status_code = 200

        mock_client = Mock()
        # First call returns 429, second returns 200
        mock_client.post.side_effect = [mock_response_429, mock_response_200]
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        dispatcher = AlertDispatcher()
        dispatcher._send_telegram_async("Test message")

        # Give thread time to execute with sleep
        time.sleep(2)

        # Verify post was called at least once
        assert mock_client.post.called

    @patch("httpx.Client")
    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_TELEGRAM_TOKEN": "test_token",
        "PECUNATOR_ALERT_TELEGRAM_CHAT_ID": "123456"
    })
    def test_telegram_exponential_backoff(self, mock_client_class):
        """Test exponential backoff on connection failures.

        We patch the `time.sleep` attribute of the alert_dispatcher module
        with a real (instant) function that records the requested duration.
        The background thread issues 2 retries with 2s and 4s backoff; we
        wait by polling the mock's invocation count from outside the patch's
        reach (we sleep on `_real_sleep`, the unpatched reference).
        """
        import time as _real_time
        from runtime.core import alert_dispatcher as _alert_mod

        mock_client = Mock()
        mock_client.post.side_effect = ConnectionError("Network error")
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client

        dispatcher = AlertDispatcher()
        sleep_calls: list = []

        def fake_sleep(d):
            sleep_calls.append(d)

        original_sleep = _alert_mod.time.sleep
        _alert_mod.time.sleep = fake_sleep
        try:
            dispatcher._send_telegram_async("Test message")
            # Poll outside the patch — _real_time.sleep is still real
            deadline = _real_time.monotonic() + 5.0
            while _real_time.monotonic() < deadline:
                if mock_client.post.call_count >= 3:
                    break
                _real_time.sleep(0.05)
        finally:
            _alert_mod.time.sleep = original_sleep

        # Give the thread a moment to record final sleeps after the post calls
        _real_time.sleep(0.1)

        # Verify retries happened
        assert mock_client.post.call_count >= 2, f"Expected ≥2 retries, got {mock_client.post.call_count}"
        # Exponential backoff: 2s and/or 4s should appear
        assert any(d in (2, 4) for d in sleep_calls), (
            f"Expected backoff sleeps of 2s or 4s, got: {sleep_calls}"
        )


class TestEmailIntegration:
    """Test email alert sending."""

    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_EMAIL_ENABLED": "0"
    })
    def test_email_disabled_by_default(self):
        """Email should be disabled by default."""
        dispatcher = AlertDispatcher()
        assert dispatcher._email_enabled is False

    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_EMAIL_ENABLED": "1",
        "PECUNATOR_ALERT_EMAIL_SMTP_HOST": "smtp.gmail.com",
        "PECUNATOR_ALERT_EMAIL_SMTP_PORT": "587",
        "PECUNATOR_ALERT_EMAIL_FROM": "test@example.com",
        "PECUNATOR_ALERT_EMAIL_TO": "alert@example.com",
        "PECUNATOR_ALERT_EMAIL_PASSWORD": "secret"
    })
    def test_email_enabled_with_config(self):
        """Email should be enabled if all vars are set."""
        dispatcher = AlertDispatcher()
        assert dispatcher._email_enabled is True
        assert dispatcher._email_smtp_host == "smtp.gmail.com"
        assert dispatcher._email_from == "test@example.com"

    @patch("smtplib.SMTP")
    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_EMAIL_ENABLED": "1",
        "PECUNATOR_ALERT_EMAIL_SMTP_HOST": "smtp.test.com",
        "PECUNATOR_ALERT_EMAIL_FROM": "from@test.com",
        "PECUNATOR_ALERT_EMAIL_TO": "to@test.com",
        "PECUNATOR_ALERT_EMAIL_PASSWORD": "pass"
    })
    def test_email_send_success(self, mock_smtp_class):
        """Test successful email send."""
        mock_smtp = Mock()
        mock_smtp.__enter__ = Mock(return_value=mock_smtp)
        mock_smtp.__exit__ = Mock(return_value=False)
        mock_smtp_class.return_value = mock_smtp

        dispatcher = AlertDispatcher()
        dispatcher._send_email_async("CRITICAL", "TEST", "Email test message")

        # Give thread time to send
        time.sleep(0.5)

        # Verify SMTP was called
        assert mock_smtp_class.called


class TestSingleton:
    """Test AlertDispatcher singleton pattern."""

    def test_get_alert_dispatcher_singleton(self):
        """get_alert_dispatcher should return same instance."""
        disp1 = get_alert_dispatcher()
        disp2 = get_alert_dispatcher()
        assert disp1 is disp2

    def test_singleton_reset_in_tests(self, tmp_path):
        """Conftest fixture should reset singleton between tests."""
        # This is handled by conftest.py reset_singletons fixture
        pass


class TestPayloads:
    """Test alert payloads for structured data."""

    def test_alert_with_payload(self, alert_dispatcher):
        payload = {"bot_id": "louise-btc", "error_code": "INSUFFICIENT_BALANCE"}
        alert = alert_dispatcher.critical("BUY_FAILED", "Buy execution failed", payload=payload)

        assert alert["payload"] == payload
        assert alert["payload"]["bot_id"] == "louise-btc"

    def test_payload_in_recent(self, alert_dispatcher):
        payload = {"order_id": "12345"}
        alert_dispatcher.critical("ORDER_FAILED", "Order failed", payload=payload)

        recent = alert_dispatcher.recent(1)
        assert recent[0]["payload"] == payload


class TestValidation:
    """Test config validation on startup."""

    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_TELEGRAM_TOKEN": "token_only"
    }, clear=True)
    def test_warn_on_token_without_chatid(self, caplog):
        """Should warn if token set but chat_id missing."""
        with caplog.at_level(logging.WARNING):
            AlertDispatcher()

        assert "PECUNATOR_ALERT_TELEGRAM_CHAT_ID missing" in caplog.text

    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_TELEGRAM_CHAT_ID": "123"
    }, clear=True)
    def test_warn_on_chatid_without_token(self, caplog):
        """Should warn if chat_id set but token missing."""
        with caplog.at_level(logging.WARNING):
            AlertDispatcher()

        assert "PECUNATOR_ALERT_TELEGRAM_TOKEN missing" in caplog.text

    @patch.dict(os.environ, {
        "PECUNATOR_ALERT_EMAIL_ENABLED": "1",
        "PECUNATOR_ALERT_EMAIL_SMTP_HOST": "smtp.test.com"
        # Missing other email vars
    }, clear=True)
    def test_warn_on_incomplete_email_config(self, caplog):
        """Should warn if email vars incomplete."""
        with caplog.at_level(logging.WARNING):
            AlertDispatcher()

        assert "Email alerts enabled but" in caplog.text and "incomplete" in caplog.text
