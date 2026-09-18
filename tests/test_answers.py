"""Direct answers must bypass article retrieval; all tests run offline."""
import pytest
from astro_search.core import AstroSearch

NOW = "2026-09-17T12:00:00Z"


def offline_engine(monkeypatch):
    engine = AstroSearch()
    def forbidden(*args, **kwargs):
        pytest.fail("Direct local answers must not fan out to news or APIs")
    monkeypatch.setattr(engine, "_fanout", forbidden)
    return engine


def test_moon_distance_returns_direct_answer(monkeypatch):
    pytest.importorskip("ephem")
    out = offline_engine(monkeypatch).search("how far is moon from the earth", now_utc=NOW)
    assert out["answer_status"] == "answered"
    answer = out["answer"]
    assert answer["property"] == "distance"
    assert answer["unit"] == "km"
    assert 350000 < answer["value"] < 410000
    assert answer["method"] == "computed"
    assert answer["as_of"] == NOW
    assert "center" in answer["text"]


def test_celestial_events_in_scope(monkeypatch):
    out = offline_engine(monkeypatch).search(
        "what celestial events is happening this month?", now_utc=NOW)
    assert out["interpretation"]["scope"] == "in_scope"
    assert out["answer_status"] == "answered"
    assert out["answer"]["property"] == "event_dates"
    assert out["answer"]["value"]
    assert all(row["event_date"].startswith("2026-09") for row in out["results"])


def test_next_full_moon_outside_month(monkeypatch):
    out = offline_engine(monkeypatch).search(
        "when is the next full moon happening this month", now_utc="2026-09-30T12:00:00Z")
    assert out["answer_status"] == "answered"
    assert out["answer"]["value"].startswith("2026-10")
    assert out["answer"]["outside_requested_window"] is True


def test_full_moon_this_month(monkeypatch):
    out = offline_engine(monkeypatch).search(
        "when is the next full moon happening this month", now_utc=NOW)
    assert out["answer"]["value"].startswith("2026-09")
    assert out["answer"]["outside_requested_window"] is False


@pytest.mark.parametrize("query", ["celestial events this month", "astronomical events this month", "what is happening in the sky this month"])
def test_event_paraphrases_and_truncation(monkeypatch, query):
    out = offline_engine(monkeypatch).search(query, now_utc=NOW, max_results=1)
    assert out["count"] == 1
    assert len(out["answer"]["value"]) > out["count"]
    assert out["coverage"] == "partial"


@pytest.mark.parametrize("query", ["average distance moon from earth", "moon distance from earth and Venus", "moon distance from earth tomorrow"])
def test_distance_constraints_not_ignored(monkeypatch, query):
    out = offline_engine(monkeypatch).search(query, now_utc=NOW)
    assert out["answer_status"] == "needs_clarification"
    assert out["answer"] is None


def test_missing_ephem_does_not_fall_back_to_news(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "ephem", None)
    out = offline_engine(monkeypatch).search("moon distance from earth", now_utc=NOW)
    assert out["answer"] is None
    assert "PyEphem" in out["markdown"]


def test_calendar_coverage_boundary(monkeypatch):
    out = offline_engine(monkeypatch).search("celestial events this month", now_utc="2028-01-01T00:00:00Z")
    assert out["answer"] is None
    assert out["answer_status"] == "needs_clarification"


def test_calendar_uses_local_month(monkeypatch):
    out = offline_engine(monkeypatch).search("celestial events this month", now_utc="2026-09-30T23:30:00Z", tz="Asia/Kolkata")
    assert out["answer"]["window"]["start"] == "2026-10-01"
    assert all(row["extra"]["local_display"].startswith("2026-10") for row in out["results"])


def test_launch_date_answer_and_citation(monkeypatch):
    engine = AstroSearch()
    engine._sources = []
    text = "James Webb Space Telescope was launched on December 25, 2021."
    row = {"title": "JWST", "summary": text, "url": "https://science.nasa.gov/fixture",
           "extra": {"document_text": text, "document_fetch_ok": True, "retrieved_at": NOW}}
    monkeypatch.setattr(engine, "_fanout", lambda *a, **kw: ([row], []))
    out = engine.search("when was James Webb telescope launched", now_utc=NOW)
    assert out["answer"]["value"] == "2021-12-25"
    assert out["answer"]["method"] == "primary_source"
    assert out["answer"]["citation"] == row["url"]


@pytest.mark.parametrize("statement", [
    "Nancy Grace Roman Space Telescope is scheduled to launch on May 20, 2027.",
    "Nancy Grace Roman Space Telescope was not launched on May 20, 2025.",
    "Nancy Grace Roman Space Telescope was launched on May 20, 2027.",
    "Nancy Grace Roman Space Telescope was launched on February 30, 2025.",
])
def test_roman_never_invents_completed_launch(monkeypatch, statement):
    engine = AstroSearch()
    engine._sources = []
    row = {"title": "Roman", "summary": statement, "url": "https://science.nasa.gov/fixture",
           "extra": {"document_text": statement, "document_fetch_ok": True, "retrieved_at": NOW}}
    monkeypatch.setattr(engine, "_fanout", lambda *a, **kw: ([row], []))
    out = engine.search("when was nancy grace roman telescope launched?", now_utc=NOW)
    assert out["answer"] is None
    assert out["answer_status"] == "not_found"

