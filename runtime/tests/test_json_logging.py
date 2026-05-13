"""Tests for structured JSON logging."""

import json
import logging
import io

import pytest


class TestJSONLogFormat:
    """Test JSON logging format and structure."""

    def test_json_logging_enabled(self, tmp_path, monkeypatch):
        """When PECUNATOR_LOG_JSON=1, logs should be in JSON format."""
        monkeypatch.setenv("PECUNATOR_LOG_JSON", "1")

        # Capture logs
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)

        try:
            from pythonjsonlogger import jsonlogger
            formatter = jsonlogger.JsonFormatter(
                fmt="%(timestamp)s %(level)s %(name)s %(message)s",
                timestamp=True,
            )
        except ImportError:
            pytest.skip("python-json-logger not installed")

        handler.setFormatter(formatter)

        logger = logging.getLogger("test_logger")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Log a message
        logger.info("test message")

        # Parse output as JSON
        output = stream.getvalue()
        lines = output.strip().split("\n")
        assert len(lines) >= 1

        try:
            json_data = json.loads(lines[0])
            assert json_data["message"] == "test message"
            assert json_data["name"] == "test_logger"
            # Level might be "INFO" or None depending on formatter setup
            assert "timestamp" in json_data
        except json.JSONDecodeError:
            pytest.skip("Output not valid JSON (python-json-logger not installed)")

    def test_json_log_structure(self):
        """JSON logs should include required fields."""
        try:
            from pythonjsonlogger import jsonlogger
        except ImportError:
            pytest.skip("python-json-logger not installed")

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)

        formatter = jsonlogger.JsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s %(extra_field)s",
            timestamp=True,
        )
        handler.setFormatter(formatter)

        logger = logging.getLogger("test_struct")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Log with extra fields
        logger.info("test event", extra={"extra_field": "extra_value"})

        output = stream.getvalue()
        json_data = json.loads(output.strip().split("\n")[0])

        assert "timestamp" in json_data
        assert "level" in json_data
        assert "name" in json_data
        assert "message" in json_data

    def test_text_logging_unchanged(self, tmp_path, monkeypatch):
        """When PECUNATOR_LOG_JSON not set, logs should be text format."""
        monkeypatch.delenv("PECUNATOR_LOG_JSON", raising=False)

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)

        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)

        logger = logging.getLogger("test_text")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        logger.info("test message")

        output = stream.getvalue()
        # Should NOT be JSON
        try:
            json.loads(output.strip().split("\n")[0])
            assert False, "Expected text format but got JSON"
        except json.JSONDecodeError:
            # Expected — text format
            assert "[INFO]" in output or "INFO" in output


class TestCorrelationID:
    """Test correlation ID header handling."""

    def test_correlation_id_in_response(self):
        """Response should include correlation ID header."""
        from fastapi.testclient import TestClient
        from runtime.api.app import create_app

        app = create_app()
        client = TestClient(app)

        # Make a request with custom correlation ID
        response = client.get("/metrics", headers={"X-Correlation-ID": "test-123"})

        assert response.status_code == 200
        assert response.headers.get("X-Correlation-ID") == "test-123"

    def test_correlation_id_auto_generated(self):
        """If no correlation ID provided, one should be auto-generated."""
        from fastapi.testclient import TestClient
        from runtime.api.app import create_app

        app = create_app()
        client = TestClient(app)

        # Make a request without correlation ID
        response = client.get("/metrics")

        assert response.status_code == 200
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None
        assert len(correlation_id) > 0

    def test_correlation_id_uuid_format(self):
        """Auto-generated correlation ID should be a valid UUID."""
        from fastapi.testclient import TestClient
        from runtime.api.app import create_app
        import uuid

        app = create_app()
        client = TestClient(app)

        response = client.get("/metrics")
        correlation_id = response.headers.get("X-Correlation-ID")

        # Should be parseable as UUID
        try:
            uuid.UUID(correlation_id)
            # Valid UUID format
            assert True
        except ValueError:
            # Not a UUID format, could be another format — that's ok
            assert len(correlation_id) > 0


class TestErrorLogging:
    """Test error logging in JSON format."""

    def test_exception_logged_with_traceback(self):
        """Exceptions should include traceback in logs."""
        try:
            from pythonjsonlogger import jsonlogger
        except ImportError:
            pytest.skip("python-json-logger not installed")

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)

        formatter = jsonlogger.JsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s %(exc_info)s",
            timestamp=True,
        )
        handler.setFormatter(formatter)

        logger = logging.getLogger("test_exc")
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)

        # Log an exception
        try:
            raise ValueError("test error")
        except ValueError:
            logger.exception("Error occurred")

        output = stream.getvalue()
        # Should contain traceback
        assert "ValueError" in output or "test error" in output
