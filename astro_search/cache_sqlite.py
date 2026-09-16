"""SQLite persistent cache (stdlib only). Falls back to no-op if unwritable.

TTL policy: news/space_weather 15 min, events/papers 24h. Caller passes ttl_seconds.
Path: $ASTRO_CACHE_PATH or ~/.astro_cache.db
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
from pathlib import Path


def _db_path() -> Path:
    override = os.environ.get("ASTRO_CACHE_PATH")
    if override:
        return Path(override)
    return Path.home() / ".astro_cache.db"


class SQLiteCache:
    def __init__(self, path: str | None = None):
        self.path = Path(path) if path else _db_path()
        self._ok = True
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(str(self.path))
            con.execute(
                "CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, ts REAL, v TEXT)"
            )
            con.commit()
            con.close()
        except Exception:
            self._ok = False

    def get(self, key: str, ttl_seconds: int) -> dict | None:
        if not self._ok:
            return None
        try:
            con = sqlite3.connect(str(self.path))
            row = con.execute("SELECT ts, v FROM cache WHERE k=?", (key,)).fetchone()
            con.close()
            if not row:
                return None
            ts, v = row
            if time.time() - ts > ttl_seconds:
                return None
            return json.loads(v)
        except Exception:
            return None

    def set(self, key: str, value: dict) -> None:
        if not self._ok:
            return None
        try:
            con = sqlite3.connect(str(self.path))
            con.execute(
                "REPLACE INTO cache (k, ts, v) VALUES (?,?,?)",
                (key, time.time(), json.dumps(value, ensure_ascii=False)),
            )
            con.commit()
            con.close()
        except Exception:
            pass
