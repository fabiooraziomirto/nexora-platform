"""
nexora-device-emulator — multi-board NexoraEdge edge agent simulator.

Single-board mode (backward compatible):
    python emulator.py

Multi-board mode:
    python emulator.py --n-boards 10 --fail-rate 0.1 --delay-ms 200 --kill-after 60

WebSocket tunnel mode (Phase 1 — push delivery instead of HTTP poll):
    python emulator.py --ws-mode --n-boards 5 --reconnect-interval 30

Intermittency simulation:
    --kill-after N      Board exits after N seconds (simulates device power-off)
    --reconnect-interval N  Force WS reconnect every N seconds (simulates NAT rebind / flap)
    --fail-rate P       Fraction of executions that report 'failed' (0.0-1.0)
    --delay-ms N        Extra delay before callback (simulates slow agent)

All options are also readable from environment variables (CLI wins over env):
    N_BOARDS=10 WS_MODE=true RECONNECT_INTERVAL=30 FAIL_RATE=0.1 python emulator.py
"""

import argparse
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

try:
    from websockets.sync.client import connect as _ws_connect
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEVICE_URL = os.getenv("DEVICE_URL", "http://device-service:8000").rstrip("/")
EXEC_URL = os.getenv("EXEC_URL", "http://execution-service:8000").rstrip("/")
GW_URL = os.getenv("GW_URL", "http://nexora-edge:8000").rstrip("/")
GW_WS_URL = os.getenv(
    "GW_WS_URL",
    GW_URL.replace("http://", "ws://").replace("https://", "wss://"),
)
RUNTIME_URL = os.getenv("RUNTIME_URL", "http://nexora-function-runtime:9000").rstrip("/")
BOOTSTRAP_TOKEN = os.getenv("BOOTSTRAP_TOKEN", "dev-bootstrap:dev-bootstrap-token")
BOARD_NAME = os.getenv("BOARD_NAME", "")  # auto-generated per board if empty
BOARD_TYPE = os.getenv("BOARD_TYPE", "nexoraedge-emulator")
HEARTBEAT_SECONDS = float(os.getenv("HEARTBEAT_SECONDS", "10"))
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "4"))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NexoraEdge multi-board emulator")
    p.add_argument(
        "--n-boards", type=int,
        default=int(os.getenv("N_BOARDS", "1")),
        help="Number of parallel boards to simulate (default: 1)",
    )
    p.add_argument(
        "--fail-rate", type=float,
        default=float(os.getenv("FAIL_RATE", "0.0")),
        help="Fraction of executions that return 'failed' (0.0-1.0, default: 0.0)",
    )
    p.add_argument(
        "--delay-ms", type=float,
        default=float(os.getenv("DELAY_MS", "0")),
        help="Extra delay in ms before sending callback (simulates slow agent, default: 0)",
    )
    p.add_argument(
        "--kill-after", type=float,
        default=float(os.getenv("KILL_AFTER", "0")),
        help="Board exits after this many seconds (0 = run forever, default: 0)",
    )
    p.add_argument(
        "--board-name-prefix", type=str,
        default=os.getenv("BOARD_NAME_PREFIX", BOARD_NAME or "lr-board"),
        help="Prefix for board names; suffix is -<index> for N>1 (default: lr-board)",
    )
    p.add_argument(
        "--ws-mode", action="store_true",
        default=os.getenv("WS_MODE", "").lower() in ("true", "1", "yes"),
        help="Use WebSocket tunnel for push delivery instead of HTTP polling (requires websockets package)",
    )
    p.add_argument(
        "--reconnect-interval", type=float,
        default=float(os.getenv("RECONNECT_INTERVAL", "0")),
        help="Force WS reconnect after this many seconds (0 = never, simulates NAT rebind/churn)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _http_json(
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict | None = None,
) -> Any:
    body = None
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=body, headers=req_headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


# ---------------------------------------------------------------------------
# Structured log output
# ---------------------------------------------------------------------------

_log_lock = threading.Lock()


def _log(board_name: str, event: str, **fields: Any) -> None:
    record = {
        "ts": round(time.time(), 6),
        "board": board_name,
        "event": event,
        **fields,
    }
    with _log_lock:
        print(json.dumps(record), flush=True)


# ---------------------------------------------------------------------------
# Board lifecycle
# ---------------------------------------------------------------------------

def _register(board_name: str) -> str:
    data = _http_json(
        "POST",
        f"{DEVICE_URL}/api/v2/agents/register",
        {"name": board_name, "device_type": BOARD_TYPE},
        headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
    )
    return data["device_id"]


def _register_session(device_id: str, board_name: str) -> None:
    _http_json(
        "POST",
        f"{GW_URL}/api/v2/agents/sessions/register",
        {"device_id": device_id, "board_name": board_name, "type": BOARD_TYPE},
    )


