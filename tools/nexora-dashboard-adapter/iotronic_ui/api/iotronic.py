# -*- coding: utf-8 -*-
"""Nexora adapter for legacy Horizon panel.

This module replaces the original nexoraclient-based calls with direct HTTP
calls to Nxr v2 microservices.
"""

import json
import os
import tempfile
try:
    import urllib.request as urllib_request
    import urllib.error as urllib_error
except ImportError:  # pragma: no cover
    import urllib2 as urllib_request
    import urllib2 as urllib_error

from django.utils.translation import ugettext_lazy as _
from horizon.utils.memoized import memoized


class S4TObj(object):
    def __init__(self, data):
        self._info = dict(data or {})
        for k, v in self._info.items():
            setattr(self, k, v)


_STATE_FILE = os.path.join(tempfile.gettempdir(), "s4t_nexora_adapter_state.json")


def _load_state():
    if not os.path.exists(_STATE_FILE):
        return {"plugin_meta": {}, "services": {}}
    try:
        with open(_STATE_FILE, "r") as fh:
            state = json.load(fh)
    except Exception:
        return {"plugin_meta": {}, "services": {}}
    state.setdefault("plugin_meta", {})
    state.setdefault("services", {})
    return state


def _save_state(state):
    with open(_STATE_FILE, "w") as fh:
        json.dump(state, fh)


def _service_url(name):
    defaults = {
        "device": "http://localhost:8000",
        "plugin": "http://localhost:8001",
        "execution": "http://localhost:8002",
        "network": "http://localhost:8003",
        "dns": "http://localhost:8004",
        "webservice": "http://localhost:8005",
        "fleet": "http://localhost:8006",
    }
    env_key = "S4T_%s_URL" % name.upper()
    return os.getenv(env_key, defaults[name]).rstrip("/")


def _default_headers(request):
    headers = {"Content-Type": "application/json"}
    token = os.getenv("S4T_AUTH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer %s" % token
    tenant = os.getenv("S4T_TENANT_ID")
    if tenant:
        headers["X-Tenant-Id"] = tenant
    return headers


def _http_json(request, method, url, payload=None, allow_404=False):
    body = None
    headers = _default_headers(request)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url=url, data=body, headers=headers)
    req.get_method = lambda: method
    try:
        resp = urllib_request.urlopen(req, timeout=15)
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}
    except urllib_error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        raise


def _board_meta(board):
    location = getattr(board, "location", None)
    if isinstance(location, dict):
        return dict(location)
    return {}


def _set_board_meta(request, board_id, meta):
    _http_json(
        request,
        "PATCH",
        "%s/api/v2/devices/%s" % (_service_url("device"), board_id),
        {"metadata": meta},
    )


def _board_plugin_state(request, board_id):
    board = board_get(request, board_id, None)
    return _board_meta(board).get("plugins_state", [])


def _update_board_plugin_state(request, board_id, plugins_state):
    board = board_get(request, board_id, None)
    meta = _board_meta(board)
    meta["plugins_state"] = plugins_state
    _set_board_meta(request, board_id, meta)


def _board_services_state(request, board_id):
    board = board_get(request, board_id, None)
    return _board_meta(board).get("enabled_services", [])


def _update_board_services_state(request, board_id, enabled_services):
    board = board_get(request, board_id, None)
    meta = _board_meta(board)
    meta["enabled_services"] = enabled_services
    _set_board_meta(request, board_id, meta)


def _as_board(row):
    meta = row.get("metadata", {}) or {}
    return S4TObj({
        "uuid": row.get("id"),
        "id": row.get("id"),
        "name": row.get("name", "unknown-board"),
        "type": row.get("device_type", "gateway"),
        "status": row.get("status", "offline"),
        "lr_version": row.get("lr_version", "n/a"),
        "fleet": row.get("fleet", meta.get("fleet")),
        "fleet_name": row.get("fleet_name"),
        "mobile": row.get("mobile", meta.get("mobile", False)),
        "code": row.get("code", meta.get("code", "n/a")),
        "location": meta.get("location", {}),
        "owner": row.get("owner", "nexora"),
        "services": row.get("services", []),
        "plugins": row.get("plugins", []),
        "webservices": row.get("webservices", []),
    })


