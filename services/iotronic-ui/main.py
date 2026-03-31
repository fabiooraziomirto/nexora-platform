import os
from typing import Any

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

APP_TITLE = "Stack4Things UI (IoTronic-compatible)"

SERVICE_URLS = {
    "device": os.getenv("S4T_DEVICE_URL", "http://device-service:8000"),
    "plugin": os.getenv("S4T_PLUGIN_URL", "http://plugin-service:8000"),
    "execution": os.getenv("S4T_EXECUTION_URL", "http://execution-service:8000"),
    "network": os.getenv("S4T_NETWORK_URL", "http://network-service:8000"),
    "dns": os.getenv("S4T_DNS_URL", "http://dns-service:8000"),
    "webservice": os.getenv("S4T_WEBSERVICE_URL", "http://webservice-service:8000"),
    "fleet": os.getenv("S4T_FLEET_URL", "http://fleet-service:8000"),
}

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "stack4things")
DEFAULT_TOKEN = os.getenv("S4T_AUTH_TOKEN", "")
TENANT_ID = os.getenv("S4T_TENANT_ID", "")

app = FastAPI(title=APP_TITLE, version="0.1.0")
templates = Jinja2Templates(directory="templates")


def _headers(token: str) -> dict[str, str]:
    h = {"Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if TENANT_ID:
        h["X-Tenant-Id"] = TENANT_ID
    return h


async def _safe_get(url: str, token: str) -> tuple[bool, Any]:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url, headers=_headers(token))
        if r.status_code >= 400:
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        return True, r.json()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "iotronic-ui"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token = request.cookies.get("s4t_token", DEFAULT_TOKEN)
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    targets = {
        "devices": f"{SERVICE_URLS['device']}/api/v2/devices",
        "plugins": f"{SERVICE_URLS['plugin']}/api/v2/plugins",
        "executions": f"{SERVICE_URLS['execution']}/api/v2/executions",
        "ports": f"{SERVICE_URLS['network']}/api/v2/ports",
        "dns": f"{SERVICE_URLS['dns']}/api/v2/dns/records",
        "webservices": f"{SERVICE_URLS['webservice']}/api/v2/webservices",
        "fleets": f"{SERVICE_URLS['fleet']}/api/v2/fleets",
    }

    data: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for k, url in targets.items():
        ok, payload = await _safe_get(url, token)
        if ok:
            data[k] = payload
        else:
            data[k] = {"items": [], "total": 0}
            errors[k] = str(payload)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "title": APP_TITLE,
            "keycloak_url": KEYCLOAK_URL,
            "realm": KEYCLOAK_REALM,
            "tenant_id": TENANT_ID,
            "services": SERVICE_URLS,
            "data": data,
            "errors": errors,
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": APP_TITLE,
            "keycloak_url": KEYCLOAK_URL,
            "realm": KEYCLOAK_REALM,
            "default_token": DEFAULT_TOKEN,
        },
    )


@app.post("/login")
async def login(token: str = Form(...)):
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie("s4t_token", token, httponly=True, samesite="lax")
    return resp


@app.post("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("s4t_token")
    return resp
