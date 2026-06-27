import json
from typing import Any


def json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def json_dump(value: Any) -> str:
    return json.dumps(value, default=str)
