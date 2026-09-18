"""RSS sources — single class parameterized by RSS_FEEDS config."""
from __future__ import annotations
import html
import re
import requests
import feedparser
from .base import BaseSource
from ..normalizer import normalize

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}
TAG_RE = re.compile(r"<[^>]+>")


def _clean(s: str) -> str:
    s = html.unescape(s or "")
    s = TAG_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


RSS_FEEDS = [
    {"name": "The Astronomer's Telegram", "url": "https://www.astronomerstelegram.org/?rss", "authority": 2,
     "intents": ["alert_lookup"], "entities": ["*"], "category": "news", "rapid_reports": True},
    {"name": "NASA News", "url": "https://www.nasa.gov/news-releases/feed/", "authority": 3,
     "intents": ["recent_news", "mission_status", "celestial_event_lookup"], "entities": ["*"], "category": "news"},
    {"name": "NASA Science", "url": "https://science.nasa.gov/feed/", "authority": 3,
     "intents": ["recent_news", "research_lookup"], "entities": ["*"], "category": "discoveries"},
    {"name": "ESA News", "url": "https://www.esa.int/rssfeed/Our_Activities/Space_Science", "authority": 3,
     "intents": ["recent_news", "mission_status"], "entities": ["*"], "category": "news"},
    {"name": "NRAO", "url": "https://public.nrao.edu/news/feed/", "authority": 3,
     "intents": ["recent_news", "research_lookup"], "entities": ["deep_sky"], "category": "discoveries"},
    {"name": "JWST", "url": "https://webbtelescope.org/news/webb-news/rss.xml", "authority": 3,
     "intents": ["recent_news", "object_lookup"], "entities": ["missions", "deep_sky"], "category": "discoveries"},
    {"name": "Hubble", "url": "https://hubblesite.org/api/v3/news_releases/all?format=rss", "authority": 3,
     "intents": ["recent_news", "object_lookup"], "entities": ["missions", "deep_sky"], "category": "discoveries"},
    {"name": "ESO", "url": "https://www.eso.org/public/news/feed.rss", "authority": 3,
     "intents": ["recent_news", "research_lookup"], "entities": ["deep_sky"], "category": "discoveries"},
    {"name": "Chandra X-ray", "url": "https://chandra.harvard.edu/rss/news.rss", "authority": 3,
     "intents": ["recent_news"], "entities": ["deep_sky", "solar"], "category": "discoveries"},
    {"name": "EarthSky", "url": "https://earthsky.org/feed/", "authority": 2,
     "intents": ["recent_news", "celestial_event_lookup", "celestial_event_detail", "current_phenomenon", "concept_explanation"],
     "entities": ["*"], "category": "news"},
    {"name": "Universe Today", "url": "https://www.universetoday.com/feed/", "authority": 2,
     "intents": ["recent_news", "research_lookup", "concept_explanation"], "entities": ["*"], "category": "news"},
    {"name": "Sky & Telescope", "url": "https://skyandtelescope.org/astronomy-news/feed/", "authority": 2,
     "intents": ["recent_news", "celestial_event_lookup", "periodic_event"], "entities": ["*"], "category": "news"},
    {"name": "Astronomy Magazine", "url": "https://astronomy.com/feed", "authority": 2,
     "intents": ["recent_news", "celestial_event_lookup", "concept_explanation"], "entities": ["*"], "category": "news"},
    {"name": "AAS Nova", "url": "https://aasnova.org/feed/", "authority": 2,
     "intents": ["research_lookup", "recent_news"], "entities": ["*"], "category": "papers"},
    {"name": "Space.com", "url": "https://www.space.com/feeds/all", "authority": 2,
     "intents": ["recent_news", "mission_status"], "entities": ["*"], "category": "news"},
    {"name": "Spaceflight Now", "url": "https://spaceflightnow.com/feed/", "authority": 2,
     "intents": ["mission_status", "recent_news"], "entities": ["missions"], "category": "news"},
    {"name": "The Planetary Society", "url": "https://www.planetary.org/articles?rss=1", "authority": 2,
     "intents": ["recent_news", "mission_status"], "entities": ["*"], "category": "news"},
    {"name": "In-The-Sky.org", "url": "https://in-the-sky.org/rss.php?feed=dfan", "authority": 2,
     "intents": ["celestial_event_lookup", "periodic_event"], "entities": ["planetary", "moon_phases", "eclipses"], "category": "events"},
    {"name": "American Meteor Society", "url": "https://www.amsmeteors.org/feed/", "authority": 2,
     "intents": ["celestial_event_lookup", "periodic_event", "current_phenomenon"], "entities": ["meteor_showers"], "category": "events"},
    {"name": "Spaceweather.com", "url": "https://spaceweather.com/wordpress/?feed=rss2", "authority": 2,
     "intents": ["current_phenomenon", "celestial_event_lookup"], "entities": ["solar"], "category": "space_weather"},
    {"name": "SpaceNews", "url": "https://spacenews.com/feed/", "authority": 2,
     "intents": ["recent_news", "mission_status"], "entities": ["missions"], "category": "news"},
    {"name": "Centauri Dreams", "url": "https://www.centauri-dreams.org/feed/", "authority": 2,
     "intents": ["research_lookup", "concept_explanation"], "entities": ["deep_sky"], "category": "papers"},
    {"name": "Science News Space", "url": "https://www.sciencenews.org/topic/astronomy/feed", "authority": 2,
     "intents": ["recent_news", "research_lookup"], "entities": ["*"], "category": "news"},
    {"name": "Keck Observatory", "url": "https://www.keckobservatory.org/feed/", "authority": 1,
     "intents": ["recent_news", "research_lookup"], "entities": ["deep_sky"], "category": "discoveries"},
    {"name": "SpaceDaily", "url": "https://www.spacedaily.com/spacedaily.xml", "authority": 1,
     "intents": ["recent_news"], "entities": ["*"], "category": "news"},
    {"name": "Phys.org", "url": "https://phys.org/rss-feed/space-news/", "authority": 2,
     "intents": ["recent_news", "mission_status", "object_lookup"], "entities": ["missions", "deep_sky", "planets"], "category": "news"},
    {"name": "The Space Review", "url": "https://www.thespacereview.com/articles.xml", "authority": 1,
     "intents": ["recent_news", "mission_status"], "entities": ["missions"], "category": "news"},
]


