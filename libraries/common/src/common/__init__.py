"""
Common library for Nxr v2.0

Shared utilities for all microservices.
"""

from importlib import import_module

__version__ = "0.1.0"


_EXPORTS = {
    "settings": ("common.config", "settings"),
    "get_db_session": ("common.database", "get_db_session"),
    "Base": ("common.database", "Base"),
    "init_db": ("common.database", "init_db"),
    "close_db": ("common.database", "close_db"),
    "EventBus": ("common.events", "EventBus"),
    "EventBusType": ("common.events", "EventBusType"),
    "get_event_bus": ("common.events", "get_event_bus"),
    "Cache": ("common.cache", "Cache"),
    "get_cache": ("common.cache", "get_cache"),
    "setup_logging": ("common.logging", "setup_logging"),
    "get_logger": ("common.logging", "get_logger"),
    "NxrError": ("common.errors", "NxrError"),
    "ValidationError": ("common.errors", "ValidationError"),
    "NotFoundError": ("common.errors", "NotFoundError"),
    "ConflictError": ("common.errors", "ConflictError"),
    "UnauthorizedError": ("common.errors", "UnauthorizedError"),
    "ForbiddenError": ("common.errors", "ForbiddenError"),
    "DatabaseError": ("common.errors", "DatabaseError"),
    "ExternalServiceError": ("common.errors", "ExternalServiceError"),
    "HealthChecker": ("common.health", "HealthChecker"),
    "HealthStatus": ("common.health", "HealthStatus"),
    "check_health": ("common.health", "check_health"),
    "Metrics": ("common.metrics", "Metrics"),
    "get_metrics": ("common.metrics", "get_metrics"),
    "TenantContext": ("common.tenancy", "TenantContext"),
    "extract_tenant_id": ("common.tenancy", "extract_tenant_id"),
    "DeprecationPolicy": ("common.api_versioning", "DeprecationPolicy"),
    "build_deprecation_headers": ("common.api_versioning", "build_deprecation_headers"),
    "write_audit_event": ("common.audit", "write_audit_event"),
    "KeystoneAdapter": ("common.openstack", "KeystoneAdapter"),
    "KeystoneTokenInfo": ("common.openstack", "KeystoneTokenInfo"),
    "NeutronAdapter": ("common.openstack", "NeutronAdapter"),
    "NovaAdapter": ("common.openstack", "NovaAdapter"),
    "GlanceCinderAdapter": ("common.openstack", "GlanceCinderAdapter"),
}


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module 'common' has no attribute '{name}'")
    module_name, attr_name = _EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

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
    "NxrError",
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
    "TenantContext",
    "extract_tenant_id",
    "DeprecationPolicy",
    "build_deprecation_headers",
    "write_audit_event",
    "KeystoneAdapter",
    "KeystoneTokenInfo",
    "NeutronAdapter",
    "NovaAdapter",
    "GlanceCinderAdapter",
]
