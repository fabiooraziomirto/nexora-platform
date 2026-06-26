"""
FastAPI auth dependency for device-service.

Extracts CurrentUser from a Keycloak-issued JWT. In dev (AUTH_ENABLED=false)
any request with the AUTH_DEV_TOKEN value is accepted and treated as a
non-operator owner with tenant "dev".

Keycloak JWT claims used:
  sub               → user_id
  groups[0]         → tenant_id (first group, or "global" if absent)
  realm_access.roles → roles list
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Header, HTTPException, status

from device_service.core.config import settings

# Import OIDCVerifier lazily to avoid startup failure when Keycloak is unreachable
_verifier = None


def _get_verifier():
    global _verifier
    if _verifier is None:
        from common.auth.oidc import OIDCVerifier
        _verifier = OIDCVerifier(
            jwks_url=settings.KEYCLOAK_JWKS_URL,
            issuer=f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}",
        )
    return _verifier


@dataclass
class CurrentUser:
    user_id: str
    tenant_id: str
    roles: list[str] = field(default_factory=list)
    is_operator: bool = False


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> CurrentUser:
    """FastAPI dependency — resolves the authenticated caller from JWT Bearer token."""
    if not settings.AUTH_ENABLED:
        # Dev bypass: accept any request, treat as non-operator owner in "dev" tenant
        return CurrentUser(user_id="dev-user", tenant_id="dev", roles=[], is_operator=False)

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    # Dev token shortcut (AUTH_ENABLED=true but token == dev token)
    if settings.AUTH_DEV_BYPASS_ENABLED and authorization == f"Bearer {settings.AUTH_DEV_TOKEN}":
        return CurrentUser(user_id="dev-user", tenant_id="dev", roles=[], is_operator=False)

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header format")

    token = authorization.removeprefix("Bearer ")
    try:
        claims = _get_verifier().verify(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}") from exc

    raw = claims.raw
    roles: list[str] = raw.get("realm_access", {}).get("roles", [])
    groups: list[str] = raw.get("groups", [])
    tenant_id = groups[0].lstrip("/") if groups else "global"

    return CurrentUser(
        user_id=claims.sub,
        tenant_id=tenant_id,
        roles=roles,
        is_operator=settings.AUTH_OPERATOR_ROLE in roles,
    )


async def require_operator(user: CurrentUser) -> CurrentUser:
    """Raises 403 if the caller is not a platform operator."""
    if not user.is_operator:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform operator role required")
    return user
