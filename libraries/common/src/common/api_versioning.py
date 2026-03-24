from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class DeprecationPolicy:
    current_version: str
    sunset_date: date | None = None
    replacement_version: str | None = None


def build_deprecation_headers(policy: DeprecationPolicy) -> dict[str, str]:
    headers: dict[str, str] = {"x-api-version": policy.current_version}
    if policy.sunset_date:
        headers["sunset"] = policy.sunset_date.isoformat()
    if policy.replacement_version:
        headers["x-api-replacement-version"] = policy.replacement_version
    return headers
