from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TenantContext:
    tenant_id: str
    quota_limit: int = 1000


def extract_tenant_id(headers: dict[str, str]) -> str:
    tenant_id = headers.get("x-tenant-id") or headers.get("X-Tenant-Id")
    if not tenant_id:
        raise ValueError("missing tenant header")
    return tenant_id
