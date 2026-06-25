import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from plugin_service.core.database import SessionLocal, engine
from plugin_service.models.plugin import Plugin

router = APIRouter()

_VALID_STATUSES = {"draft", "active", "deprecated", "archived"}
_STATUS_TRANSITIONS = {
    "draft": {"active"},
    "active": {"deprecated"},
    "deprecated": {"archived"},
}


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
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/api/v2/plugins")
async def list_plugins() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(select(Plugin)).scalars().all()
    return {"items": [_plugin_to_dict(p) for p in items], "total": len(items)}


# Semantic alias: list only FaaS functions
@router.get("/api/v2/functions")
async def list_functions() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(
            select(Plugin).where(Plugin.module_type == "function")
        ).scalars().all()
    return {"items": [_plugin_to_dict(p) for p in items], "total": len(items)}


# Legacy alias
@router.get("/api/v2/modules")
async def list_modules() -> dict[str, Any]:
    return await list_plugins()


@router.post("/api/v2/plugins", status_code=201)
async def create_plugin(payload: dict[str, Any]) -> dict[str, Any]:
    if "name" not in payload or not payload["name"]:
        raise HTTPException(status_code=400, detail="name is required")
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
        created_at=now,
        updated_at=now,
    )
    with SessionLocal() as db:
        db.add(plugin)
        db.commit()
        db.refresh(plugin)
    return _plugin_to_dict(plugin)


@router.get("/api/v2/plugins/{plugin_id}")
async def get_plugin(plugin_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="plugin not found")
    return _plugin_to_dict(plugin)


@router.patch("/api/v2/plugins/{plugin_id}")
async def update_plugin(plugin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
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
        plugin.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plugin)
    return _plugin_to_dict(plugin)


@router.delete("/api/v2/plugins/{plugin_id}", status_code=204)
async def delete_plugin(plugin_id: str) -> None:
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        db.delete(plugin)
        db.commit()


@router.patch("/api/v2/plugins/{plugin_id}/activate")
async def activate_plugin(plugin_id: str) -> dict[str, Any]:
    """Transition a draft plugin/function to active. Requires artifact_uri + entrypoint for functions."""
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        current_status = plugin.status or "draft"
        if current_status != "draft":
            raise HTTPException(status_code=409, detail=f"cannot activate from status '{current_status}'")
        if plugin.module_type == "function":
            if not plugin.artifact_uri:
                raise HTTPException(status_code=400, detail="artifact_uri required to activate a function")
            if not plugin.entrypoint:
                raise HTTPException(status_code=400, detail="entrypoint required to activate a function")
        plugin.status = "active"
        plugin.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plugin)
    return _plugin_to_dict(plugin)


@router.patch("/api/v2/plugins/{plugin_id}/deprecate")
async def deprecate_plugin(plugin_id: str) -> dict[str, Any]:
    """Transition an active plugin/function to deprecated."""
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        if (plugin.status or "draft") != "active":
            raise HTTPException(status_code=409, detail="only active plugins can be deprecated")
        plugin.status = "deprecated"
        plugin.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(plugin)
    return _plugin_to_dict(plugin)


@router.get("/api/v2/plugins/{plugin_id}/schema")
async def get_plugin_schema(plugin_id: str) -> dict[str, Any]:
    """Return the input JSON Schema for a function (used for client-side validation)."""
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="plugin not found")
    schema = json.loads(plugin.input_schema) if plugin.input_schema else {}
    return {"plugin_id": plugin_id, "input_schema": schema}


@router.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Plugin))
    return {"status": "ready", "service": "plugin-service", "database": "ok"}