def _as_plugin(row):
    state = _load_state()
    meta = state.get("plugin_meta", {}).get(row.get("id"), {})
    return S4TObj({
        "uuid": row.get("id"),
        "id": row.get("id"),
        "name": row.get("name", "plugin"),
        "version": row.get("version", "0.1.0"),
        "owner": meta.get("owner", row.get("owner", "nexora")),
        "public": bool(meta.get("public", row.get("public", False))),
        "callable": bool(meta.get("callable", row.get("callable", False))),
        "code": meta.get("code", row.get("code", "")),
    })


def _as_service(row):
    return S4TObj({
        "uuid": row.get("id", row.get("uuid", "")),
        "id": row.get("id", row.get("uuid", "")),
        "name": row.get("name", "service"),
        "port": row.get("port", 0),
        "protocol": row.get("protocol", "TCP"),
        "owner": row.get("owner", "nexora"),
    })


def _as_port(row):
    return S4TObj({
        "uuid": row.get("id"),
        "id": row.get("id"),
        "name": row.get("id"),
        "board_uuid": row.get("device_id"),
        "network_id": row.get("network_id"),
        "ip": row.get("network_id", "n/a"),
        "status": row.get("status", "created"),
    })


def _as_fleet(row):
    return S4TObj({
        "uuid": row.get("id"),
        "id": row.get("id"),
        "name": row.get("name", "fleet"),
        "description": row.get("description", ""),
        "owner": row.get("owner", "nexora"),
    })


def _as_webservice(row):
    return S4TObj({
        "uuid": row.get("id"),
        "id": row.get("id"),
        "name": row.get("name", "webservice"),
        "board_uuid": row.get("device_id"),
        "port": row.get("port", 0),
        "http_port": row.get("port", 0),
        "https_port": row.get("port", 0),
        "status": row.get("status", "enabled"),
    })


@memoized
def nexoraclient(request):
    # Kept for compatibility with callers; not used in this adapter.
    return None


# BOARD MANAGEMENT

def board_list(request, status=None, detail=None, project=None):
    url = "%s/api/v2/devices" % _service_url("device")
    if status:
        url = "%s?status=%s" % (url, status)
    data = _http_json(request, "GET", url)
    return [_as_board(x) for x in data.get("items", [])]


def board_get(request, board_id, fields):
    row = _http_json(request, "GET", "%s/api/v2/devices/%s" % (_service_url("device"), board_id))
    return _as_board(row)


def board_create(request, code, mobile, location, type, name):
    payload = {
        "name": name,
        "device_type": type,
        "metadata": {"code": code, "mobile": mobile, "location": location},
    }
    _http_json(request, "POST", "%s/api/v2/devices" % _service_url("device"), payload)


def board_update(request, board_id, patch):
    current = board_get(request, board_id, None)
    metadata = _board_meta(current)
    if "fleet" in patch:
        metadata["fleet"] = patch.get("fleet")
    if "mobile" in patch:
        metadata["mobile"] = patch.get("mobile")
    if "location" in patch and patch.get("location") is not None:
        metadata["location"] = patch.get("location")
    payload = {"name": patch.get("name", current.name), "metadata": metadata}
    _http_json(request, "PATCH", "%s/api/v2/devices/%s" % (_service_url("device"), board_id), payload)


def board_delete(request, board_id):
    _http_json(request, "DELETE", "%s/api/v2/devices/%s" % (_service_url("device"), board_id))


# PLUGIN MANAGEMENT

def plugin_list(request, detail=None, project=None, with_public=False, all_plugins=False):
    data = _http_json(request, "GET", "%s/api/v2/plugins" % _service_url("plugin"))
    return [_as_plugin(x) for x in data.get("items", [])]


