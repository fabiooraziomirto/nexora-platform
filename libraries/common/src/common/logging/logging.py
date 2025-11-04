"""
Structured logging utilities using structlog.
"""

import sys
import logging
from typing import Optional, Dict, Any

import structlog
from structlog.types import Processor

from common.config import settings


def setup_logging(
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_file: Optional[str] = None,
) -> None:
    """Setup structured logging."""
    log_level = log_level or settings.LOG_LEVEL
    log_format = log_format or settings.LOG_FORMAT
    log_file = log_file or settings.LOG_FILE

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout if not log_file else open(log_file, "a"),
        level=getattr(logging, log_level.upper()),
    )

    # Configure processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        processors.extend([
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ])
    else:
        processors.extend([
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(),
        ])

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get structured logger instance."""
    return structlog.get_logger(name)


class LoggerAdapter:
    """Logger adapter for adding context to logs."""

    def __init__(self, logger: structlog.BoundLogger, **context):
        self.logger = logger
        self.context = context

    def bind(self, **kwargs) -> "LoggerAdapter":
        """Bind additional context."""
        return LoggerAdapter(self.logger, **{**self.context, **kwargs})

    def _log(self, level: str, msg: str, **kwargs):
        """Log message with context."""
        getattr(self.logger, level.lower())(msg, **{**self.context, **kwargs})

    def debug(self, msg: str, **kwargs):
        """Log debug message."""
        self._log("debug", msg, **kwargs)

    def info(self, msg: str, **kwargs):
        """Log info message."""
        self._log("info", msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """Log warning message."""
        self._log("warning", msg, **kwargs)

    def error(self, msg: str, **kwargs):
        """Log error message."""
        self._log("error", msg, **kwargs)

    def exception(self, msg: str, **kwargs):
        """Log exception message."""
        self._log("exception", msg, exc_info=True, **kwargs)

    def critical(self, msg: str, **kwargs):
        """Log critical message."""
        self._log("critical", msg, **kwargs)

