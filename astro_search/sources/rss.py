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
        max_items = int(kwargs.get("max_results", 8))
        try:
            resp = requests.get(self.cfg["url"], headers=HEADERS, timeout=self.timeout)
            feed = feedparser.parse(resp.content)
        except Exception:
            return []
        qtok = set(query.lower().split())
        scored = []
        for e in feed.entries[:30]:
            title = _clean(getattr(e, "title", ""))
            summary = _clean(getattr(e, "summary", getattr(e, "description", "")))
            url = getattr(e, "link", "")
            pub = getattr(e, "published", getattr(e, "updated", ""))
            blob = (title + " " + summary).lower()
            hits = sum(1 for t in qtok if len(t) > 2 and t in blob)
            scored.append((hits, {"title": title, "summary": summary, "url": url,
                                  "published": pub, "category": self.cfg.get("category", "news")}))
        # keyword hit first, then recency order
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [s for _, s in scored[:max_items]]
        # if no hits at all, still return freshest 3 (keeps agents useful)
        if top and all(h == 0 for h, _ in scored[:max_items]) and qtok:
            top = [s for _, s in scored[:3]]
        return [normalize(r, {"name": self.name, "source_type": "rss",
                              "authority": self.authority, "category": self.cfg.get("category", "news")})
                for r in top if r["title"] or r["url"]]