def _heartbeat(device_id: str) -> None:
    _http_json("POST", f"{DEVICE_URL}/api/v2/agents/{device_id}/heartbeat", {})
    _http_json("POST", f"{GW_URL}/api/v2/agents/sessions/{device_id}/heartbeat", {})


def _list_executions() -> list[dict]:
    data = _http_json("GET", f"{EXEC_URL}/api/v2/executions")
    return data.get("items", [])


# ---------------------------------------------------------------------------
# Execution handlers
# ---------------------------------------------------------------------------

def _handle_function_install(execution_id: str, payload: dict) -> dict:
    plugin = payload.get("plugin") or {}
    try:
        _http_json(
            "POST",
            f"{RUNTIME_URL}/runtime/functions/install",
            {
                "id": plugin.get("id"),
                "name": plugin.get("name", ""),
                "version": plugin.get("version", "1.0.0"),
                "runtime_type": plugin.get("runtime_type", "wasm-wasi"),
                "artifact_uri": plugin.get("artifact_uri"),
                "artifact_checksum": plugin.get("artifact_checksum"),
                "entrypoint": plugin.get("entrypoint", "_start"),
                "timeout_seconds": plugin.get("timeout_seconds", 30),
                "memory_limit_mb": plugin.get("memory_limit_mb", 64),
                "permissions": plugin.get("permissions", []),
            },
        )
        return {
            "status": "succeeded",
            "exit_code": 0,
            "stdout": f"installed {plugin.get('id')}\n",
            "stderr": "",
        }
    except Exception as exc:
        return {"status": "failed", "exit_code": 1, "stdout": "", "stderr": str(exc)}


def _handle_function_invoke(execution_id: str, payload: dict) -> dict:
    plugin = payload.get("plugin") or {}
    args = payload.get("args") or {}
    function_id = plugin.get("id")
    if not function_id:
        return {"status": "failed", "exit_code": 1, "stderr": "missing plugin id in dispatch payload"}
    try:
        resp = _http_json(
            "POST",
            f"{RUNTIME_URL}/runtime/functions/{function_id}/invoke",
            {"args": args, "entrypoint": plugin.get("entrypoint", "_start")},
        )
        return {
            "status": "succeeded",
            "exit_code": resp.get("exit_code", 0),
            "stdout": resp.get("stdout", ""),
            "stderr": resp.get("stderr", ""),
            "function_result": resp.get("function_result"),
        }
    except Exception as exc:
        return {"status": "failed", "exit_code": 1, "stderr": str(exc), "function_result": None}


def _handle_execution(
    device_id: str,
    board_name: str,
    execution: dict,
    *,
    fail_rate: float,
    delay_ms: float,
) -> None:
    execution_id = execution["id"]
    status = execution.get("status")
    if status not in ("dispatched", "queued"):
        return

    t_start = time.time()

    try:
        delivery_resp = _http_json("POST", f"{GW_URL}/api/v2/deliver/{execution_id}", {})
    except Exception as exc:
        _log(board_name, "deliver_error", execution_id=execution_id, error=str(exc))
        return

    # Use the Kafka event payload from the gateway (includes full plugin object).
    dispatch_payload = delivery_resp.get("payload") or execution
    exec_type = dispatch_payload.get("execution_type") or execution.get("execution_type", "command")
    _http_json(
        "POST",
        f"{EXEC_URL}/api/v2/executions/{execution_id}/callback",
        {"status": "running"},
    )

    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    else:
        time.sleep(1)

    if fail_rate > 0 and random.random() < fail_rate:
        result: dict = {
            "status": "failed",
            "exit_code": 1,
            "stdout": "",
            "stderr": f"injected failure (fail_rate={fail_rate})",
        }
    elif exec_type == "function.install":
        result = _handle_function_install(execution_id, dispatch_payload)
    elif exec_type == "function.invoke":
        result = _handle_function_invoke(execution_id, dispatch_payload)
    else:
        result = {
            "status": "succeeded",
            "exit_code": 0,
            "stdout": f"ok from {board_name}\n",
            "stderr": "",
        }

    callback_payload = {k: v for k, v in result.items() if v is not None}
    _http_json(
        "POST",
        f"{EXEC_URL}/api/v2/executions/{execution_id}/callback",
        callback_payload,
    )

    latency_ms = round((time.time() - t_start) * 1000, 2)
    _log(
        board_name,
        "execution_complete",
        execution_id=execution_id,
        exec_type=exec_type,
        final_status=result["status"],
        latency_ms=latency_ms,
        injected_failure=(fail_rate > 0 and result["status"] == "failed"),
    )


# ---------------------------------------------------------------------------
# Heartbeat thread (used in WS mode to keep device-service session alive)
# ---------------------------------------------------------------------------

