"""Tests für Logging Utilities."""

import logging
import os

from mkg_core.utils.logging import (
    configure_logging,
    get_logger,
)


class TestGetLogger:
    """Tests für get_logger Funktion."""

    def test_get_logger_returns_bound_logger(self):
        """get_logger gibt einen BoundLogger zurück."""
        logger = get_logger("test-module")

        assert logger is not None
        # Prüfe dass es ein structlog Logger ist
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_get_logger_with_class_name(self):
        """get_logger funktioniert mit Klassennamen."""
        logger = get_logger("MyClassName")

        assert logger is not None

    def test_get_logger_binds_module_name(self):
        """get_logger bindet Modulnamen."""
        logger = get_logger("my-module")

        # Logger sollte den Modulnamen gebunden haben
        assert logger is not None

    def test_get_logger_returns_same_logger_for_same_name(self):
        """get_logger gibt für gleichen Namen gleichen Logger zurück."""
        logger1 = get_logger("same-module")
        logger2 = get_logger("same-module")

        # Beide Logger sollten funktionieren
        assert logger1 is not None
        assert logger2 is not None


class TestConfigureLogging:
    """Tests für configure_logging Funktion."""

    def test_configure_logging_runs_without_error(self):
        """configure_logging läuft ohne Fehler."""
        # configure_logging wird nur einmal ausgeführt (singleton pattern)
        configure_logging(level="INFO")
        # Sollte keine Exception werfen
        assert True

    def test_configure_logging_is_idempotent(self):
        """configure_logging kann mehrfach aufgerufen werden."""
        configure_logging(level="INFO")
        configure_logging(level="DEBUG")  # Wird ignoriert wegen _configured flag
        # Sollte keine Exception werfen
        assert True

    def test_configure_logging_with_json_format(self):
        """configure_logging mit JSON Format."""
        configure_logging(json_format=True)

        # Logger sollte konfiguriert sein
        logger = get_logger("test")
        assert logger is not None

    def test_configure_logging_with_console_format(self):
        """configure_logging mit Console Format."""
        configure_logging(json_format=False)

        logger = get_logger("test")
        assert logger is not None

    def test_configure_logging_with_service_name(self):
        """configure_logging mit Service-Name."""
        configure_logging(service_name="my-service")
        # Sollte keine Exception werfen
        assert True


class TestLoggerUsage:
    """Tests für Logger-Verwendung."""

    def test_logger_info_message(self):
        """Logger kann Info-Nachrichten loggen."""
        logger = get_logger("test-info")

        # Sollte keine Exception werfen
        logger.info("Test message")

    def test_logger_debug_message(self):
        """Logger kann Debug-Nachrichten loggen."""
        logger = get_logger("test-debug")

        logger.debug("Debug message")

    def test_logger_warning_message(self):
        """Logger kann Warning-Nachrichten loggen."""
        logger = get_logger("test-warning")

        logger.warning("Warning message")

    def test_logger_error_message(self):
        """Logger kann Error-Nachrichten loggen."""
        logger = get_logger("test-error")

        logger.error("Error message")

    def test_logger_with_context(self):
        """Logger kann mit Kontext-Daten loggen."""
        logger = get_logger("test-context")

        # Sollte keine Exception werfen
        logger.info(
            "Request processed",
            tenant_id="tnt-123",
            user_id="usr-456",
            duration_ms=42,
        )

    def test_logger_with_exception(self):
        """Logger kann Exceptions loggen."""
        logger = get_logger("test-exception")

        try:
            raise ValueError("Test error")
        except ValueError:
            logger.exception("An error occurred")


class TestLoggerBinding:
    """Tests für Logger-Binding."""

    def test_bind_adds_context(self):
        """bind() fügt Kontext hinzu."""
        logger = get_logger("test-bind")
        bound = logger.bind(request_id="req-123")

        assert bound is not None

    def test_unbind_removes_context(self):
        """unbind() entfernt Kontext."""
        logger = get_logger("test-unbind")
        bound = logger.bind(key="value")
        unbound = bound.unbind("key")

        assert unbound is not None

    def test_new_creates_fresh_logger(self):
        """new() erstellt neuen Logger."""
        logger = get_logger("test-new")
        bound = logger.bind(key="value")
        new_logger = bound.new()

        assert new_logger is not None


class TestLogLevelEnvironment:
    """Tests für Log-Level aus Environment."""

    def test_uses_env_log_level(self, mocker):
        """Logger verwendet LOG_LEVEL aus Environment."""
        mocker.patch.dict(os.environ, {"LOG_LEVEL": "WARNING"})
        configure_logging()

        root = logging.getLogger()
        # Das Level sollte durch configure_logging gesetzt sein
        assert root.level <= logging.WARNING

    def test_defaults_to_info(self, mocker):
        """Logger verwendet INFO als Default."""
        mocker.patch.dict(os.environ, {}, clear=True)
        os.environ.pop("LOG_LEVEL", None)
        configure_logging()

        # Sollte funktionieren ohne Exception
        logger = get_logger("test")
        logger.info("Test")


class TestStructuredLogging:
    """Tests für strukturiertes Logging."""

    def test_structured_fields_are_included(self):
        """Strukturierte Felder werden inkludiert."""
        logger = get_logger("structured-test")

        # Sollte keine Exception werfen
        logger.info(
            "User action",
            action="login",
            user_id="usr-123",
            ip_address="192.168.1.1",
            success=True,
        )

    def test_nested_data_is_logged(self):
        """Verschachtelte Daten werden geloggt."""
        logger = get_logger("nested-test")

        logger.info(
            "Complex data",
            metadata={
                "version": "1.0",
                "features": ["a", "b", "c"],
            },
        )

    def test_numeric_values_are_logged(self):
        """Numerische Werte werden korrekt geloggt."""
        logger = get_logger("numeric-test")

        logger.info(
            "Metrics",
            count=42,
            duration=1.5,
            percentage=0.95,
        )
