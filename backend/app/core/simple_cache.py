"""A minimal in-process TTL cache used by read-heavy API routes.

Whether a cache instance is active is controlled explicitly via the
``enabled`` constructor flag (wired from Settings.route_cache_enabled),
never by runtime test-framework detection.
"""

import time
from collections.abc import Hashable
from typing import Any


class SimpleTTLCache:
    def __init__(self, ttl: float = 10.0, enabled: bool = True):
        self.ttl = ttl
        self.enabled = enabled
        self._cache: dict[Hashable, tuple[Any, float]] = {}

    def get(self, key: Hashable) -> Any | None:
        if not self.enabled:
            return None
        if key in self._cache:
            val, expire = self._cache[key]
            if time.time() < expire:
                return val
            del self._cache[key]
        return None

    def set(self, key: Hashable, val: Any) -> None:
        if not self.enabled:
            return
        self._cache[key] = (val, time.time() + self.ttl)

    def clear(self) -> None:
        self._cache.clear()
