"""Validation is applied before network/cache work at public boundaries."""
import json
import pytest
from astro_search import core, tools
from astro_search.timeparse import timezone_for
from astro_search.validation import observer


@pytest.mark.parametrize("kwargs", [
    {"lat": 0}, {"lon": 0}, {"lat": True, "lon": 0},
    {"lat": "28", "lon": 77}, {"lat": 91, "lon": 0},
    {"lat": 0, "lon": -181}, {"lat": float("nan"), "lon": 0},
    {"lat": 0, "lon": float("inf")}, {"tz": None}, {"tz": ""},
    {"tz": float("inf")}, {"tz": True}, {"year": True},
    {"year": "2026"}, {"year": 1899}, {"year": 2101},
])
def test_search_and_calendar_reject_invalid_context(kwargs):
    engine = core.AstroSearch()
    engine._sources = []
    for call in (lambda: engine.search("explain gravity", **kwargs),
                 lambda: engine.get_celestial_events(**kwargs)):
        with pytest.raises(ValueError):
            call()


@pytest.mark.parametrize("kwargs", [
    {"query": []}, {"query": "x" * 4001}, {"category": []},
    {"category": "invalid"}, {"trends": "false"}, {"topic": []},
    {"edition": {}}, {"edition": "India"},
])
def test_invalid_search_inputs(kwargs):
    with pytest.raises(ValueError):
        core.AstroSearch().search(**kwargs)


def test_coordinate_boundaries_and_fractional_zone():
    assert observer(-90, 180, 5.5) == (-90.0, 180.0)
    rows = [{"event_date_utc": "2026-01-01T00:00:00Z", "extra": {}}]
    core.AstroSearch()._apply_local_display(rows, 5.5)
    assert "05:30" in rows[0]["extra"]["local_display"]
    assert timezone_for(5.5).utcoffset(None).total_seconds() == 19800


def test_tools_preserve_validation(monkeypatch):
    engine = core.AstroSearch()
    engine._sources = []
    monkeypatch.setattr(tools, "_engine", engine)
    for name, args in (("astro_search", {"query": "gravity", "trends": "false"}),
                       ("astro_search", {"query": "gravity", "lat": 28}),
                       ("astro_events", {"year": 2026, "lon": 77}),
                       ("astro_events", {"year": True}), ("astro_search", [])):
        assert "error" in json.loads(tools.tool_handler(name, args))
    out = json.loads(tools.tool_handler("astro_search", {"query": "explain gravity", "max_results": "bad"}))
    assert out["json"]["count"] == 0
