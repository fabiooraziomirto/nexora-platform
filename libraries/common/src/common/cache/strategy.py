from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CacheStrategy:
    mode: str = "read-through"
    default_ttl_seconds: int = 300
    invalidate_on_write: bool = True


DEFAULT_CACHE_STRATEGY = CacheStrategy()
