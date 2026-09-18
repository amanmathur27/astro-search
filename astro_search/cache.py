"""15-min TTL in-memory cache (GitHub Actions safe, stdlib only)."""
from __future__ import annotations
import time
from copy import deepcopy
from threading import RLock


class TTLCache:
    def __init__(self, ttl_minutes: int = 15, max_entries: int = 1000):
        self._store: dict = {}
        self.ttl = ttl_minutes * 60
        self.max_entries = max(1, int(max_entries))
        self._lock = RLock()

    def _now(self) -> float:
        return time.monotonic()

    def get(self, key: tuple) -> dict | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            ts, value = item
            if self._now() - ts > self.ttl:
                self._store.pop(key, None)
                return None
            return deepcopy(value)

    def set(self, key: tuple, value: dict) -> None:
        with self._lock:
            now = self._now()
            for k in [k for k, (ts, _) in self._store.items() if now - ts > self.ttl]:
                self._store.pop(k, None)
            self._store.pop(key, None)
            self._store[key] = (now, deepcopy(value))
            while len(self._store) > self.max_entries:
                self._store.pop(next(iter(self._store)))

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
