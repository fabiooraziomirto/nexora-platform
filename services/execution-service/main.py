import os
import sys

# Ensure src/ is on the path when running directly (docker, uvicorn main:app).
# When pytest runs with PYTHONPATH=src this is already set; the insert is a no-op
# if it's already present.
_SRC = os.path.join(os.path.dirname(__file__), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import asyncio
import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import aiokafka
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest
from sqlalchemy import func, select, and_

# ── Submodule imports ─────────────────────────────────────────────────────────
from execution_service.core.config import (
    DATABASE_URL,
    DB_CONNECT_TIMEOUT_SECONDS,
    AUTH_ENABLED,
    AUTH_DEV_TOKEN,
    AUTH_DEV_BYPASS_ENABLED,
    AUTH_OPERATOR_ROLE,
    ENVIRONMENT,
    KEYCLOAK_ISSUER,
    AUTH_WRITE_ROLE,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC_PREFIX,
    KAFKA_ENABLED,
    KAFKA_REQUIRED,
    KAFKA_RETRY_ATTEMPTS,
    KAFKA_RETRY_DELAY_SECONDS,
    AGENT_CALLBACK_SECRET,
    CALLBACK_REPLAY_TTL_SECONDS,
    CALLBACK_REPLAY_REQUIRED,
    MAX_EXECUTIONS_PER_DEVICE,
    EXECUTION_DISPATCHED_TIMEOUT_SECONDS,
    EXECUTION_RUNNING_TIMEOUT_SECONDS,
    EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    TERMINAL_STATUSES,
    VALID_STATUSES,
    ACTIVE_STATUSES,
    _ALLOWED_TRANSITIONS,
    _CALLBACK_ALLOWED_FIELDS,
    PLUGIN_SERVICE_URL,
    DEVICE_SERVICE_URL,
)
from execution_service.core.database import Base, engine, SessionLocal, ensure_execution_columns
from execution_service.core.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    ACTIVE_EXECUTIONS_GAUGE,
)
import execution_service.core.events as _events
from execution_service.models.execution import (
    Execution,
    execution_to_dict,
    make_aware,
    transition_allowed,
    validate_callback_payload,
    check_and_store_callback_key,
    audit_log,
)

# ── Aliases for backward compatibility with tests that import these names ─────
# Tests do: from main import app, SessionLocal, Execution, ACTIVE_STATUSES
# All these names are now present in this module's namespace from imports above.

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("execution-service")

app = FastAPI(title="Execution Service", version="0.1.0")


# ── Private helpers that stay here so monkeypatch.setattr("main.X") works ────
# Tests patch: main.MAX_EXECUTIONS_PER_DEVICE and main.EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS.
# Because those names were imported into this module's namespace above, patching
# main.X updates *this* module's global dict, which the route closures read.


def _count_active_for_device(db, device_id: str) -> int:
    return db.execute(
        select(func.count()).select_from(Execution).where(
            and_(Execution.device_id == device_id, Execution.status.in_(ACTIVE_STATUSES))
        )
    ).scalar() or 0


