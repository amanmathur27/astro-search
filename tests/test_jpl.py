"""Horizons request correctness, with no live service calls."""
from astro_search.sources import jpl


def test_horizons_window_and_no_default_body(monkeypatch):
    calls = []

    class Response:
        ok = False

    def get(url, **kwargs):
        calls.append((url, kwargs.get("params", {})))
        return Response()

    monkeypatch.setattr(jpl.requests, "get", get)
    source = jpl.JPLSource()
    source.fetch("Jupiter position", lat=28, lon=77, now_utc="2026-12-31T12:00:00Z")
    params = next(p for url, p in calls if "horizons.api" in url)
    assert params["START_TIME"] == "2026-12-31"
    assert params["STOP_TIME"] == "2027-01-01"
    assert params["STEP_SIZE"] == "1h"
    calls.clear()
    source.fetch("where is the object", lat=28, lon=77, now_utc="2026-12-31T12:00:00Z")
    assert not any("horizons.api" in url for url, _ in calls)
