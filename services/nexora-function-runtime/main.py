"""
nexora-function-runtime — Edge WASM/WASI function execution daemon.

Runs on the edge device alongside the LightningRod agent. Provides local
APIs (not exposed to the control plane) that the agent calls to install,
invoke, and manage WASM/WASI functions.

Dispatch flow:
  1. Agent receives function.install dispatch from lightningrod-gateway
  2. Agent POSTs to /runtime/functions/install (downloads + verifies artifact)
  3. Agent receives function.invoke dispatch
  4. Agent POSTs to /runtime/functions/{id}/invoke (executes in WASM sandbox)
  5. Agent relays function_result back to execution-service via callback

Port: RUNTIME_PORT (default 9000) — loopback only, not exposed externally.
"""
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("function-runtime")

# ── Config ────────────────────────────────────────────────────────────────────

INSTALL_DIR = Path(os.getenv("FUNCTION_INSTALL_DIR", "/var/nexora/functions"))
RUNTIME_PORT = int(os.getenv("RUNTIME_PORT", "9000"))
DOWNLOAD_TIMEOUT_SECONDS = float(os.getenv("DOWNLOAD_TIMEOUT_SECONDS", "30"))
MAX_MEMORY_MB_DEFAULT = int(os.getenv("MAX_MEMORY_MB_DEFAULT", "64"))

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Nexora Function Runtime", version="0.1.0")

# In-memory registry of installed functions.
# Persisted to INSTALL_DIR/<function_id>.meta.json on install.
_installed: dict[str, dict[str, Any]] = {}


@app.on_event("startup")
def startup() -> None:
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    _reload_installed()
    logger.info(json.dumps({
        "service": "function-runtime",
        "event": "startup",
        "install_dir": str(INSTALL_DIR),
        "loaded_functions": len(_installed),
    }))


def _reload_installed() -> None:
    """Load persisted function metadata from disk on startup."""
    for meta_file in INSTALL_DIR.glob("*.meta.json"):
        try:
            meta = json.loads(meta_file.read_text())
            _installed[meta["id"]] = meta
        except Exception as exc:
            logger.warning("Failed to load function meta %s: %s", meta_file, exc)


def _wasm_path(function_id: str) -> Path:
    return INSTALL_DIR / f"{function_id}.wasm"


def _meta_path(function_id: str) -> Path:
    return INSTALL_DIR / f"{function_id}.meta.json"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "function-runtime",
        "installed_count": len(_installed),
        "install_dir": str(INSTALL_DIR),
    }


@app.get("/runtime/functions")
async def list_functions() -> dict[str, Any]:
    return {"items": list(_installed.values()), "total": len(_installed)}


@app.get("/runtime/functions/{function_id}")
async def get_function(function_id: str) -> dict[str, Any]:
    fn = _installed.get(function_id)
    if not fn:
        raise HTTPException(status_code=404, detail="function not installed")
    return fn


@app.get("/runtime/functions/{function_id}/status")
async def get_function_status(function_id: str) -> dict[str, Any]:
    fn = _installed.get(function_id)
    if not fn:
        raise HTTPException(status_code=404, detail="function not installed")
    wasm_ok = _wasm_path(function_id).exists()
    return {
        "function_id": function_id,
        "status": fn.get("status", "installed"),
        "wasm_file_present": wasm_ok,
        "last_invoked_at": fn.get("last_invoked_at"),
        "last_error": fn.get("last_error"),
        "invocation_count": fn.get("invocation_count", 0),
    }


