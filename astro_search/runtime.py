"""Bounded shared source execution and per-engine source response caching.

Running HTTP calls cannot be forcibly cancelled. Admission is bounded separately
from worker count, so concurrent callers cannot build an unbounded work queue.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, RLock
from .cache import TTLCache


class BoundedExecutor:
    def __init__(self, workers=8, capacity=24):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="astro-source")
        self._slots = BoundedSemaphore(capacity)

    def submit(self, function, *args, **kwargs):
        if not self._slots.acquire(blocking=False):
            return None
        try:
            future = self._pool.submit(function, *args, **kwargs)
        except BaseException:
            self._slots.release()
            raise
        future.add_done_callback(lambda _: self._slots.release())
        return future

    def shutdown(self):
        self._pool.shutdown(wait=True, cancel_futures=True)


EXECUTOR = BoundedExecutor()


class SourceRuntime:
    def __init__(self):
        self.cache = TTLCache(ttl_minutes=1, max_entries=256)
        self._failures = {}
        self._lock = RLock()

    def _key_for(self, source):
        return getattr(source, "name", str(source))

    def fetch(self, source, query, **kwargs):
        deadline = kwargs.pop("_deadline", None)
        errors = kwargs.pop("_errors", None)
        if deadline is not None and time.monotonic() >= deadline:
            if errors is not None:
                errors.append({"source": source.name, "error": "deadline_exceeded"})
            return []
        # Include exact request context, including time. Never reuse live readings
        # for a different historical override or observer just to increase hit rate.
        key = (source, query, json.dumps(kwargs, sort_keys=True, default=str))
        cached = self.cache.get(key)
        if cached is not None:
            return cached["rows"]
        s_key = self._key_for(source)
        with self._lock:
            failures, retry_at = self._failures.get(s_key, (0, 0))
        if time.monotonic() < retry_at:
            if errors is not None:
                errors.append({"source": getattr(source, "name", str(source)), "error": "source_backoff"})
            return []
        local_errors = []
        try:
            rows = source.fetch(query, **kwargs, _errors=local_errors)
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise ValueError("Invalid source result shape")
        except Exception:
            self._failed(source, failures)
            raise
        if local_errors:
            if errors is not None:
                errors.extend(local_errors)
            self._failed(source, failures)
        else:
            with self._lock:
                self._failures.pop(s_key, None)
            self.cache.set(key, {"rows": rows})
        return rows

    def _failed(self, source, failures):
        s_key = self._key_for(source)
        with self._lock:
            self._failures[s_key] = (min(failures + 1, 6), time.monotonic() + min(60, 2 ** failures))
            while len(self._failures) > 256:
                self._failures.pop(next(iter(self._failures)))

    def circuit_status(self, source) -> dict:
        """Return circuit breaker status for a source (object or name string)."""
        s_key = self._key_for(source)
        with self._lock:
            failures, retry_at = self._failures.get(s_key, (0, 0))
        now = time.monotonic()
        return {
            "source": s_key,
            "failures": failures,
            "is_open": now < retry_at,
            "cooldown_remaining_sec": max(0.0, round(retry_at - now, 2)),
        }

    def reset_circuit(self, source=None):
        """Reset circuit breaker failure counts."""
        with self._lock:
            if source:
                self._failures.pop(self._key_for(source), None)
            else:
                self._failures.clear()

