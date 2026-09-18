"""DONKI event-time regression using an offline response fixture."""
from astro_search.sources import nasa


class Response:
    ok = True

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload



def test_donki_flare_preserves_event_time(monkeypatch):
    event_time = "2026-09-17T08:15Z"

    def get(url, **kwargs):
        if url.endswith("/DONKI/FLR"):
            return Response([{"flrID": "fixture-flare", "beginTime": event_time,
                              "note": "Fixture observation"}])
        if "/DONKI/" in url:
            return Response([])
        return Response({"date": "2026-09-17", "title": "Fixture APOD"})

    monkeypatch.setattr(nasa.requests, "get", get)
    rows = nasa.NASASource().fetch("solar flare", now_utc="2026-09-17T12:00:00Z")
    flares = [row for row in rows if row["title"] == "Solar flare: fixture-flare"]
    assert len(flares) == 1
    assert flares[0]["event_date_utc"] == "2026-09-17T08:15:00Z"
