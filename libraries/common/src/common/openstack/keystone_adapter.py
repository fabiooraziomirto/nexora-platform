from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class KeystoneTokenInfo:
    user_id: str
    project_id: str
    roles: list[str]
    raw: dict[str, Any]


class KeystoneAdapter:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def introspect_token(self, token: str) -> KeystoneTokenInfo:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/auth/tokens",
                headers={"X-Subject-Token": token},
            )
            response.raise_for_status()
            payload = response.json().get("token", {})
            user = payload.get("user", {})
            project = payload.get("project", {})
            roles = [r.get("name", "") for r in payload.get("roles", [])]
            return KeystoneTokenInfo(
                user_id=str(user.get("id", "")),
                project_id=str(project.get("id", "")),
                roles=[r for r in roles if r],
                raw=payload,
            )
