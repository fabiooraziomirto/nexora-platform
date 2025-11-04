"""
Error handling utilities.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class Stack4ThingsError(Exception):
    """Base exception for Stack4Things errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }

    def to_http_exception(self, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return HTTPException(
            status_code=status_code,
            detail=self.to_dict(),
        )


class ValidationError(Stack4ThingsError):
    """Validation error."""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details)
        self.field = field
        if field:
            self.details["field"] = field

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return super().to_http_exception(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class NotFoundError(Stack4ThingsError):
    """Resource not found error."""

    def __init__(self, resource_type: str, resource_id: Optional[str] = None):
        message = f"{resource_type} not found"
        if resource_id:
            message += f": {resource_id}"
        
        details = {
            "resource_type": resource_type,
            "resource_id": resource_id,
        }
        
        super().__init__(message, code="NOT_FOUND", details=details)
        self.resource_type = resource_type
        self.resource_id = resource_id

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return super().to_http_exception(status_code=status.HTTP_404_NOT_FOUND)


class ConflictError(Stack4ThingsError):
    """Resource conflict error."""

    def __init__(self, message: str, resource_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CONFLICT", details=details or {})
        self.resource_type = resource_type
        if resource_type:
            self.details["resource_type"] = resource_type

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return super().to_http_exception(status_code=status.HTTP_409_CONFLICT)


class UnauthorizedError(Stack4ThingsError):
    """Unauthorized error."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, code="UNAUTHORIZED")

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return super().to_http_exception(status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(Stack4ThingsError):
    """Forbidden error."""

    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, code="FORBIDDEN")

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return super().to_http_exception(status_code=status.HTTP_403_FORBIDDEN)


class DatabaseError(Stack4ThingsError):
    """Database error."""

    def __init__(self, message: str, operation: Optional[str] = None):
        details = {"operation": operation} if operation else {}
        super().__init__(message, code="DATABASE_ERROR", details=details)
        self.operation = operation


class ExternalServiceError(Stack4ThingsError):
    """External service error."""

    def __init__(self, service_name: str, message: str):
        details = {"service_name": service_name}
        super().__init__(message, code="EXTERNAL_SERVICE_ERROR", details=details)
        self.service_name = service_name

