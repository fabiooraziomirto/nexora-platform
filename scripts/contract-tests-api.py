#!/usr/bin/env python3
import json
import urllib.request


def _request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _assert_fields(name: str, data: dict, expected: dict[str, type]) -> None:
    for key, kind in expected.items():
        assert key in data, f"{name}: missing key '{key}'"
        assert isinstance(data[key], kind), f"{name}: key '{key}' should be {kind.__name__}"


def main() -> None:
    plugin = _request_json(
        "http://localhost:8001/api/v2/plugins",
        method="POST",
        payload={"name": "contract-plugin"},
    )
    _assert_fields("plugin.create", plugin, {"id": str, "name": str})

    execution = _request_json(
        "http://localhost:8002/api/v2/executions",
        method="POST",
        payload={"device_id": "contract-device", "command": "noop"},
    )
    _assert_fields(
        "execution.create",
        execution,
        {"id": str, "device_id": str, "command": str, "status": str},
    )

    port = _request_json(
        "http://localhost:8003/api/v2/ports",
        method="POST",
        payload={"device_id": "contract-device", "network_id": "contract-net"},
    )
    _assert_fields(
        "network.create",
        port,
        {"id": str, "device_id": str, "network_id": str, "status": str},
    )

    dns_record = _request_json(
        "http://localhost:8004/api/v2/dns/records",
        method="POST",
        payload={"name": "contract.example.org", "type": "A", "value": "10.0.0.99"},
    )
    _assert_fields(
        "dns.create",
        dns_record,
        {"id": str, "name": str, "type": str, "value": str},
    )

    webservice = _request_json(
        "http://localhost:8005/api/v2/webservices",
        method="POST",
        payload={"device_id": "contract-device", "port": 9443},
    )
    _assert_fields(
        "webservice.create",
        webservice,
        {"id": str, "device_id": str, "port": int, "status": str},
    )

    fleet = _request_json(
        "http://localhost:8006/api/v2/fleets",
        method="POST",
        payload={"name": "contract-fleet", "description": "contract-check"},
    )
    _assert_fields(
        "fleet.create",
        fleet,
        {"id": str, "name": str},
    )

    print("API contract tests passed")


if __name__ == "__main__":
    main()
