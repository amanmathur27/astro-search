"""Phys.org space feed integration: config presence + offline fetch behavior."""
import feedparser
import pytest
import requests
from astro_search.sources.rss import RSS_FEEDS, RSSSource


FEED_XML = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Space News</title>
<item><title>NASA spacecraft discovers a huge new crater on the moon</title>
<description>Scientists discovered a crater bigger than expected.</description>
<link>https://phys.org/news/2026-09-nasa-spacecraft-huge-crater-moon.html</link>
<pubDate>Thu, 17 Sep 2026 04:12:32 EDT</pubDate></item>
<item><title>Completely unrelated biology story</title>
<description>Virus particles assemble themselves.</description>
<link>https://phys.org/news/2026-09-virus.html</link>
<pubDate>Thu, 17 Sep 2026 03:00:00 EDT</pubDate></item>
</channel></rss>"""


class FakeResponse:
    content = FEED_XML.encode()
    status_code = 200

    def raise_for_status(self):
        pass


def test_phys_org_registered_with_space_scope():
    cfg = next(f for f in RSS_FEEDS if f["name"] == "Phys.org")
    assert cfg["url"].startswith("https://phys.org/rss-feed/")
    assert "space" in cfg["url"]
    assert "recent_news" in cfg["intents"] and "mission_status" in cfg["intents"]
    assert cfg["authority"] == 2  # aggregator, not institutional


def test_phys_org_fetch_scores_and_keeps_relevant_only(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResponse())
    rows = RSSSource({"name": "Phys.org", "url": "https://phys.org/rss-feed/space-news/",
                      "authority": 2, "intents": ["recent_news"], "entities": ["*"],
                      "category": "news"}).fetch("moon crater")
    assert len(rows) == 1
    assert rows[0]["title"].startswith("NASA spacecraft")
    assert rows[0]["source"] == "Phys.org"
    assert rows[0]["published"].endswith("Z")


def test_phys_org_not_selected_for_non_recency_intent():
    from astro_search.core import AstroSearch
    selected = [s.name for s in AstroSearch()._select("concept_explanation", [], "all")]
    assert "Phys.org" not in selected


def test_us_timezone_abbreviations_are_converted_not_assumed_utc():
    from astro_search.normalizer import to_iso_utc, freshness_hours
    # EDT is UTC-4: 04:12 EDT == 08:12Z, not 04:12Z
    assert to_iso_utc("Thu, 17 Sep 2026 04:12:32 EDT") == "2026-09-17T08:12:32Z"
    assert to_iso_utc("Thu, 17 Sep 2026 04:12:32 EST") == "2026-09-17T09:12:32Z"
    assert to_iso_utc("Thu, 17 Sep 2026 04:12:32 PDT") == "2026-09-17T11:12:32Z"
    assert to_iso_utc("Thu, 17 Sep 2026 04:12:32 PST") == "2026-09-17T12:12:32Z"
    assert to_iso_utc("Thu, 17 Sep 2026 04:12:32 CDT") == "2026-09-17T09:12:32Z"
    # numeric offsets and UTC keep working
    assert to_iso_utc("Thu, 17 Sep 2026 04:12:32 -0400") == "2026-09-17T08:12:32Z"
    assert to_iso_utc("Thu, 17 Sep 2026 04:12:32 GMT") == "2026-09-17T04:12:32Z"
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error", category=Warning)  # no UnknownTimezoneWarning
        to_iso_utc("Thu, 17 Sep 2026 04:12:32 EDT")
    # freshness inherits the same correctness
    assert freshness_hours("Thu, 17 Sep 2026 04:12:32 EDT", now="2026-09-17T12:12:32Z") == 4
