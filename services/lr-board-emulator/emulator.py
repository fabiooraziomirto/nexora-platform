import json
import os
import time
import uuid
import urllib.error
import urllib.request


DEVICE_URL = os.getenv("DEVICE_URL", "http://device-service:8000").rstrip("/")
EXEC_URL = os.getenv("EXEC_URL", "http://execution-service:8000").rstrip("/")
GW_URL = os.getenv("GW_URL", "http://lightningrod-gateway:8000").rstrip("/")
RUNTIME_URL = os.getenv("RUNTIME_URL", "http://nexora-function-runtime:9000").rstrip("/")
BOOTSTRAP_TOKEN = os.getenv("BOOTSTRAP_TOKEN", "dev-bootstrap:dev-bootstrap-token")
BOARD_NAME = os.getenv("BOARD_NAME", f"lr-board-{uuid.uuid4().hex[:8]}")
BOARD_TYPE = os.getenv("BOARD_TYPE", "lightningrod-emulator")
HEARTBEAT_SECONDS = float(os.getenv("HEARTBEAT_SECONDS", "10"))
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "4"))


def _http_json(method: str, url: str, payload: dict | None = None, headers: dict | None = None):
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


def register_board() -> str:
    payload = {"name": BOARD_NAME, "device_type": BOARD_TYPE}
    data = _http_json(
        "POST",
        f"{DEVICE_URL}/api/v2/agents/register",
        payload,
        headers={"X-Bootstrap-Token": BOOTSTRAP_TOKEN},
    )
    return data["device_id"]


def register_gateway_session(device_id: str) -> None:
    _http_json(
        "POST",
        f"{GW_URL}/api/v2/agents/sessions/register",
        {"device_id": device_id, "board_name": BOARD_NAME, "type": BOARD_TYPE},
    )


def heartbeat(device_id: str) -> None:
    _http_json("POST", f"{DEVICE_URL}/api/v2/agents/{device_id}/heartbeat", {})
    _http_json("POST", f"{GW_URL}/api/v2/agents/sessions/{device_id}/heartbeat", {})


def list_executions() -> list[dict]:
    data = _http_json("GET", f"{EXEC_URL}/api/v2/executions")
    return data.get("items", [])


def _handle_function_install(execution_id: str, execution: dict) -> dict:
    plugin = execution.get("plugin") or {}
    try:
        resp = _http_json(
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
        return {"status": "installed", "exit_code": 0, "stdout": f"installed {plugin.get('id')} on {BOARD_NAME}\n", "stderr": ""}
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


def handle_execution(device_id: str, execution: dict) -> None:
    execution_id = execution["id"]
    status = execution.get("status")
    if status not in ("dispatched", "queued"):
        return

    try:
        _http_json("POST", f"{GW_URL}/api/v2/deliver/{execution_id}", {})
    except Exception:
        return

    exec_type = execution.get("execution_type", "command")
    _http_json("POST", f"{EXEC_URL}/api/v2/executions/{execution_id}/callback", {"status": "running"})
    time.sleep(1)

    if exec_type == "function.install":
        result = _handle_function_install(execution_id, execution)
    elif exec_type == "function.invoke":
        result = _handle_function_invoke(execution_id, execution)
    else:
        result = {"status": "succeeded", "exit_code": 0, "stdout": f"ok from {BOARD_NAME}\n", "stderr": ""}

    callback_payload = {k: v for k, v in result.items() if v is not None}
    _http_json("POST", f"{EXEC_URL}/api/v2/executions/{execution_id}/callback", callback_payload)
    print(f"[{BOARD_NAME}] {exec_type} {execution_id} -> {result['status']}", flush=True)


def main() -> None:
    while True:
        try:
            device_id = register_board()
            register_gateway_session(device_id)
            print(f"[{BOARD_NAME}] registered device_id={device_id}", flush=True)
            break
        except Exception as exc:
            print(f"[{BOARD_NAME}] bootstrap failed: {exc}; retrying...", flush=True)
            time.sleep(3)

    last_heartbeat = 0.0
    while True:
        now = time.time()
        try:
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                heartbeat(device_id)
                last_heartbeat = now
            for execution in list_executions():
                if execution.get("device_id") == device_id:
                    handle_execution(device_id, execution)
        except urllib.error.HTTPError as exc:
            print(f"[{BOARD_NAME}] http error {exc.code}", flush=True)
        except Exception as exc:
            print(f"[{BOARD_NAME}] loop error: {exc}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
