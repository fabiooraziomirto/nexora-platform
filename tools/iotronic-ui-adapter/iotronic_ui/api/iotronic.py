# -*- coding: utf-8 -*-
"""Stack4Things v2 adapter for legacy IoTronic Horizon panel.

This module replaces the original iotronicclient-based calls with direct HTTP
calls to Stack4Things v2 microservices.
"""

import json
import os
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


def _as_board(row):
    return S4TObj({
        "uuid": row.get("id"),
        "id": row.get("id"),
        "name": row.get("name", "unknown-board"),
        "type": row.get("device_type", "gateway"),
        "status": row.get("status", "offline"),
        "lr_version": row.get("lr_version", "n/a"),
        "fleet": row.get("fleet"),
        "fleet_name": row.get("fleet_name"),
        "mobile": row.get("mobile", False),
        "code": row.get("code", "n/a"),
        "location": row.get("metadata", {}).get("location", {}),
        "owner": row.get("owner", "stack4things"),
        "services": row.get("services", []),
        "plugins": row.get("plugins", []),
        "webservices": row.get("webservices", []),
    })


def _as_plugin(row):
    return S4TObj({
        "uuid": row.get("id"),
        "id": row.get("id"),
        "name": row.get("name", "plugin"),
        "version": row.get("version", "0.1.0"),
        "owner": row.get("owner", "stack4things"),
        "public": bool(row.get("public", False)),
        "callable": bool(row.get("callable", False)),
        "code": row.get("code", ""),
    })


def _as_service(row):
    return S4TObj({
        "uuid": row.get("id", row.get("uuid", "")),
        "id": row.get("id", row.get("uuid", "")),
        "name": row.get("name", "service"),
        "port": row.get("port", 0),
        "protocol": row.get("protocol", "TCP"),
        "owner": row.get("owner", "stack4things"),
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
        "owner": row.get("owner", "stack4things"),
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
def iotronicclient(request):
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
    payload = {
        "name": patch.get("name"),
        "metadata": {
            "fleet": patch.get("fleet"),
            "mobile": patch.get("mobile"),
            "location": patch.get("location"),
        },
    }
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
    _http_json(request, "POST", "%s/api/v2/plugins" % _service_url("plugin"), payload)


def plugin_update(request, plugin_id, patch):
    payload = {"name": patch.get("name")}
    _http_json(request, "PATCH", "%s/api/v2/plugins/%s" % (_service_url("plugin"), plugin_id), payload)


def plugin_delete(request, plugin_id):
    _http_json(request, "DELETE", "%s/api/v2/plugins/%s" % (_service_url("plugin"), plugin_id))


# PLUGIN ON BOARD (no native equivalent in v2 yet)

def plugin_inject(request, board_id, plugin_id, onboot):
    return "plugin %s injected on %s" % (plugin_id, board_id)


def plugin_action(request, board_id, plugin_id, action, params={}):
    return "plugin action %s executed on board %s" % (action, board_id)


def plugin_remove(request, board_id, plugin_id):
    return "plugin %s removed from board %s" % (plugin_id, board_id)


def plugins_on_board(request, board_id):
    return []


# SERVICE MANAGEMENT (legacy concept; mapped as empty catalog for now)

def service_list(request, detail=None):
    return []


def service_get(request, service_id, fields):
    return _as_service({"id": service_id, "name": "service", "port": 0, "protocol": "TCP"})


def service_create(request, name, port, protocol):
    return "service %s created" % name


def service_update(request, service_id, patch):
    return "service %s updated" % service_id


def service_delete(request, service_id):
    return "service %s deleted" % service_id


def services_on_board(request, board_id, detail=False):
    return []


def service_action(request, board_id, service_id, action):
    return "service action %s on board %s" % (action, board_id)


def restore_services(request, board_id):
    return "services restored on board %s" % board_id


# PORTS MANAGEMENT

def port_list(request, board_id):
    data = _http_json(request, "GET", "%s/api/v2/ports" % _service_url("network"))
    ports = [_as_port(x) for x in data.get("items", [])]
    return [p for p in ports if p.board_uuid == board_id] + [p for p in ports if p.board_uuid != board_id]


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
            result.append(S4TObj({
                "board_uuid": board.uuid,
                "name": board.name,
                "http_port": board_ws[0].http_port,
                "https_port": board_ws[0].https_port,
                "dns": os.getenv("S4T_DNS_DOMAIN", "local"),
                "zone": os.getenv("S4T_DNS_ZONE", "stack4things"),
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
        "zone": os.getenv("S4T_DNS_ZONE", "stack4things"),
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
    return "webservices enabled for board %s" % board


def webservice_disable(request, board):
    return "webservices disabled for board %s" % board


def boards_no_webservice(request):
    enabled = {x.board_uuid for x in webservice_enabled_list(request)}
    missing = []
    for b in board_list(request):
        if b.uuid not in enabled:
            missing.append((b.uuid, _(b.name)))
    return missing
