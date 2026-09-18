"""Request-level regression tests for NASA date windows; no live HTTP."""
from datetime import date, timedelta

from astro_search.sources import nasa


class Response:
    ok = True

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def capture_requests(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs.get("params", {})))
        if "/neo/rest/v1/feed" in url:
            return Response({"near_earth_objects": {}})
        if "/DONKI/" in url:
            return Response([])
        return Response({})

    monkeypatch.setattr(nasa.requests, "get", get)
    return calls


def test_neows_seven_day_limit_and_complete_requested_window(monkeypatch):
    calls = capture_requests(monkeypatch)
    nasa.NASASource().fetch(
        "asteroid close approaches", date="2026-09-01", date_max="2026-09-30",
        now_utc="2026-09-17T12:00:00Z",
    )
    windows = [params for url, params in calls if "/neo/rest/v1/feed" in url]
    assert windows, "NeoWs was never requested"
    covered = set()
    for params in windows:
        start = date.fromisoformat(params["start_date"])
        end = date.fromisoformat(params["end_date"])
        assert 0 <= (end - start).days <= 7, "NeoWs request exceeds its seven-day limit"
        assert start >= date(2026, 9, 1) and end <= date(2026, 9, 30)
        covered.update(start + timedelta(days=i) for i in range((end - start).days + 1))
    assert covered == {date(2026, 9, 1) + timedelta(days=i) for i in range(30)}


def test_donki_passes_requested_start_and_end_to_every_endpoint(monkeypatch):
    calls = capture_requests(monkeypatch)
    nasa.NASASource().fetch(
        "solar flare", date="2024-01-03", date_max="2024-01-05",
        now_utc="2026-09-17T12:00:00Z",
    )
    windows = {url.rsplit("/", 1)[-1]: params for url, params in calls if "/DONKI/" in url}
    assert set(windows) == {"FLR", "CME", "GST"}
    for endpoint, params in windows.items():
        assert params["startDate"] == "2024-01-03", endpoint
        assert params["endDate"] == "2024-01-05", endpoint


def test_search_resolves_month_into_neows_windows(monkeypatch):
    from astro_search.core import AstroSearch
    calls = capture_requests(monkeypatch)
    engine = AstroSearch()
    engine._sources = [nasa.NASASource()]
    # Exercise routing, date resolution, fan-out and the real NASA adapter.
    result = engine.search("asteroid close approaches this month", now_utc="2026-09-17T12:00:00Z")
    windows = [params for url, params in calls if "/neo/rest/v1/feed" in url]
    assert [(p["start_date"], p["end_date"]) for p in windows] == [
        ("2026-09-01", "2026-09-07"), ("2026-09-08", "2026-09-14"),
        ("2026-09-15", "2026-09-21"), ("2026-09-22", "2026-09-28"),
        ("2026-09-29", "2026-09-30"),
    ]
    assert result["context"]["now_utc"] == "2026-09-17T12:00:00Z"

