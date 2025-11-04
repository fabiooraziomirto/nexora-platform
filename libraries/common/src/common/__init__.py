"""
Common library for Stack4Things v2.0

Shared utilities for all microservices.
"""

__version__ = "0.1.0"

from common.config import settings
from common.database import get_db_session, Base, init_db, close_db
from common.events import EventBus, EventBusType, get_event_bus
from common.cache import Cache, get_cache
from common.logging import setup_logging, get_logger
from common.errors import (
    Stack4ThingsError,
    ValidationError,
    NotFoundError,
    ConflictError,
    UnauthorizedError,
    ForbiddenError,
    DatabaseError,
    ExternalServiceError,
)
from common.health import HealthChecker, HealthStatus, check_health
from common.metrics import Metrics, get_metrics

__all__ = [
    "__version__",
    "settings",
    "get_db_session",
    "Base",
    "init_db",
    "close_db",
    "EventBus",
    "EventBusType",
    "get_event_bus",
    "Cache",
    "get_cache",
    "setup_logging",
    "get_logger",
    "Stack4ThingsError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "UnauthorizedError",
    "ForbiddenError",
    "DatabaseError",
    "ExternalServiceError",
    "HealthChecker",
    "HealthStatus",
    "check_health",
    "Metrics",
    "get_metrics",
]
