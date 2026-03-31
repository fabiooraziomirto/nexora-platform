import json
import os
import time
import uuid
import urllib.error
import urllib.request


DEVICE_URL = os.getenv("DEVICE_URL", "http://device-service:8000").rstrip("/")
EXEC_URL = os.getenv("EXEC_URL", "http://execution-service:8000").rstrip("/")
GW_URL = os.getenv("GW_URL", "http://lightningrod-gateway:8000").rstrip("/")
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


def handle_execution(device_id: str, execution: dict) -> None:
    execution_id = execution["id"]
    status = execution.get("status")
    if status not in ("dispatched", "queued"):
        return

    try:
        _http_json("POST", f"{GW_URL}/api/v2/deliver/{execution_id}", {})
    except Exception:
        return

    _http_json("POST", f"{EXEC_URL}/api/v2/executions/{execution_id}/callback", {"status": "running"})
    time.sleep(1)
    _http_json(
        "POST",
        f"{EXEC_URL}/api/v2/executions/{execution_id}/callback",
        {"status": "succeeded", "exit_code": 0, "stdout": f"ok from {BOARD_NAME}\n", "stderr": ""},
    )
    print(f"[{BOARD_NAME}] executed {execution_id} -> succeeded", flush=True)


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