def _decode_jwt_payload(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        data = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
        return json.loads(data)
    except Exception:
        return None


# ── Timeout loop (defined here so `import main; main.EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS = 0`
#    is visible to this function's globals) ────────────────────────────────────
async def _timeout_loop() -> None:
    while True:
        await asyncio.sleep(EXECUTION_TIMEOUT_CHECK_INTERVAL_SECONDS)
        try:
            now = datetime.now(timezone.utc)
            with SessionLocal() as db:
                candidates = db.execute(
                    select(Execution).where(Execution.status.in_({"dispatched", "running"}))
                ).scalars().all()
                for ex in candidates:
                    elapsed = None
                    if ex.status == "dispatched" and ex.dispatched_at:
                        elapsed = (now - make_aware(ex.dispatched_at)).total_seconds()
                        threshold = EXECUTION_DISPATCHED_TIMEOUT_SECONDS
                    elif ex.status == "running" and ex.running_at:
                        elapsed = (now - make_aware(ex.running_at)).total_seconds()
                        threshold = EXECUTION_RUNNING_TIMEOUT_SECONDS
                    if elapsed is not None and elapsed > threshold:
                        ex.status = "timeout"
                        audit_log("timeout", ex.id, f"elapsed={elapsed:.1f}s threshold={threshold}s")
                db.commit()
        except Exception:
            logger.exception("Timeout check iteration failed")


# ── Alias for internal backward compat (_ensure_execution_columns still in tests?) ──
def _ensure_execution_columns() -> None:
    ensure_execution_columns()


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup() -> None:
    if AUTH_DEV_BYPASS_ENABLED:
        if ENVIRONMENT == "production":
            raise RuntimeError("AUTH_DEV_BYPASS_ENABLED=true is not allowed when ENVIRONMENT=production")
        logger.warning("AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION")
    Base.metadata.create_all(bind=engine)
    _ensure_execution_columns()
    asyncio.create_task(_timeout_loop())
    if not KAFKA_ENABLED:
        logger.info("Kafka publisher disabled by configuration")
        return
    _events.producer = aiokafka.AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    try:
        await _events.producer.start()
    except Exception:
        logger.exception("Failed to connect Kafka producer")
        _events.producer = None
        if KAFKA_REQUIRED:
            raise


@app.on_event("shutdown")
async def shutdown() -> None:
    if _events.producer:
        await _events.producer.stop()
        _events.producer = None


# ── Middleware ────────────────────────────────────────────────────────────────

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # When auth is disabled (tests / local dev), treat as operator so no filtering is applied.
    # Allow outer ASGI test wrappers to pre-inject a specific identity (skip overwrite if set).
    if not AUTH_ENABLED:
        if not getattr(request.state, "user_id", None):
            request.state.user_id = "dev-user"
            request.state.tenant_id = "dev"
            request.state.is_operator = True
        return await call_next(request)
    if request.url.path in {"/health", "/ready", "/metrics"}:
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "missing bearer token"})
    token = auth.split(" ", 1)[1]
    if AUTH_DEV_BYPASS_ENABLED and token == AUTH_DEV_TOKEN:
        request.state.user_id = "dev-user"
        request.state.tenant_id = "dev"
        request.state.is_operator = True
        return await call_next(request)
    payload = _decode_jwt_payload(token)
    if not payload:
        return JSONResponse(status_code=401, content={"detail": "invalid token"})
    exp = payload.get("exp")
    if exp and float(exp) < time.time():
        return JSONResponse(status_code=401, content={"detail": "token expired"})
    if KEYCLOAK_ISSUER and payload.get("iss") != KEYCLOAK_ISSUER:
        return JSONResponse(status_code=401, content={"detail": "invalid issuer"})
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        realm_access = payload.get("realm_access", {})
        roles = set(realm_access.get("roles", []))
        if AUTH_WRITE_ROLE and AUTH_WRITE_ROLE not in roles:
            return JSONResponse(status_code=403, content={"detail": "forbidden"})
    # Propagate caller identity to request.state for use in route handlers
    roles_list: list[str] = payload.get("realm_access", {}).get("roles", [])
    groups: list[str] = payload.get("groups", [])
    request.state.user_id = payload.get("sub", "")
    request.state.tenant_id = groups[0].lstrip("/") if groups else "global"
    request.state.is_operator = AUTH_OPERATOR_ROLE in roles_list
    return await call_next(request)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or uuid4().hex
    correlation_id = request.headers.get("x-correlation-id", trace_id)
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["x-trace-id"] = trace_id
    response.headers["x-correlation-id"] = correlation_id
    HTTP_REQUESTS_TOTAL.labels(
        "execution-service", request.method, request.url.path, str(response.status_code)
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        "execution-service", request.method, request.url.path
    ).observe(elapsed)
    logger.info(
        json.dumps({
            "service": "execution-service",
            "trace_id": trace_id,
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_s": round(elapsed, 6),
        })
    )
    return response


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "execution-service"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    with engine.connect() as conn:
        conn.execute(select(func.count()).select_from(Execution))
    return {"status": "ready", "service": "execution-service", "database": "ok"}


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=generate_latest(), media_type="text/plain")


@app.get("/api/v2/executions")
async def list_executions(request: Request) -> dict[str, Any]:
    is_operator = getattr(request.state, "is_operator", True)
    caller_owner_id = getattr(request.state, "user_id", None)
    with SessionLocal() as db:
        q = select(Execution)
        if not is_operator and caller_owner_id:
            # Non-operators see only their own executions (command history, level 3)
            q = q.where(Execution.owner_id == caller_owner_id)
        items = db.execute(q).scalars().all()
        # Payload masking: owner sees full content (level 4); others see metadata only (level 3)
        result = [
            execution_to_dict(e, include_payload=(is_operator or e.owner_id == caller_owner_id))
            for e in items
        ]
    return {"items": result, "total": len(result)}