def plugin_get(request, plugin_id, fields):
    return _as_plugin(_http_json(request, "GET", "%s/api/v2/plugins/%s" % (_service_url("plugin"), plugin_id)))


def plugin_create(request, name, public, callable, code, parameters):
    payload = {"name": name, "version": "0.1.0", "public": public, "callable": callable, "code": code, "parameters": parameters}
    created = _http_json(request, "POST", "%s/api/v2/plugins" % _service_url("plugin"), payload)
    state = _load_state()
    state["plugin_meta"][created["id"]] = {
        "owner": os.getenv("S4T_USER_ID", "nexora"),
        "public": bool(public),
        "callable": bool(callable),
        "code": code,
        "parameters": parameters or {},
    }
    _save_state(state)


def plugin_update(request, plugin_id, patch):
    payload = {"name": patch.get("name")}
    _http_json(request, "PATCH", "%s/api/v2/plugins/%s" % (_service_url("plugin"), plugin_id), payload)
    state = _load_state()
    meta = state.get("plugin_meta", {}).get(plugin_id, {})
    for key in ("public", "callable", "code"):
        if key in patch:
            meta[key] = patch.get(key)
    state["plugin_meta"][plugin_id] = meta
    _save_state(state)


def plugin_delete(request, plugin_id):
    _http_json(request, "DELETE", "%s/api/v2/plugins/%s" % (_service_url("plugin"), plugin_id))
    state = _load_state()
    state.get("plugin_meta", {}).pop(plugin_id, None)
    _save_state(state)


# PLUGIN ON BOARD

def plugin_inject(request, board_id, plugin_id, onboot):
    plugins = _board_plugin_state(request, board_id)
    found = False
    for item in plugins:
        if item.get("plugin_id") == plugin_id:
            item["onboot"] = bool(onboot)
            item["status"] = "injected"
            found = True
            break
    if not found:
        plugins.append({
            "plugin_id": plugin_id,
            "onboot": bool(onboot),
            "status": "injected",
            "last_action": "PluginInject",
        })
    _update_board_plugin_state(request, board_id, plugins)
    return "plugin %s injected on board %s" % (plugin_id, board_id)


def plugin_action(request, board_id, plugin_id, action, params={}):
    execution = _http_json(
        request,
        "POST",
        "%s/api/v2/executions" % _service_url("execution"),
        {
            "device_id": board_id,
            "command": "plugin:%s:%s:%s" % (action, plugin_id, json.dumps(params or {})),
        },
    )
    _http_json(
        request,
        "POST",
        "%s/api/v2/executions/%s/dispatch" % (_service_url("execution"), execution["id"]),
        {},
    )
    plugins = _board_plugin_state(request, board_id)
    for item in plugins:
        if item.get("plugin_id") == plugin_id:
            item["status"] = "running"
            item["last_action"] = action
            item["last_execution_id"] = execution["id"]
    _update_board_plugin_state(request, board_id, plugins)
    return "plugin action %s dispatched on board %s (execution %s)" % (action, board_id, execution["id"])


def plugin_remove(request, board_id, plugin_id):
    plugins = [p for p in _board_plugin_state(request, board_id) if p.get("plugin_id") != plugin_id]
    _update_board_plugin_state(request, board_id, plugins)
    return "plugin %s removed from board %s" % (plugin_id, board_id)


def plugins_on_board(request, board_id):
    state = _load_state()
    plugins = _board_plugin_state(request, board_id)
    plugin_index = {p.id: p for p in plugin_list(request)}
    rows = []
    for item in plugins:
        pid = item.get("plugin_id")
        base = plugin_index.get(pid)
        rows.append(S4TObj({
            "uuid": pid,
            "id": pid,
            "name": getattr(base, "name", pid),
            "version": getattr(base, "version", "0.1.0"),
            "status": item.get("status", "injected"),
            "onboot": item.get("onboot", False),
            "public": bool(state.get("plugin_meta", {}).get(pid, {}).get("public", False)),
            "callable": bool(state.get("plugin_meta", {}).get(pid, {}).get("callable", False)),
        }))
    return rows