@app.post("/runtime/functions/install", status_code=201)
async def install_function(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Download a WASM artifact, verify its SHA256 checksum, and persist it.

    Expected payload:
      {
        "id": "plugin-uuid",
        "name": "my-function",
        "version": "1.0.0",
        "artifact_uri": "https://...",
        "artifact_checksum": "sha256:<hex>",
        "entrypoint": "_start",
        "runtime_type": "wasm-wasi",
        "timeout_seconds": 30,
        "memory_limit_mb": 64,
        "permissions": ["fs_read"],
        "required_capabilities": ["wasm_wasi"]
      }
    """
    function_id = payload.get("id") or str(uuid4())
    artifact_uri = payload.get("artifact_uri")
    expected_checksum = payload.get("artifact_checksum", "")

    if not artifact_uri:
        raise HTTPException(status_code=400, detail="artifact_uri is required")

    # Download artifact
    try:
        resp = httpx.get(artifact_uri, timeout=DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"artifact download failed: {exc}") from exc

    artifact_bytes = resp.content

    # Verify checksum
    actual_hash = "sha256:" + hashlib.sha256(artifact_bytes).hexdigest()
    if expected_checksum and actual_hash != expected_checksum:
        raise HTTPException(
            status_code=422,
            detail=f"checksum mismatch: expected {expected_checksum}, got {actual_hash}",
        )

    # Persist WASM file
    wasm_file = _wasm_path(function_id)
    wasm_file.write_bytes(artifact_bytes)

    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "id": function_id,
        "name": payload.get("name", function_id),
        "version": payload.get("version", "unknown"),
        "runtime_type": payload.get("runtime_type", "wasm-wasi"),
        "entrypoint": payload.get("entrypoint", "_start"),
        "artifact_uri": artifact_uri,
        "artifact_checksum": actual_hash,
        "timeout_seconds": payload.get("timeout_seconds", 30),
        "memory_limit_mb": payload.get("memory_limit_mb", MAX_MEMORY_MB_DEFAULT),
        "permissions": payload.get("permissions", []),
        "wasm_size_bytes": len(artifact_bytes),
        "status": "installed",
        "installed_at": now,
        "last_invoked_at": None,
        "last_error": None,
        "invocation_count": 0,
    }
    _meta_path(function_id).write_text(json.dumps(meta, indent=2))
    _installed[function_id] = meta

    logger.info(json.dumps({
        "service": "function-runtime",
        "event": "installed",
        "function_id": function_id,
        "wasm_size_bytes": len(artifact_bytes),
        "checksum": actual_hash,
    }))

    return meta


@app.post("/runtime/functions/{function_id}/invoke")
async def invoke_function(function_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a WASM/WASI function with the provided args.

    Uses wasmtime-py if available; falls back to a sandboxed subprocess
    stub for environments without wasmtime installed.

    Returns:
      {"exit_code": 0, "stdout": "...", "stderr": "...", "function_result": {...},
       "duration_seconds": 0.1}
    """
    fn = _installed.get(function_id)
    if not fn:
        raise HTTPException(status_code=404, detail="function not installed")

    wasm_file = _wasm_path(function_id)
    if not wasm_file.exists():
        raise HTTPException(status_code=409, detail="WASM artifact file missing — reinstall required")

    args = payload.get("args", {})
    entrypoint = payload.get("entrypoint") or fn.get("entrypoint", "_start")
    timeout = payload.get("timeout_seconds") or fn.get("timeout_seconds", 30)

    started = time.perf_counter()
    result = _execute_wasm(wasm_file, entrypoint, args, timeout, fn.get("permissions", []))
    duration = round(time.perf_counter() - started, 6)

    # Update invocation stats
    fn["invocation_count"] = fn.get("invocation_count", 0) + 1
    fn["last_invoked_at"] = datetime.now(timezone.utc).isoformat()
    if result.get("exit_code", 0) != 0:
        fn["last_error"] = result.get("stderr", "")
    else:
        fn["last_error"] = None
    _meta_path(function_id).write_text(json.dumps(fn, indent=2))

    logger.info(json.dumps({
        "service": "function-runtime",
        "event": "invoked",
        "function_id": function_id,
        "exit_code": result.get("exit_code"),
        "duration_seconds": duration,
    }))

    return {**result, "duration_seconds": duration, "function_id": function_id}


@app.delete("/runtime/functions/{function_id}", status_code=204)
async def remove_function(function_id: str) -> None:
    if function_id not in _installed:
        raise HTTPException(status_code=404, detail="function not installed")

    wasm_file = _wasm_path(function_id)
    meta_file = _meta_path(function_id)
    if wasm_file.exists():
        wasm_file.unlink()
    if meta_file.exists():
        meta_file.unlink()
    del _installed[function_id]

    logger.info(json.dumps({
        "service": "function-runtime",
        "event": "removed",
        "function_id": function_id,
    }))


# ── WASM Execution Engine ─────────────────────────────────────────────────────

def _execute_wasm(
    wasm_file: Path,
    entrypoint: str,
    args: dict[str, Any],
    timeout: int,
    permissions: list[str],
) -> dict[str, Any]:
    """
    Execute a WASM/WASI module.

    Tries wasmtime-py first (full sandbox). Falls back to a simulation
    stub when wasmtime is not installed (useful for dev/emulator environments).
    """
    try:
        return _execute_wasmtime(wasm_file, entrypoint, args, timeout, permissions)
    except ImportError:
        logger.warning("wasmtime not installed — using execution stub")
        return _execute_stub(wasm_file, entrypoint, args)


def _execute_wasmtime(
    wasm_file: Path,
    entrypoint: str,
    args: dict[str, Any],
    timeout: int,
    permissions: list[str],
) -> dict[str, Any]:
    """Execute using wasmtime-py with WASI sandbox."""
    from wasmtime import Config, Engine, Linker, Module, Store, WasiConfig  # type: ignore[import]

    import io
    from contextlib import redirect_stdout, redirect_stderr

    engine_config = Config()
    engine_config.consume_fuel = True  # enables fuel-based timeout
    engine = Engine(engine_config)

    store = Store(engine)
    store.add_fuel(timeout * 1_000_000)  # rough fuel limit per second

    wasi_cfg = WasiConfig()
    # Pass args as first argv element (JSON-encoded)
    wasi_cfg.argv = ["function", json.dumps(args)]

    # Apply permissions
    if "fs_read" in permissions:
        wasi_cfg.preopen_dir("/tmp", "/tmp")
    if "inherit_env" in permissions:
        wasi_cfg.inherit_env()

    # Capture stdout/stderr via WASI pipes
    stdout_buf = io.BytesIO()
    stderr_buf = io.BytesIO()
    wasi_cfg.set_stdout_bytes(stdout_buf)
    wasi_cfg.set_stderr_bytes(stderr_buf)

    store.set_wasi(wasi_cfg)

    linker = Linker(engine)
    linker.define_wasi()
    module = Module(engine, wasm_file.read_bytes())
    instance = linker.instantiate(store, module)

    try:
        fn = instance.exports(store).get(entrypoint)
        if fn is None and entrypoint != "_start":
            fn = instance.exports(store).get("_start")
        if fn is not None:
            fn(store)
        exit_code = 0
    except Exception as exc:
        stderr_buf.write(str(exc).encode())
        exit_code = 1

    stdout_text = stdout_buf.getvalue().decode("utf-8", errors="replace")
    stderr_text = stderr_buf.getvalue().decode("utf-8", errors="replace")

    # Attempt to parse stdout as structured JSON result
    function_result: dict | None = None
    try:
        function_result = json.loads(stdout_text)
    except (ValueError, TypeError):
        function_result = {"output": stdout_text} if stdout_text.strip() else None

    return {
        "exit_code": exit_code,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "function_result": function_result,
    }


def _execute_stub(
    wasm_file: Path,
    entrypoint: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """
    Simulation stub used when wasmtime is not installed.

    Verifies the file exists (integrity check) and returns a synthetic
    result. Used in emulator/CI environments without a real WASM runtime.
    """
    if not wasm_file.exists():
        return {"exit_code": 1, "stdout": "", "stderr": "wasm file not found", "function_result": None}

    file_size = wasm_file.stat().st_size
    stdout = json.dumps({"status": "ok", "args_received": args, "stub": True})
    return {
        "exit_code": 0,
        "stdout": stdout,
        "stderr": "",
        "function_result": {"status": "ok", "args_received": args, "stub": True, "wasm_size_bytes": file_size},
    }
