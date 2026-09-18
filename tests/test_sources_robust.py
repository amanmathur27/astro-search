"""Offline regressions at adapter request/response boundaries."""
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from astro_search.sources import ads, arxiv, nasa, rss


class Response:
    ok = True

    def __init__(self, payload=None, content=b""):
        self.payload = payload
        self.content = content

    def json(self):
        return self.payload

    def raise_for_status(self):
        pass


def test_rss_no_unrelated_padding(monkeypatch):
    monkeypatch.setattr(rss.requests, "get", lambda *a, **k: Response())
    monkeypatch.setattr(rss.feedparser, "parse", lambda _: SimpleNamespace(entries=[
        {"title": "Ocean temperatures", "link": "https://example.org/ocean"},
        {"title": "Perseids peak", "link": "https://example.org/perseids"},
    ]))
    source = rss.RSSSource({"name": "Fixture", "url": "https://example.org/feed"})
    assert source.fetch("quasar spectroscopy", intent="research_lookup") == []
    rows = source.fetch("Perseids", intent="celestial_event_lookup")
    assert len(rows) == 1 and rows[0]["title"] == "Perseids peak"
    rows = source.fetch("latest astronomy news", intent="recent_news", max_results=1)
    assert len(rows) == 1 and rows[0]["extra"]["zero_hit_fallback"]


def test_ads_topic_reaches_request(monkeypatch):
    monkeypatch.setenv("ASTRO_ADS_KEY", "fixture")
    calls = []
    def get(url, **kwargs):
        calls.append(kwargs["params"]["q"])
        return Response({"response": {"docs": [{"title": ["Planet atmospheres"], "bibcode": "fixture"}]}})
    monkeypatch.setattr(ads.requests, "get", get)
    assert ads.ADSSource().fetch("atmospheres", topic="planets")[0]["category"] == "papers"
    assert 'arxiv_class:"astro-ph.EP"' in calls[0]
    assert "database:astronomy" in calls[0]


def test_nasa_earth_weather_and_apod_citation(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        if "apod" in url:
            return Response({"title": "Stars", "date": "2026-09-17", "url": "https://example.org/image.jpg"})
        if "eonet" in url:
            return Response({"events": [{"title": "Hurricane fixture", "id": "fixture"}]})
        return Response([])
    monkeypatch.setattr(nasa.requests, "get", get)
    source = nasa.NASASource()
    rows = source.fetch("aurora solar storm", now_utc="2026-09-17T00:00:00Z")
    assert not any("eonet" in url or "/neo/" in url for url in calls)
    assert rows[0]["url"] == "https://apod.nasa.gov/apod/ap260917.html"
    assert rows[0]["extra"]["media_url"].endswith("image.jpg")
    rows = source.fetch("hurricane", now_utc="2026-09-17T00:00:00Z")
    assert next(r for r in rows if r["title"] == "Hurricane fixture")["category"] == "news"


def test_arxiv_throttle_serializes_reservations(monkeypatch):
    clock = [100.0]
    sleeps = []
    monkeypatch.setattr(arxiv, "_LAST", [0.0])
    monkeypatch.setattr(arxiv, "_THROTTLE_LOCK", Lock())
    monkeypatch.setattr(arxiv.time, "monotonic", lambda: clock[0])
    def sleep(delay):
        sleeps.append(delay)
        clock[0] += delay
    monkeypatch.setattr(arxiv.time, "sleep", sleep)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: arxiv._throttle(), range(4)))
    assert sleeps == [3.0, 3.0, 3.0]
    assert arxiv._LAST[0] == 109.0


def test_arxiv_fetch_uses_throttle_and_topic(monkeypatch):
    calls = []
    monkeypatch.setattr(arxiv, "_throttle", lambda: calls.append("throttle"))
    def get(url, **kwargs):
        calls.append(kwargs["params"]["search_query"])
        return Response(content=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Planet study</title><id>https://arxiv.org/abs/fixture</id></entry></feed>')
    monkeypatch.setattr(arxiv.requests, "get", get)
    assert arxiv.ArxivSource().fetch("atmospheres", topic="planets")
    assert calls == ["throttle", "all:atmospheres AND cat:astro-ph.EP"]
