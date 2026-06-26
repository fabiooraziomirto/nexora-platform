import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, String, Integer, Text, DateTime

from execution_service.core.database import Base
import hmac

from execution_service.core.config import (
    VALID_STATUSES,
    ACTIVE_STATUSES,
    _ALLOWED_TRANSITIONS,
    _CALLBACK_ALLOWED_FIELDS,
    CALLBACK_REPLAY_REQUIRED,
    AGENT_CALLBACK_SECRET,
)

logger = logging.getLogger("execution-service")


class Execution(Base):
    __tablename__ = "executions"

    id = Column(String(36), primary_key=True, index=True)
    device_id = Column(String(64), nullable=True, index=True)
    command = Column(String(255), nullable=False, default="noop")
    status = Column(String(64), nullable=False, default="queued")
    correlation_id = Column(String(64), nullable=True)
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    exit_code = Column(Integer, nullable=True)
    result_stdout = Column(Text, nullable=True)
    result_stderr = Column(Text, nullable=True)
    tenant_id = Column(String(64), nullable=True, index=True)
    # owner_id: Keycloak sub of the user who created this execution.
    # Used for privacy enforcement: only the owner sees full payload (level 4).
    owner_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, nullable=True)
    dispatched_at = Column(DateTime, nullable=True)
    running_at = Column(DateTime, nullable=True)

    # FaaS fields
    # execution_type: "command" (default) | "function.install" | "function.invoke"
    execution_type = Column(String(30), nullable=True)
    plugin_id = Column(String(36), nullable=True, index=True)  # ref to plugin-service
    args = Column(Text, nullable=True)                          # JSON args for function.invoke
    function_result = Column(Text, nullable=True)               # JSON result from agent callback
    invocation_mode = Column(String(10), nullable=True)         # "async" (default) | "sync"


def make_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def execution_to_dict(e: Execution, *, include_payload: bool = True) -> dict[str, Any]:
    """Serialize an Execution to dict.

    include_payload=False applies privacy level 3 (command history without
    stdout/stderr content). Set to True only for the owner (level 4).
    """
    dispatch_latency_seconds: float | None = None
    if e.dispatched_at and e.running_at:
        dispatch_latency_seconds = round(
            (make_aware(e.running_at) - make_aware(e.dispatched_at)).total_seconds(), 6
        )
    return {
        "id": e.id,
        "device_id": e.device_id,
        "command": e.command,
        "status": e.status,
        "execution_type": e.execution_type or "command",
        "plugin_id": e.plugin_id,
        "args": json.loads(e.args) if e.args else None,
        "invocation_mode": e.invocation_mode or "async",
        "correlation_id": e.correlation_id,
        "idempotency_key": e.idempotency_key,
        "exit_code": e.exit_code if include_payload else None,
        "result_stdout": e.result_stdout if include_payload else None,
        "result_stderr": e.result_stderr if include_payload else None,
        "function_result": json.loads(e.function_result) if (e.function_result and include_payload) else None,
        "tenant_id": e.tenant_id,
        "owner_id": e.owner_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "dispatched_at": e.dispatched_at.isoformat() if e.dispatched_at else None,
        "running_at": e.running_at.isoformat() if e.running_at else None,
        "dispatch_latency_seconds": dispatch_latency_seconds,
    }


def transition_allowed(from_status: str, to_status: str) -> bool:
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, set())


def validate_callback_payload(payload: dict[str, Any]) -> str | None:
    unknown = set(payload.keys()) - _CALLBACK_ALLOWED_FIELDS
    if unknown:
        return f"unknown fields: {', '.join(sorted(unknown))}"
    status = payload.get("status")
    if status is not None and status not in VALID_STATUSES:
        return f"invalid status: {status}"
    return None


def check_and_store_callback_key(db, execution: Execution, key: str | None) -> str | None:
    if not AGENT_CALLBACK_SECRET:
        return None
    if not key:
        return "callback_key is required"
    expected = hmac.new(
        AGENT_CALLBACK_SECRET.encode(),
        execution.id.encode(),
        digestmod="sha256",
    ).hexdigest()
    if not hmac.compare_digest(key, expected):
        return "invalid callback_key"
    if CALLBACK_REPLAY_REQUIRED and getattr(execution, "callback_received", False):
        return "callback already received"
    return None


def audit_log(action: str, execution_id: str, detail: str = "") -> None:
    logger.info(
        json.dumps({
            "audit": True,
            "service": "execution-service",
            "action": action,
            "execution_id": execution_id,
            "detail": detail,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    )
