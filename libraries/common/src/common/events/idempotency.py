from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryIdempotencyStore:
    _keys: dict[str, Any] = field(default_factory=dict)

    def exists(self, key: str) -> bool:
        return key in self._keys

    def save(self, key: str, value: Any) -> None:
        self._keys[key] = value
