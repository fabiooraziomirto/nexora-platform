import os
from typing import Any

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

APP_TITLE = "Nexora UI (legacy-compatible)"

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
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "nexora")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "nexora-ui")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
DEFAULT_TOKEN = os.getenv("S4T_AUTH_TOKEN", "")
TENANT_ID = os.getenv("S4T_TENANT_ID", "")
LOCAL_ADMIN_USER = os.getenv("S4T_UI_LOCAL_ADMIN_USER", "admin")
LOCAL_ADMIN_PASSWORD = os.getenv("S4T_UI_LOCAL_ADMIN_PASSWORD", "admin")
AUTH_DEV_BYPASS_ENABLED = os.getenv("AUTH_DEV_BYPASS_ENABLED", "false").lower() == "true"
AUTH_DEV_TOKEN = os.getenv("AUTH_DEV_TOKEN", "dev-token")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

app = FastAPI(title=APP_TITLE, version="0.1.0")
templates = Jinja2Templates(directory="templates")

import logging as _logging
_logger = _logging.getLogger("nexora-ui")


@app.on_event("startup")
async def startup() -> None:
    if AUTH_DEV_BYPASS_ENABLED:
        if ENVIRONMENT == "production":
            raise RuntimeError("AUTH_DEV_BYPASS_ENABLED=true is not allowed when ENVIRONMENT=production")
        _logger.warning("AUTH DEV BYPASS ENABLED — NOT FOR PRODUCTION")


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


async def _fetch_keycloak_token(username: str, password: str) -> tuple[bool, str]:
    candidate_realms = [KEYCLOAK_REALM]
    if KEYCLOAK_REALM != "master":
        candidate_realms.append("master")
    candidate_client_ids = [KEYCLOAK_CLIENT_ID]
    if KEYCLOAK_CLIENT_ID != "admin-cli":
        candidate_client_ids.append("admin-cli")

    async with httpx.AsyncClient(timeout=10) as client:
        for realm in candidate_realms:
            for client_id in candidate_client_ids:
                token_url = f"{KEYCLOAK_URL}/realms/{realm}/protocol/openid-connect/token"
                form = {
                    "grant_type": "password",
                    "client_id": client_id,
                    "username": username,
                    "password": password,
                }
                if KEYCLOAK_CLIENT_SECRET and client_id == KEYCLOAK_CLIENT_ID:
                    form["client_secret"] = KEYCLOAK_CLIENT_SECRET
                try:
                    resp = await client.post(
                        token_url,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        data=form,
                    )
                    if resp.status_code < 400:
                        access_token = resp.json().get("access_token", "")
                        if access_token:
                            return True, access_token
                except Exception:
                    continue
    return False, ""


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "nexora-ui"}


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
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "title": APP_TITLE,
            "keycloak_url": KEYCLOAK_URL,
            "realm": KEYCLOAK_REALM,
            "default_username": os.getenv("S4T_UI_DEFAULT_USERNAME", "admin"),
            "default_password": os.getenv("S4T_UI_DEFAULT_PASSWORD", "admin"),
            "error": error,
        },
    )


@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    ok, token = await _fetch_keycloak_token(username=username, password=password)
    # Local fallback: only active when AUTH_DEV_BYPASS_ENABLED=true (explicit opt-in).
    if not ok and AUTH_DEV_BYPASS_ENABLED and username == LOCAL_ADMIN_USER and password == LOCAL_ADMIN_PASSWORD:
        token = DEFAULT_TOKEN or AUTH_DEV_TOKEN
        ok = True
    if not ok:
        return RedirectResponse(url="/login?error=Credenziali+non+valide", status_code=302)
    resp = RedirectResponse(url="/", status_code=302)
    resp.set_cookie("s4t_token", token, httponly=True, samesite="lax")
    return resp


@app.post("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("s4t_token")
    return resp
