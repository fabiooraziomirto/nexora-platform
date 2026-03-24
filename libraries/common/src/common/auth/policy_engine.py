from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str = ""


class PolicyEngine:
    """Simple centralized policy evaluator (RBAC/ABAC baseline)."""

    def __init__(self, write_role: str = "writer"):
        self.write_role = write_role

    def evaluate(self, method: str, roles: Iterable[str], resource: str) -> PolicyDecision:
        method = method.upper()
        if method in {"GET", "HEAD", "OPTIONS"}:
            return PolicyDecision(True, "read operation allowed")
        if self.write_role in set(roles):
            return PolicyDecision(True, f"role {self.write_role} granted for write")
        return PolicyDecision(False, f"missing role {self.write_role} for write on {resource}")
