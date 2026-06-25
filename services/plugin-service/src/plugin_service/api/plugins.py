from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from plugin_service.core.database import SessionLocal, engine
from plugin_service.models.plugin import Plugin

router = APIRouter()


@router.get("/api/v2/plugins")
async def list_plugins() -> dict[str, Any]:
    with SessionLocal() as db:
        items = db.execute(select(Plugin)).scalars().all()
        payload = [{"id": p.id, "name": p.name, "version": p.version} for p in items]
    return {"items": payload, "total": len(payload)}


# Legacy alias — respond to /api/v2/modules with same logic
@router.get("/api/v2/modules")
async def list_modules() -> dict[str, Any]:
    return await list_plugins()


@router.post("/api/v2/plugins", status_code=201)
async def create_plugin(payload: dict[str, Any]) -> dict[str, Any]:
    if "name" not in payload or not payload["name"]:
        raise HTTPException(status_code=400, detail="name is required")
    plugin_id = str(uuid4())
    data = Plugin(id=plugin_id, name=payload["name"], version=payload.get("version", "0.1.0"))
    with SessionLocal() as db:
        db.add(data)
        db.commit()
    return {"id": data.id, "name": data.name, "version": data.version}


@router.get("/api/v2/plugins/{plugin_id}")
async def get_plugin(plugin_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="plugin not found")
    return {"id": plugin.id, "name": plugin.name, "version": plugin.version}


@router.patch("/api/v2/plugins/{plugin_id}")
async def update_plugin(plugin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        if "name" in payload and payload["name"]:
            plugin.name = payload["name"]
        if "version" in payload and payload["version"]:
            plugin.version = payload["version"]
        db.commit()
        db.refresh(plugin)
    return {"id": plugin.id, "name": plugin.name, "version": plugin.version}


@router.delete("/api/v2/plugins/{plugin_id}", status_code=204)
async def delete_plugin(plugin_id: str) -> None:
    with SessionLocal() as db:
        plugin = db.get(Plugin, plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail="plugin not found")
        db.delete(plugin)
        db.commit()


@router.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Plugin))
    return {"status": "ready", "service": "plugin-service", "database": "ok"}
