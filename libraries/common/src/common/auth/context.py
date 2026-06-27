from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from common.auth.oidc import OIDCVerifier


READONLY_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_PATHS = {"/health", "/ready", "/metrics"}


@dataclass(frozen=True)
class AuthSettings:
    auth_enabled: bool = True
    auth_dev_bypass_enabled: bool = False
    auth_dev_token: str = "dev-token"
    environment: str = "development"
    keycloak_url: str = "http://keycloak:8080"
    keycloak_realm: str = "nxr"
    keycloak_jwks_url: str | None = None
    platform_admin_role: str = "platform-admin"
    tenant_admin_role: str = "tenant-admin"
    operator_role: str = "operator"
    viewer_role: str = "viewer"

    @property
    def issuer(self) -> str:
        return f"{self.keycloak_url.rstrip('/')}/realms/{self.keycloak_realm}"

    @property
    def jwks_url(self) -> str:
        return self.keycloak_jwks_url or f"{self.issuer}/protocol/openid-connect/certs"


@dataclass
class CurrentUser:
    user_id: str
    tenant_id: str
    roles: list[str] = field(default_factory=list)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    @property
    def is_authenticated(self) -> bool:
        return bool(self.user_id)

    def is_platform_admin(self, settings: AuthSettings) -> bool:
        return self.has_role(settings.platform_admin_role)

    def is_tenant_admin(self, settings: AuthSettings) -> bool:
        return self.is_platform_admin(settings) or self.has_role(settings.tenant_admin_role)

    def can_write(self, settings: AuthSettings) -> bool:
        return (
            self.is_platform_admin(settings)
            or self.has_role(settings.tenant_admin_role)
            or self.has_role(settings.operator_role)
        )


def auth_settings_from_env(prefix: str | None = None) -> AuthSettings:
    def env(name: str, default: str) -> str:
        if prefix:
            return os.getenv(f"{prefix}_{name}", os.getenv(name, default))
        return os.getenv(name, default)

    return AuthSettings(
        auth_enabled=env("AUTH_ENABLED", "true").lower() == "true",
        auth_dev_bypass_enabled=env("AUTH_DEV_BYPASS_ENABLED", "false").lower() == "true",
        auth_dev_token=env("AUTH_DEV_TOKEN", "dev-token"),
        environment=env("ENVIRONMENT", "development"),
        keycloak_url=env("KEYCLOAK_URL", "http://keycloak:8080"),
        keycloak_realm=env("KEYCLOAK_REALM", "nxr"),
        keycloak_jwks_url=env("KEYCLOAK_JWKS_URL", "") or None,
        platform_admin_role=env("AUTH_PLATFORM_ADMIN_ROLE", "platform-admin"),
        tenant_admin_role=env("AUTH_TENANT_ADMIN_ROLE", "tenant-admin"),
        operator_role=env("AUTH_OPERATOR_ROLE", "operator"),
        viewer_role=env("AUTH_VIEWER_ROLE", "viewer"),
    )


class RequestAuthenticator:
    def __init__(self, settings: AuthSettings | None = None):
        self.settings = settings or auth_settings_from_env()
        self._verifier: OIDCVerifier | None = None

    def _verifier_for_settings(self) -> OIDCVerifier:
        if self._verifier is None:
            self._verifier = OIDCVerifier(self.settings.jwks_url, issuer=self.settings.issuer)
        return self._verifier

    def user_from_claims(self, raw: dict[str, Any]) -> CurrentUser:
        groups = raw.get("groups") or []
        roles = raw.get("realm_access", {}).get("roles") or []
        tenant_id = groups[0].lstrip("/") if groups else "global"
        return CurrentUser(user_id=str(raw.get("sub", "")), tenant_id=tenant_id, roles=list(roles))

    def dev_user(self) -> CurrentUser:
        return CurrentUser(
            user_id="dev-user",
            tenant_id="dev",
            roles=[
                self.settings.platform_admin_role,
                self.settings.tenant_admin_role,
                self.settings.operator_role,
                self.settings.viewer_role,
            ],
        )

    def authenticate_header(self, authorization: str | None) -> CurrentUser | JSONResponse:
        if not self.settings.auth_enabled:
            return self.dev_user()
        if not authorization or not authorization.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "missing bearer token"})
        token = authorization.split(" ", 1)[1]
        if self.settings.auth_dev_bypass_enabled and token == self.settings.auth_dev_token:
            return self.dev_user()
        try:
            claims = self._verifier_for_settings().verify(token)
        except Exception as exc:
            return JSONResponse(status_code=401, content={"detail": f"invalid token: {exc}"})
        return self.user_from_claims(claims.raw)

    async def middleware(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        result = self.authenticate_header(request.headers.get("Authorization"))
        if isinstance(result, JSONResponse):
            return result
        request.state.current_user = result
        request.state.user_id = result.user_id
        request.state.tenant_id = result.tenant_id
        request.state.roles = result.roles
        request.state.is_operator = result.is_platform_admin(self.settings) or result.has_role(self.settings.operator_role)
        if self.settings.auth_enabled and request.method not in READONLY_METHODS and not result.can_write(self.settings):
            return JSONResponse(status_code=403, content={"detail": "write role required"})
        return await call_next(request)


def current_user_from_request(request: Request) -> CurrentUser:
    user = getattr(request.state, "current_user", None)
    if user:
        return user
    return CurrentUser(
        user_id=getattr(request.state, "user_id", "dev-user"),
        tenant_id=getattr(request.state, "tenant_id", "dev"),
        roles=getattr(request.state, "roles", []),
    )