def _heartbeat_loop(
    device_id: str,
    board_name: str,
    stop_event: threading.Event,
) -> None:
    """Send HTTP heartbeats to device-service while stop_event is not set."""
    while not stop_event.wait(HEARTBEAT_SECONDS):
        try:
            _http_json("POST", f"{DEVICE_URL}/api/v2/agents/{device_id}/heartbeat", {})
        except Exception as exc:
            _log(board_name, "hb_error", device_id=device_id, error=str(exc))


# ---------------------------------------------------------------------------
# WS board loop (Phase 1 — push delivery via tunnel)
# ---------------------------------------------------------------------------

def _handle_execution_ws(
    device_id: str,
    board_name: str,
    msg: dict,
    ws: Any,
    *,
    fail_rate: float,
    delay_ms: float,
) -> None:
    """Handle a control push received over WebSocket."""
    execution_id = msg.get("execution_id", "")
    payload = msg.get("payload", {})
    exec_type = payload.get("execution_type", "command")
    t_start = time.time()

    try:
        _http_json(
            "POST",
            f"{EXEC_URL}/api/v2/executions/{execution_id}/callback",
            {"status": "running"},
        )
    except Exception as exc:
        _log(board_name, "callback_running_error", execution_id=execution_id, error=str(exc))

    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    else:
        time.sleep(1)

    if fail_rate > 0 and random.random() < fail_rate:
        result: dict = {
            "status": "failed",
            "exit_code": 1,
            "stdout": "",
            "stderr": f"injected failure (fail_rate={fail_rate})",
        }
    elif exec_type == "function.install":
        result = _handle_function_install(execution_id, payload)
    elif exec_type == "function.invoke":
        result = _handle_function_invoke(execution_id, payload)
    else:
        result = {
            "status": "succeeded",
            "exit_code": 0,
            "stdout": f"ok from {board_name}\n",
            "stderr": "",
        }

    # ACK to gateway so it can remove the dispatch from cache.
    try:
        ws.send(json.dumps({"type": "ack", "execution_id": execution_id}))
    except Exception as exc:
        _log(board_name, "ws_ack_error", execution_id=execution_id, error=str(exc))

    # Final callback to execution-service.
    callback_payload = {k: v for k, v in result.items() if v is not None}
    try:
        _http_json(
            "POST",
            f"{EXEC_URL}/api/v2/executions/{execution_id}/callback",
            callback_payload,
        )
    except Exception as exc:
        _log(board_name, "callback_final_error", execution_id=execution_id, error=str(exc))

    latency_ms = round((time.time() - t_start) * 1000, 2)
    _log(
        board_name,
        "execution_complete_ws",
        execution_id=execution_id,
        exec_type=exec_type,
        final_status=result["status"],
        latency_ms=latency_ms,
        injected_failure=(fail_rate > 0 and result["status"] == "failed"),
    )


def _run_board_ws(
    board_name: str,
    device_id: str,
    *,
    fail_rate: float,
    delay_ms: float,
    kill_after: float,
    reconnect_interval: float,
    result_bucket: list[str],
) -> None:
    """WS tunnel mode: receive push notifications instead of HTTP polling.

    Intermittency scenarios exercised:
    - kill_after: simulates device power-off / hard disconnect
    - reconnect_interval: forces WS reconnect (simulates NAT rebind, flap)
    """
    if not HAS_WEBSOCKETS:
        _log(board_name, "ws_mode_unavailable",
             error="websockets package not installed; falling back to HTTP poll mode")
        result_bucket.append("error")
        return

    start_time = time.time()
    ws_uri = f"{GW_WS_URL}/api/v2/agents/ws/{device_id}"
    connect_count = 0

    # Start heartbeat thread.
    stop_hb = threading.Event()
    hb_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(device_id, board_name, stop_hb),
        daemon=True,
    )
    hb_thread.start()

    try:
        while True:
            if kill_after > 0 and (time.time() - start_time) >= kill_after:
                _log(board_name, "killed", device_id=device_id,
                     uptime_s=round(time.time() - start_time, 2))
                result_bucket.append("killed")
                return

            connect_count += 1
            if connect_count > 1:
                _log(board_name, "ws_reconnect", device_id=device_id, attempt=connect_count)

            try:
                with _ws_connect(ws_uri) as ws:
                    _log(board_name, "ws_connected", device_id=device_id, attempt=connect_count)
                    connect_start = time.time()

                    while True:
                        if kill_after > 0 and (time.time() - start_time) >= kill_after:
                            break
                        if reconnect_interval > 0 and (time.time() - connect_start) >= reconnect_interval:
                            _log(board_name, "ws_forced_reconnect", device_id=device_id,
                                 uptime_s=round(time.time() - connect_start, 2))
                            break

                        try:
                            raw = ws.recv(timeout=1.0)
                            msg = json.loads(raw)
                            msg_type = msg.get("type")

                            if msg_type == "control":
                                _handle_execution_ws(
                                    device_id, board_name, msg, ws,
                                    fail_rate=fail_rate, delay_ms=delay_ms,
                                )
                            elif msg_type == "ping":
                                ws.send(json.dumps({"type": "pong"}))

                        except TimeoutError:
                            # No message within timeout — send a heartbeat over WS.
                            try:
                                ws.send(json.dumps({"type": "heartbeat"}))
                            except Exception:
                                break  # Connection broken; reconnect.

            except Exception as exc:
                _log(board_name, "ws_error", device_id=device_id, error=str(exc))
                time.sleep(3)  # Backoff before reconnect.

    finally:
        stop_hb.set()
        hb_thread.join(timeout=5)

    result_bucket.append("ok")