class RSSSource(BaseSource):
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.name = cfg["name"]
        self.source_type = "rss"
        self.authority = cfg.get("authority", 2)
        self.intents = cfg.get("intents", [])
        self.entities = cfg.get("entities", ["*"])
        self.timeout = 12

    def fetch(self, query: str, **kwargs) -> list[dict]:
        try:
            max_results = int(kwargs.get("max_results", 8))
        except (TypeError, ValueError):
            max_results = 8
        max_results = max(1, min(max_results, 20))
        try:
            resp = requests.get(self.cfg["url"], headers=HEADERS, timeout=self.timeout)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            if self.cfg.get("rapid_reports") and (not feed.version or feed.bozo):
                raise ValueError("Invalid rapid-report feed")
        except Exception:
            self.report_error(kwargs)
            return []
        from ..ranker import _tok
        from ..intent import classify
        from ..relevance import tokens
        qtok = tokens(query)
        generic = {"latest", "news", "astronomy", "space", "science", "today", "recent", "updates"}
        broad_news = (kwargs.get("intent") == "recent_news" and not classify(query)[1]
                      and not (qtok - generic))
        scored = []
        for e in feed.entries[:100]:
            g = (lambda k, d="": e[k] if hasattr(e, "keys") and k in e.keys() else d)
            title = _clean(g("title"))
            summary = _clean(g("summary") or g("description"))
            url = g("link")
            pub = g("published") or g("updated")
            blob = (title + " " + summary).lower()
            hits = len(qtok & set(_tok(blob)))
            extra, authors = {}, []
            published_kind = "published" if g("published") else "updated_fallback"
            if self.cfg.get("rapid_reports"):
                from ..alerts import report_matches
                from urllib.parse import urlsplit, parse_qs
                parsed = urlsplit(url)
                ident = re.search(r"\bATel\s+(\d+)\b", title, re.I)
                if (parsed.scheme != "https" or parsed.hostname != "www.astronomerstelegram.org"
                        or not ident or parse_qs(parsed.query).get("read") != [ident.group(1)]):
                    self.report_error(kwargs)
                    continue
                if not report_matches(query, title, summary):
                    continue
                hits = max(hits, 1)  # explicit broad report browsing, not general RSS filler
                authors = [_clean(g("author"))] if g("author") else []
                published_kind = "issued" if pub else "unknown"
                extra = {"report_id": "ATel" + ident.group(1),
                         "publication_status": "rapid_report_not_peer_reviewed",
                         "complete_archive": False, "timestamp_semantics": "report_issued_not_event_time"}
            scored.append((hits, {"title": title, "summary": summary, "url": url,
                                  "extra": extra, "authors": authors,
                                  "modified": g("updated"),
                                  "published_kind": published_kind,
                                  "published": pub, "category": self.cfg.get("category", "news")}))
        from ..normalizer import to_iso_utc
        scored.sort(key=lambda x: (x[0], to_iso_utc(x[1]["published"])), reverse=True)
        top = [s for hits, s in scored if hits > 0][:max_results]
        if not top and broad_news:
            top = [s for _, s in sorted(scored, key=lambda x: to_iso_utc(x[1]["published"]), reverse=True)[:min(3, max_results)]]
            for row in top:
                row["extra"] = {"zero_hit_fallback": True}
        return [normalize(r, {"name": self.name, "source_type": "rss",
                              "authority": self.authority, "category": self.cfg.get("category", "news")})
                for r in top if r["title"] or r["url"]]
