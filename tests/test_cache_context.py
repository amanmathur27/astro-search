import pytest
from astro_search import core
from astro_search.cache_sqlite import SQLiteCache


@pytest.mark.parametrize("persistent", [False, True])
def test_cache_isolates_explicit_time_overrides(monkeypatch, tmp_path, persistent):
    if persistent:
        monkeypatch.setattr(core, "SQLiteCache", lambda: SQLiteCache(str(tmp_path / "cache.db")))
    else:
        monkeypatch.setattr(core, "SQLiteCache", lambda: None)
    monkeypatch.setattr(core, "now_utc_iso", lambda: "2026-09-17T12:00:00Z")
    engine = core.AstroSearch()
    engine._sources = []  # No HTTP calls or ephemeris downloads.
    query = "explain gravity"
    first_time = "2024-01-01T12:00:00Z"
    second_time = "2025-01-01T12:00:00Z"

    def search(override=None):
        if persistent:
            engine.mem.clear()  # Exercise SQLite rather than the memory cache.
        return engine.search(query, now_utc=override)

    first = search(first_time)
    second = search(second_time)
    assert first["context"]["now_utc"] == first_time
    assert first["cached"] is False
    assert second["context"]["now_utc"] == second_time
    assert second["cached"] is False

    repeated = search(second_time)
    assert repeated["cached"] is True
    assert repeated["context"]["now_utc"] == second_time
    assert search(first_time)["cached"] is True

    live = search()
    assert live["cached"] is False
    assert live["context"]["now_utc"] == "2026-09-17T12:00:00Z"
    assert search()["cached"] is True
    assert search("")["cached"] is True


@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("parameter, first_value, second_value", [
    ("lat", 0.0, 28.6),
    ("lon", 0.0, 77.2),
    ("tz", "UTC", "Asia/Kolkata"),
    ("year", 2026, 2027),
])
def test_cache_isolates_observer_context(monkeypatch, tmp_path, persistent,
                                        parameter, first_value, second_value):
    if persistent:
        monkeypatch.setattr(core, "SQLiteCache", lambda: SQLiteCache(str(tmp_path / "cache.db")))
    else:
        monkeypatch.setattr(core, "SQLiteCache", lambda: None)
    engine = core.AstroSearch()
    engine._sources = []
    calls = []

    class ContextSource:
        name = "Context fixture"
        intents = ["concept_explanation"]

        def fetch(self, query, **kwargs):
            calls.append(kwargs.copy())
            return [{"title": "Gravity", "summary": "Observer context fixture",
                     "url": "https://example.com/gravity", "source": self.name,
                     "authority": 2, "freshness_h": None,
                     "extra": {"requested": {k: kwargs[k] for k in ("lat", "lon", "tz", "year")}}}]

    monkeypatch.setattr(engine, "_select", lambda *args, **kwargs: [ContextSource()])

    def search(value):
        if persistent:
            engine.mem.clear()
        context = {"lat": 0.0, "lon": 0.0, parameter: value}
        return engine.search("explain gravity", **context)

    first = search(first_value)
    second = search(second_value)
    assert first["cached"] is False
    assert second["cached"] is False
    assert first["results"][0]["extra"]["requested"][parameter] == first_value
    assert second["results"][0]["extra"]["requested"][parameter] == second_value
    assert search(second_value)["cached"] is True
    assert search(first_value)["cached"] is True
    assert len(calls) == 2


@pytest.mark.parametrize("persistent", [False, True])
def test_cache_ignores_legacy_keys(monkeypatch, tmp_path, persistent):
    import json

    if persistent:
        monkeypatch.setattr(core, "SQLiteCache", lambda: SQLiteCache(str(tmp_path / "cache.db")))
    else:
        monkeypatch.setattr(core, "SQLiteCache", lambda: None)
    engine = core.AstroSearch()
    engine._sources = []
    query = "explain gravity"
    legacy_key = (query, "all", 8, False, "")
    stale = {"cached": False, "legacy": True}
    if persistent:
        engine.disk.set(json.dumps(legacy_key), stale)
    else:
        engine.mem.set(legacy_key, stale)

    result = engine.search(query)
    assert "legacy" not in result
    assert result["cached"] is False

