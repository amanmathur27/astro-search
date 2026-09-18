"""Cache contract tests: isolation, bounding, persistence."""
import sqlite3
from astro_search.cache import TTLCache
from astro_search.cache_sqlite import SQLiteCache


def test_memory_cache_isolates_values():
    cache = TTLCache(60)
    value = {"rows": [1, 2]}
    cache.set(("key",), value)
    value["rows"].append(3)
    first = cache.get(("key",))
    first["rows"].append(99)
    assert cache.get(("key",)) == {"rows": [1, 2]}


def test_memory_cache_evicts_oldest_beyond_cap():
    cache = TTLCache(60, max_entries=2)
    for k in ("a", "b", "c"):
        cache.set((k,), {"k": k})
    assert cache.get(("a",)) is None
    assert cache.get(("c",)) == {"k": "c"}


def test_disk_cache_bounded(tmp_path):
    path = tmp_path / "cache.db"
    cache = SQLiteCache(path)
    cache.MAX_ROWS = 5
    for i in range(10):
        cache.set(f"key-{i}", {"i": i})
    with sqlite3.connect(str(path)) as con:
        assert con.execute("SELECT COUNT(*) FROM cache").fetchone()[0] == 5
    assert cache.get("key-9", 60) == {"i": 9}