# SERVICE MANAGEMENT

def service_list(request, detail=None):
    state = _load_state()
    items = []
    for sid, svc in state.get("services", {}).items():
        items.append(_as_service({
            "id": sid,
            "name": svc.get("name"),
            "port": svc.get("port", 0),
            "protocol": svc.get("protocol", "TCP"),
            "owner": svc.get("owner", "nexora"),
        }))
    return items


def service_get(request, service_id, fields):
    state = _load_state()
    svc = state.get("services", {}).get(service_id)
    if not svc:
        return _as_service({"id": service_id, "name": "service", "port": 0, "protocol": "TCP"})
    return _as_service({
        "id": service_id,
        "name": svc.get("name"),
        "port": svc.get("port", 0),
        "protocol": svc.get("protocol", "TCP"),
        "owner": svc.get("owner", "nexora"),
    })


def service_create(request, name, port, protocol):
    state = _load_state()
    service_id = os.urandom(16).hex()
    state["services"][service_id] = {
        "name": name,
        "port": int(port),
        "protocol": protocol,
        "owner": os.getenv("S4T_USER_ID", "nexora"),
    }
    _save_state(state)
    return "service %s created" % name


def service_update(request, service_id, patch):
    state = _load_state()
    current = state.get("services", {}).get(service_id, {})
    current["name"] = patch.get("name", current.get("name", "service"))
    current["port"] = patch.get("port", current.get("port", 0))
    current["protocol"] = patch.get("protocol", current.get("protocol", "TCP"))
    state["services"][service_id] = current
    _save_state(state)
    return "service %s updated" % service_id


def service_delete(request, service_id):
    state = _load_state()
    state.get("services", {}).pop(service_id, None)
    _save_state(state)
    return "service %s deleted" % service_id


def services_on_board(request, board_id, detail=False):
    enabled = _board_services_state(request, board_id)
    by_id = {s.id: s for s in service_list(request)}
    return [by_id[sid] for sid in enabled if sid in by_id]


def service_action(request, board_id, service_id, action):
    enabled = _board_services_state(request, board_id)
    if action == "ServiceEnable":
        if service_id not in enabled:
            enabled.append(service_id)
    elif action == "ServiceDisable":
        enabled = [sid for sid in enabled if sid != service_id]
    elif action == "ServiceRestore":
        enabled = list(_load_state().get("services", {}).keys())
    _update_board_services_state(request, board_id, enabled)
    execution = _http_json(
        request,
        "POST",
        "%s/api/v2/executions" % _service_url("execution"),
        {"device_id": board_id, "command": "service:%s:%s" % (action, service_id)},
    )
    _http_json(
        request,
        "POST",
        "%s/api/v2/executions/%s/dispatch" % (_service_url("execution"), execution["id"]),
        {},
    )
    return "service action %s dispatched on board %s (execution %s)" % (action, board_id, execution["id"])


def restore_services(request, board_id):
    return service_action(request, board_id, "", "ServiceRestore")


# PORTS MANAGEMENT

def port_list(request, board_id):
    data = _http_json(request, "GET", "%s/api/v2/ports" % _service_url("network"))
    ports = [_as_port(x) for x in data.get("items", [])]
    return [p for p in ports if p.board_uuid == board_id]


def attach_port(request, board_id, network_id, subnet_id):
    payload = {"device_id": board_id, "network_id": network_id}
    return _as_port(_http_json(request, "POST", "%s/api/v2/ports" % _service_url("network"), payload))


def detach_port(request, board_id, port_id):
    _http_json(request, "DELETE", "%s/api/v2/ports/%s" % (_service_url("network"), port_id))


# FLEETS MANAGEMENT

def fleet_list(request, detail=None):
    data = _http_json(request, "GET", "%s/api/v2/fleets" % _service_url("fleet"))
    return [_as_fleet(x) for x in data.get("items", [])]