# ---------------------------------------------------------------------------
# Board main loop
# ---------------------------------------------------------------------------

def _run_board(
    board_name: str,
    device_id: str,
    *,
    fail_rate: float,
    delay_ms: float,
    kill_after: float,
    result_bucket: list[str],
) -> None:
    """HTTP-poll board lifecycle. Appends 'ok'/'error'/'killed' to result_bucket on exit."""
    start_time = time.time()
    last_heartbeat = 0.0
    try:
        while True:
            if kill_after > 0 and (time.time() - start_time) >= kill_after:
                _log(board_name, "killed", device_id=device_id, uptime_s=round(time.time() - start_time, 2))
                result_bucket.append("killed")
                return

            now = time.time()
            try:
                if now - last_heartbeat >= HEARTBEAT_SECONDS:
                    _heartbeat(device_id)
                    last_heartbeat = now

                for execution in _list_executions():
                    if execution.get("device_id") == device_id:
                        _handle_execution(
                            device_id,
                            board_name,
                            execution,
                            fail_rate=fail_rate,
                            delay_ms=delay_ms,
                        )

            except urllib.error.HTTPError as exc:
                _log(board_name, "http_error", code=exc.code)
            except Exception as exc:
                _log(board_name, "loop_error", error=str(exc))

            time.sleep(POLL_SECONDS)

    except Exception as exc:
        _log(board_name, "fatal_error", error=str(exc))
        result_bucket.append("error")
        return

    result_bucket.append("ok")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()
    n = args.n_boards
    fail_rate = max(0.0, min(1.0, args.fail_rate))
    delay_ms = max(0.0, args.delay_ms)
    kill_after = max(0.0, args.kill_after)
    prefix = args.board_name_prefix
    ws_mode = args.ws_mode
    reconnect_interval = max(0.0, args.reconnect_interval)

    _log("__launcher__", "start", n_boards=n, fail_rate=fail_rate,
         delay_ms=delay_ms, kill_after=kill_after, prefix=prefix,
         ws_mode=ws_mode, reconnect_interval=reconnect_interval)

    if ws_mode and not HAS_WEBSOCKETS:
        _log("__launcher__", "ws_mode_unavailable",
             error="websockets package not installed; install it with: pip install websockets")
        sys.exit(1)

    def _launch_board(board_name: str, result_bucket: list[str]) -> None:
        """Register the board, then run it in the selected mode."""
        device_id: str | None = None
        while True:
            try:
                device_id = _register(board_name)
                _register_session(device_id, board_name)
                _log(board_name, "registered", device_id=device_id)
                break
            except Exception as exc:
                _log(board_name, "bootstrap_retry", error=str(exc))
                time.sleep(3)

        if ws_mode:
            _run_board_ws(
                board_name, device_id,
                fail_rate=fail_rate, delay_ms=delay_ms,
                kill_after=kill_after, reconnect_interval=reconnect_interval,
                result_bucket=result_bucket,
            )
        else:
            _run_board(
                board_name, device_id,
                fail_rate=fail_rate, delay_ms=delay_ms,
                kill_after=kill_after, result_bucket=result_bucket,
            )

    if n == 1:
        board_name = prefix if BOARD_NAME else f"{prefix}-{uuid.uuid4().hex[:8]}"
        result_bucket: list[str] = []
        _launch_board(board_name, result_bucket)
        sys.exit(0 if result_bucket and result_bucket[0] in ("ok", "killed") else 1)

    threads: list[threading.Thread] = []
    results: list[list[str]] = [[] for _ in range(n)]

    for i in range(n):
        board_name = f"{prefix}-{i+1:03d}"
        t = threading.Thread(
            target=_launch_board,
            args=(board_name, results[i]),
            daemon=True,
            name=f"board-{i+1:03d}",
        )
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    errors = sum(1 for r in results if r and r[0] == "error")
    _log("__launcher__", "done", n_boards=n, errors=errors)
    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
