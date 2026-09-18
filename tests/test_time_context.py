"""Offline regression coverage for request-time context."""
import pytest
import requests
from astro_search import core
from astro_search.timeparse import reference_time, resolve_dates, today_label


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected HTTP request")
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    monkeypatch.setattr(core, "SQLiteCache", lambda: None)


@pytest.mark.parametrize("query, instant, start, end", [
    ("this weekend", "2026-09-20T12:00:00Z", "2026-09-19", "2026-09-20"),
    ("this weekend", "2026-09-19T12:00:00Z", "2026-09-19", "2026-09-20"),
    ("next week", "2026-09-20T12:00:00Z", "2026-09-21", "2026-09-27"),
    ("next week", "2026-09-21T12:00:00Z", "2026-09-28", "2026-10-04"),
    ("this month", "2024-02-15T00:00:00Z", "2024-02-01", "2024-02-29"),
    ("tomorrow", "2026-12-31T12:00:00Z", "2027-01-01", "2027-01-01"),
    ("today", "2026-09-20T12:00:00Z", "2026-09-20", "2026-09-20"),
    ("events 2035", "2026-09-20T12:00:00Z", "2035-01-01", "2035-12-31"),
])
def test_date_windows(query, instant, start, end):
    result = resolve_dates(query, reference_time(instant))
    assert (result["date_min"], result["date_max"]) == (start, end)


@pytest.mark.parametrize("value", ["bad", "2026-09-20", "2026-09-20T12:00:00"])
def test_invalid_override_rejected(value):
    with pytest.raises(ValueError):
        reference_time(value)


def test_timezone_equivalence_and_civil_day():
    assert reference_time("2026-09-20T17:30:00+05:30") == reference_time("2026-09-20T12:00:00Z")
    assert today_label("2026-12-31T23:00:00Z", "Asia/Kolkata") == "Friday, 2027-01-01"
    assert resolve_dates("today", reference_time("2026-12-31T23:00:00Z"), "Asia/Kolkata")["date_min"] == "2027-01-01"


def test_search_source_context_and_freshness(monkeypatch):
    engine = core.AstroSearch()
    calls = []

    class Source:
        name = "Fixture"
        intents = ["concept_explanation"]

        def fetch(self, query, **kwargs):
            calls.append(kwargs)
            return [{"title": "Gravity", "summary": "Gravity reference", "url": "https://example.org/gravity",
                     "source": self.name, "published": "2024-01-01T00:00:00Z"}]

    engine._sources = []
    monkeypatch.setattr(engine, "_select", lambda *a, **k: [Source()])
    result = engine.search("explain gravity in 2035", now_utc="2024-01-01T12:00:00Z")
    assert calls[0]["year"] == 2035
    assert calls[0]["date_max"] == "2035-12-31"
    assert result["context"]["today"] == "Monday, 2024-01-01"
    assert "Monday, 2024-01-01" in result["markdown"]
    assert result["results"][0]["freshness_h"] == 12


def test_equivalent_overrides_share_cache():
    engine = core.AstroSearch()
    engine._sources = []
    engine.search("explain gravity", now_utc="2026-09-20T12:00:00Z")
    result = engine.search("explain gravity", now_utc="2026-09-20T17:30:00+05:30")
    assert result["cached"] is True


def test_empty_search_passes_calendar_context(monkeypatch):
    engine = core.AstroSearch()
    engine._sources = []
    calls = []
    monkeypatch.setattr(engine, "get_celestial_events", lambda **kw: calls.append(kw) or kw)
    result = engine.search("", now_utc="2026-12-31T23:00:00Z", tz="Asia/Kolkata")
    assert result["year"] == 2027
    assert result["now_utc"] == "2026-12-31T23:00:00Z"
    assert result["tz"] == "Asia/Kolkata"


def test_calendar_context_without_network():
    engine = core.AstroSearch()
    engine._sources = []
    result = engine.get_celestial_events(now_utc="2026-12-31T23:00:00Z", tz="Asia/Kolkata")
    assert result["query"] == "celestial events 2027"
    assert result["context"]["today"] == "Friday, 2027-01-01"
    assert "Friday, 2027-01-01" in result["markdown"]
