from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class OutboxEvent:
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
    published: bool = False


def make_outbox_event(event_type: str, payload: dict[str, Any]) -> OutboxEvent:
    return OutboxEvent(
        event_type=event_type,
        payload=payload,
        created_at=datetime.now(timezone.utc),
        published=False,
    )
