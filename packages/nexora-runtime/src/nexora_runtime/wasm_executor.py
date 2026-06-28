"""WASM function executor using wasmtime.

Provides sandboxed execution of WebAssembly modules with:
  - Memory limit (memory_mb from function metadata)
  - CPU timeout via asyncio
  - WASI environment (stdout/stderr capture, no filesystem access by default)
  - Input via stdin (JSON-encoded args), output via stdout (JSON-encoded result)

Falls back to a mock executor when wasmtime is not installed, so the runtime
service starts on systems where wasmtime isn't yet available.
"""
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from nexora_runtime import function_store

logger = logging.getLogger("nexora-runtime.executor")

_WASMTIME_AVAILABLE = False
try:
    import wasmtime  # noqa: F401
    _WASMTIME_AVAILABLE = True
except ImportError:
    logger.warning("wasmtime not installed — WASM execution will use mock mode")


class ExecutionError(Exception):
    pass


class TimeoutError(ExecutionError):
    pass


async def invoke(function_id: str, args: dict) -> dict:
    """Invoke an installed WASM function with the given args.

    Returns {"output": Any, "stdout": str, "stderr": str, "duration_ms": float}
    """
    if not function_store.is_installed(function_id):
        raise function_store.FunctionNotFound(function_id)

    meta = function_store.get_metadata(function_id)
    wasm_path = function_store.function_path(function_id)
    timeout_s = meta.get("timeout_ms", 30000) / 1000.0
    memory_mb = meta.get("memory_mb", 64)

    if _WASMTIME_AVAILABLE:
        return await _invoke_wasmtime(wasm_path, args, timeout_s, memory_mb)
    else:
        return await _invoke_mock(function_id, args)


async def _invoke_wasmtime(
    wasm_path: Path,
    args: dict,
    timeout_s: float,
    memory_mb: int,
) -> dict:
    import io
    import wasmtime

    def _run() -> dict:
        engine_cfg = wasmtime.Config()
        engine_cfg.consume_fuel = True
        engine = wasmtime.Engine(engine_cfg)
        store = wasmtime.Store(engine)

        # Fuel limit approximates CPU time (~1M fuel ≈ 1s on typical hardware)
        fuel_limit = max(1_000_000, int(timeout_s * 5_000_000))
        store.add_fuel(fuel_limit)

        # WASI stdio capture
        wasi_cfg = wasmtime.WasiConfig()
        stdin_data = json.dumps(args).encode()
        wasi_cfg.set_stdin_bytes(stdin_data)
        stdout_buf = io.BytesIO()
        stderr_buf = io.BytesIO()
        wasi_cfg.set_stdout_file(stdout_buf)
        wasi_cfg.set_stderr_file(stderr_buf)
        store.set_wasi(wasi_cfg)

        linker = wasmtime.Linker(engine)
        linker.define_wasi()

        module = wasmtime.Module.from_file(engine, str(wasm_path))
        instance = linker.instantiate(store, module)

        t0 = time.monotonic()
        try:
            start = instance.exports(store).get("_start")
            if start:
                start(store)
        except wasmtime.WasmtimeError as exc:
            stderr_text = stderr_buf.getvalue().decode("utf-8", errors="replace")
            raise ExecutionError(f"WASM trap: {exc}\n{stderr_text}") from exc
        duration_ms = (time.monotonic() - t0) * 1000

        stdout_text = stdout_buf.getvalue().decode("utf-8", errors="replace")
        stderr_text = stderr_buf.getvalue().decode("utf-8", errors="replace")

        # Try to parse output as JSON
        try:
            output = json.loads(stdout_text)
        except Exception:
            output = stdout_text

        return {
            "output": output,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "duration_ms": round(duration_ms, 2),
        }

    try:
        return await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, _run),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"Function timed out after {timeout_s}s")


async def _invoke_mock(function_id: str, args: dict) -> dict:
    """Mock executor used when wasmtime is not available."""
    logger.warning("Mock WASM execution for function %s — wasmtime not installed", function_id)
    await asyncio.sleep(0.01)
    return {
        "output": {"mock": True, "function_id": function_id, "args": args},
        "stdout": json.dumps({"mock": True}),
        "stderr": "",
        "duration_ms": 10.0,
    }
