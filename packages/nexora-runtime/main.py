"""nexora-runtime — local WASM function runtime for nexora-agent.

Exposes a minimal HTTP API on localhost:9001 (not exposed externally):
  POST /runtime/functions/install        → download + verify + store WASM artifact
  POST /runtime/functions/{id}/invoke    → execute installed function with args
  DELETE /runtime/functions/{id}         → uninstall function
  GET  /runtime/functions                → list installed functions
  GET  /health                           → health check
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from nexora_runtime import function_store, wasm_executor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("nexora-runtime")

PORT = int(os.getenv("NEXORA_RUNTIME_PORT", "9001"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    function_store.STORE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("nexora-runtime started — store=%s wasm=%s",
                function_store.STORE_DIR, wasm_executor._WASMTIME_AVAILABLE)
    yield


app = FastAPI(title="nexora-runtime", version="1.0.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InstallRequest(BaseModel):
    function_id: str
    artifact_uri: str
    checksum: str | None = None
    runtime_type: str = "wasm"
    memory_mb: int = 64
    timeout_ms: int = 30000


class InvokeRequest(BaseModel):
    args: dict = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/runtime/functions/install", status_code=201)
async def install_function(req: InstallRequest):
    try:
        meta = await function_store.install(
            function_id=req.function_id,
            artifact_uri=req.artifact_uri,
            checksum=req.checksum,
            runtime_type=req.runtime_type,
            memory_mb=req.memory_mb,
            timeout_ms=req.timeout_ms,
        )
        return {"status": "installed", **meta}
    except function_store.ChecksumMismatch as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Install failed function_id=%s: %s", req.function_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/runtime/functions/{function_id}/invoke")
async def invoke_function(function_id: str, req: InvokeRequest):
    try:
        result = await wasm_executor.invoke(function_id, req.args)
        return result
    except function_store.FunctionNotFound:
        raise HTTPException(status_code=404, detail=f"Function '{function_id}' not installed")
    except wasm_executor.TimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc))
    except wasm_executor.ExecutionError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.error("Invoke failed function_id=%s: %s", function_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.delete("/runtime/functions/{function_id}", status_code=204)
async def uninstall_function(function_id: str):
    if not function_store.is_installed(function_id):
        raise HTTPException(status_code=404, detail=f"Function '{function_id}' not installed")
    function_store.uninstall(function_id)


@app.get("/runtime/functions")
async def list_functions():
    installed = function_store.list_installed()
    functions = []
    for fid in installed:
        try:
            meta = function_store.get_metadata(fid)
        except Exception:
            meta = {"function_id": fid}
        functions.append(meta)
    return {"functions": functions}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "wasmtime_available": wasm_executor._WASMTIME_AVAILABLE,
        "installed_functions": len(function_store.list_installed()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=PORT, reload=False)
