"""
nexora-device-emulator — multi-board NexoraEdge edge agent simulator.

Single-board mode (backward compatible):
    python emulator.py

Multi-board mode:
    python emulator.py --n-boards 10 --fail-rate 0.1 --delay-ms 200 --kill-after 60

All options are also readable from environment variables (CLI wins over env):
    N_BOARDS=10 FAIL_RATE=0.1 DELAY_MS=200 KILL_AFTER=60 python emulator.py
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


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEVICE_URL = os.getenv("DEVICE_URL", "http://device-service:8000").rstrip("/")
EXEC_URL = os.getenv("EXEC_URL", "http://execution-service:8000").rstrip("/")
GW_URL = os.getenv("GW_URL", "http://nexora-edge:8000").rstrip("/")
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

def _handle_function_install(execution_id: str, execution: dict) -> dict:
    plugin = execution.get("plugin") or {}
    try:
        _http_json(
            "POST",
            f"{RUNTIME_URL}/runtime/functions/install",
            {
                "function_id": plugin.get("id"),
                "artifact_uri": plugin.get("artifact_uri"),
                "checksum": plugin.get("artifact_checksum"),
                "entrypoint": plugin.get("entrypoint"),
                "permissions": plugin.get("permissions", []),
            },
        )
        return {
            "status": "installed",
            "exit_code": 0,
            "stdout": f"installed {plugin.get('id')}\n",
            "stderr": "",
        }
    except Exception as exc:
        return {"status": "failed", "exit_code": 1, "stdout": "", "stderr": str(exc)}


def _handle_function_invoke(execution_id: str, execution: dict) -> dict:
    plugin = execution.get("plugin") or {}
    args = execution.get("args") or {}
    function_id = plugin.get("id")
    if not function_id:
        return {"status": "failed", "exit_code": 1, "stderr": "missing plugin id"}
    try:
        resp = _http_json(
            "POST",
            f"{RUNTIME_URL}/runtime/functions/{function_id}/invoke",
            {"args": args, "entrypoint": plugin.get("entrypoint")},
        )
        return {
            "status": "succeeded",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "function_result": resp.get("result"),
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
        _http_json("POST", f"{GW_URL}/api/v2/deliver/{execution_id}", {})
    except Exception as exc:
        _log(board_name, "deliver_error", execution_id=execution_id, error=str(exc))
        return

    exec_type = execution.get("execution_type", "command")
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
        result = _handle_function_install(execution_id, execution)
    elif exec_type == "function.invoke":
        result = _handle_function_invoke(execution_id, execution)
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
# Board main loop
# ---------------------------------------------------------------------------

def _run_board(
    board_name: str,
    *,
    fail_rate: float,
    delay_ms: float,
    kill_after: float,
    result_bucket: list[str],
) -> None:
    """Run one board lifecycle. Appends 'ok' or 'error' to result_bucket on exit."""
    start_time = time.time()

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

    _log("__launcher__", "start", n_boards=n, fail_rate=fail_rate,
         delay_ms=delay_ms, kill_after=kill_after, prefix=prefix)

    if n == 1:
        board_name = prefix if BOARD_NAME else f"{prefix}-{uuid.uuid4().hex[:8]}"
        result_bucket: list[str] = []
        _run_board(
            board_name,
            fail_rate=fail_rate,
            delay_ms=delay_ms,
            kill_after=kill_after,
            result_bucket=result_bucket,
        )
        sys.exit(0 if result_bucket and result_bucket[0] in ("ok", "killed") else 1)

    threads: list[threading.Thread] = []
    results: list[list[str]] = [[] for _ in range(n)]

    for i in range(n):
        board_name = f"{prefix}-{i+1:03d}"
        t = threading.Thread(
            target=_run_board,
            kwargs=dict(
                board_name=board_name,
                fail_rate=fail_rate,
                delay_ms=delay_ms,
                kill_after=kill_after,
                result_bucket=results[i],
            ),
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
