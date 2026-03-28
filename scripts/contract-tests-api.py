#!/usr/bin/env python3
import json
import urllib.request
import urllib.error


def _request_json(
    url: str,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict | None = None,
) -> dict:
    body = None
    hdrs = dict(headers) if headers else {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    request = urllib.request.Request(url=url, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _expect_http_error(
    url: str,
    expected_code: int,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict | None = None,
) -> None:
    body = None
    hdrs = dict(headers) if headers else {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=body, headers=hdrs, method=method)
    try:
        urllib.request.urlopen(req, timeout=15)
        raise AssertionError(f"{url}: expected HTTP {expected_code} but got 2xx")
    except urllib.error.HTTPError as exc:
        assert exc.code == expected_code, (
            f"{url}: expected HTTP {expected_code}, got {exc.code}"
        )


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

    _negative_contract_checks()

    print("API contract tests passed (positive + negative)")


def _negative_contract_checks() -> None:
    _expect_http_error(
        "http://localhost:8002/api/v2/executions/00000000-0000-0000-0000-000000000000",
        404,
    )

    _expect_http_error(
        "http://localhost:8001/api/v2/plugins/00000000-0000-0000-0000-000000000000",
        404,
    )

    _expect_http_error(
        "http://localhost:8000/api/v2/agents/register",
        401,
        method="POST",
        payload={"name": "bad", "device_type": "sensor"},
        headers={"X-Bootstrap-Token": "dev-bootstrap:WRONG-SECRET"},
    )

    _expect_http_error(
        "http://localhost:8002/api/v2/executions/00000000-0000-0000-0000-000000000000/callback",
        404,
        method="POST",
        payload={"status": "succeeded"},
    )

    _expect_http_error(
        "http://localhost:8007/api/v2/agents/sessions/nonexistent",
        404,
    )


if __name__ == "__main__":
    main()
