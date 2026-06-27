from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_audit_event(path: str, action: str, actor: str, details: dict[str, Any]) -> None:
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "actor": actor,
        "details": details,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


AUDIT_FIELDS = {
    "timestamp",
    "service",
    "actor_user_id",
    "actor_tenant_id",
    "actor_roles",
    "action",
    "resource_type",
    "resource_id",
    "tenant_id",
    "correlation_id",
    "outcome",
    "reason",
}


def default_audit_path() -> str:
    return os.getenv("AUDIT_LOG_PATH", "/tmp/nexora-audit/events.jsonl")


def emit_audit_event(
    *,
    service: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    tenant_id: str | None,
    actor_user_id: str | None = None,
    actor_tenant_id: str | None = None,
    actor_roles: list[str] | None = None,
    correlation_id: str | None = None,
    outcome: str = "success",
    reason: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "actor_user_id": actor_user_id or "system",
        "actor_tenant_id": actor_tenant_id or tenant_id or "system",
        "actor_roles": actor_roles or [],
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "tenant_id": tenant_id,
        "correlation_id": correlation_id,
        "outcome": outcome,
        "reason": reason,
    }
    target = Path(path or default_audit_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def read_audit_events(
    *,
    path: str | None = None,
    tenant_id: str | None = None,
    actor_user_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> list[dict[str, Any]]:
    target = Path(path or default_audit_path())
    if not target.exists():
        return []
    events: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if tenant_id and event.get("tenant_id") != tenant_id:
                continue
            if actor_user_id and event.get("actor_user_id") != actor_user_id:
                continue
            if action and event.get("action") != action:
                continue
            if resource_type and event.get("resource_type") != resource_type:
                continue
            if resource_id and event.get("resource_id") != resource_id:
                continue
            ts = str(event.get("timestamp") or "")
            if from_ts and ts < from_ts:
                continue
            if to_ts and ts > to_ts:
                continue
            events.append(event)
    return events
