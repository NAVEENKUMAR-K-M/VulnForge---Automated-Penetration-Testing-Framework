"""
Structured logging configuration for VulnForge.

Architecture Decision:
    Uses ``structlog`` for structured, context-aware logging.  In production
    (``LOG_FORMAT=JSON``) every log line is a JSON object parseable by
    log aggregators (Datadog, Splunk, CloudWatch).  In development
    (``LOG_FORMAT=CONSOLE``) output is human-readable with colours.

    Bound context (request_id, user_id, scan_id) travels with every log
    line inside a single request without explicit passing via ``structlog``'s
    thread-local context vars.

Usage:
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("scan.started", scan_id=str(scan.id), target=target.value)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger


def _add_app_context(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """structlog processor: inject application-level context.

    Adds ``app`` and ``environment`` to every log event so log aggregators
    can filter by application name and deployment environment without
    needing to configure a separate log stream per environment.

    Args:
        logger:      The wrapped logger instance.
        method_name: The log level method name (e.g., 'info', 'error').
        event_dict:  The current log event dictionary.

    Returns:
        EventDict: The mutated event dictionary.
    """
    # Imported inside the function to avoid a circular import at module load
    # time — config imports logging, so logging must not import config at the
    # top level.
    try:
        from app.core.config import get_settings
        settings = get_settings()
        event_dict["app"] = settings.app_name
        event_dict["env"] = settings.app_env
        event_dict["version"] = settings.app_version
    except Exception:  # noqa: BLE001 — settings not yet loaded during tests
        event_dict["app"] = "vulnforge"
    return event_dict


def configure_logging(log_level: str = "INFO", log_format: str = "CONSOLE") -> None:
    """Configure structlog and stdlib logging for the application.

    Call this once during application startup (in ``lifespan.py``).

    Args:
        log_level:  One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        log_format: ``'JSON'`` for production, ``'CONSOLE'`` for development.
    """
    # Shared processors applied to every log event regardless of output format
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _add_app_context,
    ]

    if log_format == "JSON":
        # Production: emit newline-delimited JSON — parseable by log aggregators
        processors: list[Any] = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: human-readable, colour-coded console output
        processors = [
            *shared_processors,
            structlog.processors.ExceptionRenderer(),
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib ``logging`` calls through structlog so third-party libraries
    # (SQLAlchemy, httpx, celery) produce structured output too.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(log_level),
    )

    # Silence overly chatty libraries in production
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if log_level == "DEBUG" else logging.WARNING
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a structlog BoundLogger bound to the given module name.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        structlog.BoundLogger: A logger instance with module name bound.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user.created", user_id="abc-123")
    """
    return structlog.get_logger(name)
