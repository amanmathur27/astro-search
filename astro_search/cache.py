"""15-min TTL in-memory cache (GitHub Actions safe, stdlib only)."""
from __future__ import annotations
import time


class TTLCache:
    def __init__(self, ttl_minutes: int = 15):
        self._store: dict = {}
        self.ttl = ttl_minutes * 60

    def _now(self) -> float:
        return time.time()

    def get(self, key: tuple) -> dict | None:
        item = self._store.get(key)
        if not item:
            return None
        ts, value = item
        if self._now() - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: tuple, value: dict) -> None:
        self._store[key] = (self._now(), value)

    def clear(self) -> None:
        self._store.clear()
