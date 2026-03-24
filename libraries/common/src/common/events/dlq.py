from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeadLetterQueue:
    topic: str
    failed_events: list[dict[str, Any]] = field(default_factory=list)

    def push(self, event: dict[str, Any], reason: str) -> None:
        payload = dict(event)
        payload["_dlq_reason"] = reason
        self.failed_events.append(payload)
