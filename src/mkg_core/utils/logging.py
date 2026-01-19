"""Structured Logging für die MKG Platform.

Konfiguriert structlog für JSON-basiertes Logging,
optimiert für AWS CloudWatch Logs Insights.

Example:
    >>> from mkg_core.utils.logging import configure_logging, get_logger
    >>> configure_logging(level="INFO")
    >>> logger = get_logger(__name__)
    >>> logger.info("Entity created", entity_id="ent-123", tenant_id="tnt-456")
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any

import structlog
from structlog.types import Processor

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger

# Flag um doppelte Konfiguration zu verhindern
_configured = False


def _add_log_level(
    logger: logging.Logger, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Fügt log_level zum Event hinzu."""
    event_dict["level"] = method_name.upper()
    return event_dict


def _add_service_name(
    logger: logging.Logger, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Fügt service_name zum Event hinzu falls nicht vorhanden."""
    if "service" not in event_dict:
        event_dict["service"] = "mkg-core"
    return event_dict


def configure_logging(
    level: str = "INFO",
    *,
    service_name: str = "mkg-core",
    json_format: bool = True,
) -> None:
    """Konfiguriert structlog für die MKG Platform.

    Args:
        level: Log-Level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        service_name: Name des Service für Log-Einträge.
        json_format: True für JSON-Output (Production), False für Console (Development).

    Example:
        >>> configure_logging(level="DEBUG", service_name="mkg-kernel")
    """
    global _configured

    if _configured:
        return

    # Standard-Logging konfigurieren
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Gemeinsame Prozessoren
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        _add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        # Production: JSON für CloudWatch
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # Development: Farbige Console-Ausgabe
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Formatter für stdlib Handler
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Root Logger konfigurieren
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)

    # Service-Name als Default-Context setzen
    structlog.contextvars.bind_contextvars(service=service_name)

    _configured = True


def get_logger(name: str | None = None) -> BoundLogger:
    """Gibt einen konfigurierten Logger zurück.

    Args:
        name: Name des Loggers (typischerweise __name__).

    Returns:
        Ein BoundLogger mit dem gegebenen Namen.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return structlog.stdlib.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bindet Kontext-Variablen an alle nachfolgenden Log-Einträge.

    Thread-safe durch contextvars.

    Args:
        **kwargs: Key-Value-Paare die zu jedem Log-Eintrag hinzugefügt werden.

    Example:
        >>> bind_context(tenant_id="tnt-123", correlation_id="req-456")
        >>> logger.info("Entity created")  # Enthält tenant_id und correlation_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Entfernt Kontext-Variablen.

    Args:
        *keys: Schlüssel die entfernt werden sollen.

    Example:
        >>> unbind_context("correlation_id")
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Löscht alle Kontext-Variablen.

    Sollte am Anfang jedes Lambda-Invocations aufgerufen werden.

    Example:
        >>> clear_context()
    """
    structlog.contextvars.clear_contextvars()
