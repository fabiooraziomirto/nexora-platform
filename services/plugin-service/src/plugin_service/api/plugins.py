import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select
from common.audit import emit_audit_event
from common.auth.context import auth_settings_from_env, current_user_from_request

from plugin_service.core.config import (
    PLUGIN_SECURITY_MAX_CRITICAL,
    PLUGIN_SECURITY_MAX_HIGH,
    PLUGIN_SECURITY_SCAN_REQUIRED,
)
from plugin_service.core.database import SessionLocal, engine
from plugin_service.models.plugin import Plugin

router = APIRouter()
AUTH_SETTINGS = auth_settings_from_env()

_VALID_STATUSES = {"draft", "active", "deprecated", "archived"}
_STATUS_TRANSITIONS = {
    "draft": {"active"},
    "active": {"deprecated"},
    "deprecated": {"archived"},
}
_VALID_SCAN_STATUSES = {"pending", "passed", "failed"}


def _plugin_to_dict(p: Plugin) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "version": p.version,
        "module_type": p.module_type or "plugin",
        "status": p.status or "draft",
        "artifact_uri": p.artifact_uri,
        "artifact_checksum": p.artifact_checksum,
        "runtime_type": p.runtime_type,
        "entrypoint": p.entrypoint,
        "timeout_seconds": p.timeout_seconds,
        "memory_limit_mb": p.memory_limit_mb,
        "permissions": json.loads(p.permissions) if p.permissions else [],
        "required_capabilities": json.loads(p.required_capabilities) if p.required_capabilities else [],
        "input_schema": json.loads(p.input_schema) if p.input_schema else None,
        "env_schema": json.loads(p.env_schema) if p.env_schema else None,
        "sbom_uri": p.sbom_uri,
        "security_scan_tool": p.security_scan_tool,
        "security_scan_status": p.security_scan_status or "pending",
        "security_scan_summary": json.loads(p.security_scan_summary) if p.security_scan_summary else None,
        "scanned_at": p.scanned_at.isoformat() if p.scanned_at else None,
        "owner_id": p.owner_id,
        "tenant_id": p.tenant_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _normalize_severity_counts(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("vulnerability_counts") or {}
    counts = {
        "critical": int(raw.get("critical", 0) or 0),
        "high": int(raw.get("high", 0) or 0),
        "medium": int(raw.get("medium", 0) or 0),
        "low": int(raw.get("low", 0) or 0),
        "unknown": int(raw.get("unknown", 0) or 0),
    }
    if any(v < 0 for v in counts.values()):
        raise HTTPException(status_code=400, detail="vulnerability counts must be >= 0")
    return counts


def _scan_verdict(counts: dict[str, int]) -> str:
    if counts["critical"] > PLUGIN_SECURITY_MAX_CRITICAL:
        return "failed"
    if counts["high"] > PLUGIN_SECURITY_MAX_HIGH:
        return "failed"
    return "passed"


@router.get("/api/v2/plugins")
async def list_plugins(request: Request, tenant_id: str | None = Query(default=None)) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        q = select(Plugin)
        if user.is_platform_admin(AUTH_SETTINGS):
            if tenant_id:
                q = q.where(Plugin.tenant_id == tenant_id)
        else:
            q = q.where(Plugin.tenant_id == user.tenant_id)
        items = db.execute(q).scalars().all()
    return {"items": [_plugin_to_dict(p) for p in items], "total": len(items)}


# Semantic alias: list only FaaS functions
@router.get("/api/v2/functions")
async def list_functions(request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        q = select(Plugin).where(Plugin.module_type == "function")
        if not user.is_platform_admin(AUTH_SETTINGS):
            q = q.where(Plugin.tenant_id == user.tenant_id)
        items = db.execute(q).scalars().all()
    return {"items": [_plugin_to_dict(p) for p in items], "total": len(items)}


# Legacy alias
@router.get("/api/v2/modules")
async def list_modules(request: Request) -> dict[str, Any]:
    return await list_plugins(request)


@router.post("/api/v2/plugins", status_code=201)
async def create_plugin(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    if "name" not in payload or not payload["name"]:
        raise HTTPException(status_code=400, detail="name is required")
    user = current_user_from_request(request)
    now = datetime.now(timezone.utc)
    plugin = Plugin(
        id=str(uuid4()),
        name=payload["name"],
        version=payload.get("version", "0.1.0"),
        module_type=payload.get("module_type", "plugin"),
        artifact_uri=payload.get("artifact_uri"),
        artifact_checksum=payload.get("artifact_checksum"),
        runtime_type=payload.get("runtime_type"),
        entrypoint=payload.get("entrypoint"),
        timeout_seconds=payload.get("timeout_seconds", 30),
        memory_limit_mb=payload.get("memory_limit_mb", 64),
        permissions=json.dumps(payload.get("permissions") or []),
        required_capabilities=json.dumps(payload.get("required_capabilities") or []),
        input_schema=json.dumps(payload["input_schema"]) if payload.get("input_schema") else None,
        env_schema=json.dumps(payload["env_schema"]) if payload.get("env_schema") else None,
        status="draft",
        owner_id=user.user_id,
        tenant_id=user.tenant_id,
        created_at=now,
        updated_at=now,
    )
    with SessionLocal() as db:
        db.add(plugin)
        db.commit()
        db.refresh(plugin)
    emit_audit_event(
        service="plugin-service",
        action="plugin.created",
        resource_type="plugin",
        resource_id=plugin.id,
        tenant_id=plugin.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    return _plugin_to_dict(plugin)


@router.get("/api/v2/plugins/{plugin_id}")
async def get_plugin(plugin_id: str, request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="plugin not found")
    if plugin.tenant_id and plugin.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
        raise HTTPException(status_code=404, detail="plugin not found")
    return _plugin_to_dict(plugin)


@router.patch("/api/v2/plugins/{plugin_id}")
async def update_plugin(plugin_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        if plugin.tenant_id and plugin.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
            raise HTTPException(status_code=404, detail="plugin not found")
        if plugin.status not in {"draft"}:
            raise HTTPException(status_code=409, detail="only draft plugins can be updated")
        for field in ("name", "version", "artifact_uri", "artifact_checksum",
                      "runtime_type", "entrypoint", "timeout_seconds", "memory_limit_mb"):
            if field in payload and payload[field] is not None:
                setattr(plugin, field, payload[field])
        for json_field in ("permissions", "required_capabilities", "input_schema", "env_schema"):
            if json_field in payload:
                setattr(plugin, json_field, json.dumps(payload[json_field]))
        if "sbom_uri" in payload:
            plugin.sbom_uri = payload.get("sbom_uri")
        plugin.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plugin)
    emit_audit_event(
        service="plugin-service",
        action="plugin.updated",
        resource_type="plugin",
        resource_id=plugin.id,
        tenant_id=plugin.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    return _plugin_to_dict(plugin)


@router.delete("/api/v2/plugins/{plugin_id}", status_code=204)
async def delete_plugin(plugin_id: str, request: Request) -> None:
    user = current_user_from_request(request)
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        if plugin.tenant_id and plugin.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
            raise HTTPException(status_code=404, detail="plugin not found")
        tenant_id = plugin.tenant_id
        db.delete(plugin)
        db.commit()
    emit_audit_event(
        service="plugin-service",
        action="plugin.deleted",
        resource_type="plugin",
        resource_id=plugin_id,
        tenant_id=tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )


@router.patch("/api/v2/plugins/{plugin_id}/activate")
async def activate_plugin(plugin_id: str, request: Request) -> dict[str, Any]:
    """Transition a draft plugin/function to active. Requires artifact_uri + entrypoint for functions."""
    user = current_user_from_request(request)
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        if plugin.tenant_id and plugin.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
            raise HTTPException(status_code=404, detail="plugin not found")
        current_status = plugin.status or "draft"
        if current_status != "draft":
            raise HTTPException(status_code=409, detail=f"cannot activate from status '{current_status}'")
        if plugin.module_type == "function":
            if not plugin.artifact_uri:
                raise HTTPException(status_code=400, detail="artifact_uri required to activate a function")
            if not plugin.entrypoint:
                raise HTTPException(status_code=400, detail="entrypoint required to activate a function")
            if PLUGIN_SECURITY_SCAN_REQUIRED:
                if not plugin.sbom_uri:
                    raise HTTPException(status_code=400, detail="sbom_uri required before activating a function")
                if (plugin.security_scan_status or "pending") != "passed":
                    raise HTTPException(status_code=409, detail="security scan must pass before activating a function")
        plugin.status = "active"
        plugin.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plugin)
    emit_audit_event(
        service="plugin-service",
        action="plugin.activated",
        resource_type="plugin",
        resource_id=plugin.id,
        tenant_id=plugin.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    return _plugin_to_dict(plugin)


@router.patch("/api/v2/plugins/{plugin_id}/deprecate")
async def deprecate_plugin(plugin_id: str, request: Request) -> dict[str, Any]:
    """Transition an active plugin/function to deprecated."""
    user = current_user_from_request(request)
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        if plugin.tenant_id and plugin.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
            raise HTTPException(status_code=404, detail="plugin not found")
        if (plugin.status or "draft") != "active":
            raise HTTPException(status_code=409, detail="only active plugins can be deprecated")
        plugin.status = "deprecated"
        plugin.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plugin)
    emit_audit_event(
        service="plugin-service",
        action="plugin.deprecated",
        resource_type="plugin",
        resource_id=plugin.id,
        tenant_id=plugin.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    return _plugin_to_dict(plugin)


@router.get("/api/v2/plugins/{plugin_id}/schema")
async def get_plugin_schema(plugin_id: str, request: Request) -> dict[str, Any]:
    """Return the input JSON Schema for a function (used for client-side validation)."""
    user = current_user_from_request(request)
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="plugin not found")
    if plugin.tenant_id and plugin.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
        raise HTTPException(status_code=404, detail="plugin not found")
    schema = json.loads(plugin.input_schema) if plugin.input_schema else {}
    return {"plugin_id": plugin_id, "input_schema": schema}


@router.post("/api/v2/plugins/{plugin_id}/security/scan")
async def record_plugin_security_scan(plugin_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Record SBOM + vulnerability scan result and compute deployment verdict."""
    user = current_user_from_request(request)
    scan_tool = str(payload.get("scan_tool") or "unknown").strip()
    requested_status = payload.get("status")
    counts = _normalize_severity_counts(payload)
    status = _scan_verdict(counts) if not requested_status else str(requested_status).strip().lower()
    if status not in _VALID_SCAN_STATUSES:
        raise HTTPException(status_code=400, detail="status must be pending|passed|failed")

    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        if plugin.tenant_id and plugin.tenant_id != user.tenant_id and not user.is_platform_admin(AUTH_SETTINGS):
            raise HTTPException(status_code=404, detail="plugin not found")

        if payload.get("sbom_uri"):
            plugin.sbom_uri = str(payload.get("sbom_uri"))
        plugin.security_scan_tool = scan_tool
        plugin.security_scan_status = status
        plugin.security_scan_summary = json.dumps({
            "vulnerability_counts": counts,
            "max_allowed": {
                "critical": PLUGIN_SECURITY_MAX_CRITICAL,
                "high": PLUGIN_SECURITY_MAX_HIGH,
            },
            "verdict": status,
        })
        plugin.scanned_at = datetime.now(timezone.utc)
        plugin.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plugin)

    emit_audit_event(
        service="plugin-service",
        action="plugin.security_scanned",
        resource_type="plugin",
        resource_id=plugin.id,
        tenant_id=plugin.tenant_id,
        actor_user_id=user.user_id,
        actor_tenant_id=user.tenant_id,
        actor_roles=user.roles,
        correlation_id=request.headers.get("x-correlation-id"),
    )
    return _plugin_to_dict(plugin)


@router.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Plugin))
    return {"status": "ready", "service": "plugin-service", "database": "ok"}