def fleet_get(request, fleet_id, fields):
    return _as_fleet(_http_json(request, "GET", "%s/api/v2/fleets/%s" % (_service_url("fleet"), fleet_id)))


def fleet_create(request, name, description):
    _http_json(request, "POST", "%s/api/v2/fleets" % _service_url("fleet"), {"name": name, "description": description})


def fleet_delete(request, fleet_id):
    _http_json(request, "DELETE", "%s/api/v2/fleets/%s" % (_service_url("fleet"), fleet_id))


def fleet_update(request, fleet_id, patch):
    _http_json(request, "PATCH", "%s/api/v2/fleets/%s" % (_service_url("fleet"), fleet_id), patch)


def fleet_get_boards(request, fleet_id):
    boards = board_list(request)
    result = []
    for b in boards:
        if str(getattr(b, "fleet", "")) == str(fleet_id):
            result.append(b)
    return result


# WEBSERVICES MANAGEMENT

def webservice_list(request, detail=None):
    data = _http_json(request, "GET", "%s/api/v2/webservices" % _service_url("webservice"))
    return [_as_webservice(x) for x in data.get("items", [])]


def webservice_enabled_list(request):
    boards = board_list(request)
    ws_list = webservice_list(request)
    by_board = {}
    for ws in ws_list:
        by_board.setdefault(ws.board_uuid, []).append(ws)

    result = []
    for board in boards:
        board_ws = by_board.get(board.uuid, [])
        if board_ws:
            gateway_cfg = _board_meta(board).get("webservice_gateway", {})
            result.append(S4TObj({
                "board_uuid": board.uuid,
                "name": board.name,
                "http_port": board_ws[0].http_port,
                "https_port": board_ws[0].https_port,
                "dns": gateway_cfg.get("dns", os.getenv("S4T_DNS_DOMAIN", "local")),
                "zone": gateway_cfg.get("zone", os.getenv("S4T_DNS_ZONE", "nexora")),
                "webservices": [w._info for w in board_ws],
            }))
    return result


def webservice_get_enabled_info(request, board_id, detail=None):
    for ws in webservice_enabled_list(request):
        if ws.board_uuid == board_id:
            return ws
    return S4TObj({
        "board_uuid": board_id,
        "dns": os.getenv("S4T_DNS_DOMAIN", "local"),
        "zone": os.getenv("S4T_DNS_ZONE", "nexora"),
    })


def webservices_on_board(request, board_id, fields=None):
    ws = [w for w in webservice_list(request) if w.board_uuid == board_id]
    return [{"name": x.name, "port": x.port, "uuid": x.uuid} for x in ws]


def webservice_get(request, webservice_id, fields):
    return _as_webservice(_http_json(request, "GET", "%s/api/v2/webservices/%s" % (_service_url("webservice"), webservice_id)))


def webservice_expose(request, board_id, name, port, secure):
    payload = {"device_id": board_id, "port": port, "name": name, "secure": secure}
    return _as_webservice(_http_json(request, "POST", "%s/api/v2/webservices" % _service_url("webservice"), payload))


def webservice_unexpose(request, webservice_id):
    _http_json(request, "DELETE", "%s/api/v2/webservices/%s" % (_service_url("webservice"), webservice_id))


def webservice_enable(request, board, dns, zone, email):
    b = board_get(request, board, None)
    meta = _board_meta(b)
    meta["webservice_gateway"] = {"enabled": True, "dns": dns, "zone": zone, "email": email}
    _set_board_meta(request, board, meta)
    return "webservices enabled for board %s" % board


def webservice_disable(request, board):
    b = board_get(request, board, None)
    meta = _board_meta(b)
    meta["webservice_gateway"] = {"enabled": False}
    _set_board_meta(request, board, meta)
    return "webservices disabled for board %s" % board


def boards_no_webservice(request):
    enabled = {x.board_uuid for x in webservice_enabled_list(request)}
    missing = []
    for b in board_list(request):
        if b.uuid not in enabled:
            missing.append((b.uuid, _(b.name)))
    return missing
