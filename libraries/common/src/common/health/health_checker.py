"""
Health check utilities.
"""

from typing import Dict, Any, Optional, Callable, List
from enum import Enum
import asyncio
from sqlalchemy import text

from common.logging import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class HealthCheck:
    """Individual health check."""

    def __init__(
        self,
        name: str,
        check_fn: Callable,
        critical: bool = True,
        timeout: int = 5,
    ):
        self.name = name
        self.check_fn = check_fn
        self.critical = critical
        self.timeout = timeout

    async def run(self) -> Dict[str, Any]:
        """Run health check."""
        try:
            result = await asyncio.wait_for(
                self.check_fn(),
                timeout=self.timeout,
            )
            
            if isinstance(result, bool):
                return {
                    "status": HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    "message": "OK" if result else "Check failed",
                }
            elif isinstance(result, dict):
                return result
            else:
                return {
                    "status": HealthStatus.HEALTHY,
                    "message": str(result),
                }
        except asyncio.TimeoutError:
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": f"Health check timed out after {self.timeout}s",
            }
        except Exception as e:
            logger.error("Health check failed", name=self.name, error=str(e))
            return {
                "status": HealthStatus.UNHEALTHY,
                "message": str(e),
            }


class HealthChecker:
    """Health checker for multiple components."""

    def __init__(self):
        self.checks: List[HealthCheck] = []

    def add_check(
        self,
        name: str,
        check_fn: Callable,
        critical: bool = True,
        timeout: int = 5,
    ):
        """Add health check."""
        check = HealthCheck(name, check_fn, critical, timeout)
        self.checks.append(check)

    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        for check in self.checks:
            result = await check.run()
            results[check.name] = result
            
            if result["status"] == HealthStatus.UNHEALTHY:
                if check.critical:
                    overall_status = HealthStatus.UNHEALTHY
                else:
                    overall_status = HealthStatus.DEGRADED
        
        return {
            "status": overall_status.value,
            "checks": results,
        }

    async def check(self, name: str) -> Optional[Dict[str, Any]]:
        """Run specific health check."""
        for check in self.checks:
            if check.name == name:
                return await check.run()
        return None


# Built-in health check functions

async def check_database(db_session_factory) -> bool:
    """Check database connection."""
    try:
        async for session in db_session_factory():
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


async def check_redis(cache) -> bool:
    """Check Redis connection."""
    try:
        return await cache.ping()
    except Exception:
        return False


async def check_kafka(event_bus) -> bool:
    """Check Kafka connection."""
    try:
        return event_bus._connected
    except Exception:
        return False


async def check_health(
    checks: Optional[List[HealthCheck]] = None,
    checker: Optional[HealthChecker] = None,
) -> Dict[str, Any]:
    """Check health status."""
    if checker:
        return await checker.check_all()
    
    if checks:
        temp_checker = HealthChecker()
        for check in checks:
            temp_checker.checks.append(check)
        return await temp_checker.check_all()
    
    # Default: return basic health
    return {
        "status": HealthStatus.HEALTHY.value,
        "message": "Service is running",
    }