@app.post("/api/v2/executions", status_code=201)
async def create_execution(
    payload: dict[str, Any],
    request: Request,
    x_tenant_id: str | None = Header(None),
) -> dict[str, Any]:
    idempotency_key = payload.get("idempotency_key")
    with SessionLocal() as db:
        if idempotency_key:
            existing = db.execute(
                select(Execution).where(Execution.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if existing:
                return execution_to_dict(existing)

        device_id = payload.get("device_id")
        if device_id:
            active_count = _count_active_for_device(db, device_id)
            if active_count >= MAX_EXECUTIONS_PER_DEVICE:
                raise HTTPException(
                    status_code=429,
                    detail=f"device {device_id} has {active_count} active executions (limit {MAX_EXECUTIONS_PER_DEVICE})",
                )

        execution_id = str(uuid4())
        now = datetime.now(timezone.utc)
        caller_owner_id = getattr(request.state, "user_id", None)
        caller_tenant_id = getattr(request.state, "tenant_id", x_tenant_id)
        execution_type = payload.get("type", payload.get("execution_type", "command"))
        plugin_id = payload.get("plugin_id")
        if execution_type in {"function.install", "function.invoke"} and not plugin_id:
            raise HTTPException(status_code=400, detail="plugin_id is required for function executions")
        args_raw = payload.get("args")
        execution = Execution(
            id=execution_id,
            device_id=device_id,
            command=payload.get("command", "noop"),
            status="queued",
            correlation_id=str(uuid4()),
            idempotency_key=idempotency_key,
            tenant_id=caller_tenant_id,
            owner_id=caller_owner_id,
            created_at=now,
            execution_type=execution_type,
            plugin_id=plugin_id,
            args=json.dumps(args_raw) if args_raw is not None else None,
            invocation_mode=payload.get("mode", "async"),
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        response = execution_to_dict(execution)

    audit_log("created", execution.id)
    await _events.publish_event("created", execution.id, response)
    return response


@app.get("/api/v2/executions/{execution_id}")
async def get_execution(execution_id: str, request: Request) -> dict[str, Any]:
    is_operator = getattr(request.state, "is_operator", True)
    caller_owner_id = getattr(request.state, "user_id", None)
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="execution not found")
    # Tenant isolation: non-operators outside the owner's tenant get 404
    caller_tenant = getattr(request.state, "tenant_id", None)
    if not is_operator and execution.owner_id and execution.owner_id != caller_owner_id:
        if execution.tenant_id != caller_tenant:
            raise HTTPException(status_code=404, detail="execution not found")
    is_owner = is_operator or (execution.owner_id == caller_owner_id)
    return execution_to_dict(execution, include_payload=is_owner)


@app.delete("/api/v2/executions/{execution_id}", status_code=204)
async def delete_execution(execution_id: str) -> None:
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="execution not found")
        deleted_payload = execution_to_dict(execution)
        db.delete(execution)
        db.commit()
    audit_log("deleted", execution_id)
    await _events.publish_event("deleted", execution_id, deleted_payload)


@app.post("/api/v2/executions/{execution_id}/dispatch")
async def dispatch_execution(execution_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="execution not found")
        if not transition_allowed(execution.status, "dispatched"):
            raise HTTPException(
                status_code=409,
                detail=f"cannot transition from {execution.status} to dispatched",
            )
        execution.status = "dispatched"
        execution.dispatched_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(execution)
        response = execution_to_dict(execution)
    envelope = {
        "execution_id": execution.id,
        "device_id": execution.device_id,
        "command": execution.command,
        "execution_type": execution.execution_type or "command",
        "correlation_id": execution.correlation_id,
        "kafka_dispatched_at": time.time(),
    }

    # FaaS: fetch plugin metadata and device capabilities, embed in dispatch envelope
    exec_type = execution.execution_type or "command"
    if exec_type in {"function.install", "function.invoke"}:
        import httpx as _httpx
        try:
            plugin_resp = _httpx.get(
                f"{PLUGIN_SERVICE_URL}/api/v2/plugins/{execution.plugin_id}",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if plugin_resp.status_code != 200:
                raise HTTPException(status_code=502, detail="plugin not found in registry")
            plugin_data = plugin_resp.json()
            if plugin_data.get("status") != "active":
                raise HTTPException(status_code=409, detail=f"plugin status is '{plugin_data.get('status')}', must be active")
            envelope["plugin"] = {
                "id": execution.plugin_id,
                "name": plugin_data.get("name"),
                "version": plugin_data.get("version"),
                "runtime_type": plugin_data.get("runtime_type"),
                "artifact_uri": plugin_data.get("artifact_uri"),
                "artifact_checksum": plugin_data.get("artifact_checksum"),
                "entrypoint": plugin_data.get("entrypoint"),
                "timeout_seconds": plugin_data.get("timeout_seconds", 30),
                "memory_limit_mb": plugin_data.get("memory_limit_mb", 64),
                "permissions": plugin_data.get("permissions", []),
                "required_capabilities": plugin_data.get("required_capabilities", []),
            }
        except _httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"plugin-service unavailable: {exc}") from exc

        if execution.device_id:
            try:
                device_resp = _httpx.get(
                    f"{DEVICE_SERVICE_URL}/api/v2/devices/{execution.device_id}",
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
                if device_resp.status_code == 200:
                    caps = device_resp.json().get("capabilities") or {}
                    if "wasm_wasi" in (envelope.get("plugin", {}).get("required_capabilities") or []):
                        if not caps.get("wasm_wasi"):
                            raise HTTPException(
                                status_code=400,
                                detail=f"device {execution.device_id} does not declare wasm_wasi capability",
                            )
                    envelope["device_capabilities"] = caps
            except _httpx.RequestError:
                logger.warning("device-service unreachable — skipping capability check for %s", execution.device_id)

        if execution.args:
            envelope["args"] = json.loads(execution.args)

    audit_log("dispatched", execution_id)
    await _events.publish_event("dispatched", execution.id, envelope)
    return response


@app.post("/api/v2/executions/{execution_id}/callback")
async def callback_execution(execution_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    error = validate_callback_payload(payload)
    if error:
        raise HTTPException(status_code=422, detail=error)

    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=422, detail="status is required")

    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="execution not found")

        key_err = check_and_store_callback_key(db, execution, payload.get("callback_key"))
        if key_err:
            raise HTTPException(status_code=422, detail=key_err)

        if not transition_allowed(execution.status, new_status):
            raise HTTPException(
                status_code=409,
                detail=f"cannot transition from {execution.status} to {new_status}",
            )

        execution.status = new_status
        if new_status == "running":
            execution.running_at = datetime.now(timezone.utc)
        if "exit_code" in payload:
            execution.exit_code = payload["exit_code"]
        if "stdout" in payload:
            execution.result_stdout = payload["stdout"]
        if "stderr" in payload:
            execution.result_stderr = payload["stderr"]
        if "function_result" in payload and payload["function_result"] is not None:
            execution.function_result = json.dumps(payload["function_result"])

        db.commit()
        db.refresh(execution)
        response = execution_to_dict(execution)

    audit_log("callback", execution_id, f"new_status={new_status}")
    await _events.publish_event("callback", execution.id, response)
    return response


# ── FaaS HTTP Trigger Shortcuts ───────────────────────────────────────────────
# These create + dispatch a function execution in one call.

async def _create_and_dispatch_function(
    plugin_id: str,
    device_id: str | None,
    args: dict | None,
    mode: str,
    request: Request,
) -> dict[str, Any]:
    """Helper: create a function.invoke execution and immediately dispatch it."""
    fake_payload: dict[str, Any] = {
        "type": "function.invoke",
        "plugin_id": plugin_id,
        "device_id": device_id,
        "args": args or {},
        "mode": mode,
        "command": f"function.invoke:{plugin_id}",
    }
    # Reuse create_execution logic via internal call
    create_req = request
    created = await create_execution(fake_payload, create_req, x_tenant_id=None)
    exec_id = created["id"]
    # Dispatch immediately
    dispatched = await dispatch_execution(exec_id)
    return dispatched


@app.post("/api/v2/functions/{plugin_id}/invoke", status_code=202)
async def invoke_function(
    plugin_id: str,
    payload: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    """Invoke a function on any available device (device_id in body or omit for fleet-wide)."""
    return await _create_and_dispatch_function(
        plugin_id=plugin_id,
        device_id=payload.get("device_id"),
        args=payload.get("args"),
        mode=payload.get("mode", "async"),
        request=request,
    )


@app.post("/api/v2/devices/{device_id}/functions/{plugin_id}/invoke", status_code=202)
async def invoke_function_on_device(
    device_id: str,
    plugin_id: str,
    payload: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    """Invoke a function on a specific device."""
    return await _create_and_dispatch_function(
        plugin_id=plugin_id,
        device_id=device_id,
        args=payload.get("args"),
        mode=payload.get("mode", "async"),
        request=request,
    )


@app.post("/api/v2/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        execution = db.get(Execution, execution_id)
        if not execution:
            raise HTTPException(status_code=404, detail="execution not found")
        if not transition_allowed(execution.status, "cancelled"):
            raise HTTPException(
                status_code=409,
                detail=f"cannot transition from {execution.status} to cancelled",
            )
        execution.status = "cancelled"
        db.commit()
        db.refresh(execution)
        response = execution_to_dict(execution)
    audit_log("cancelled", execution_id)
    await _events.publish_event("cancelled", execution.id, response)
    return response
