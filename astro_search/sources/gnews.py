"""Google News RSS — gated supplemental source. Authority 1, never default-on.

Fires ONLY when: (a) recency tokens in query, (b) trends=True opt-in (gap analysis),
(c) primary pool came back empty (last resort). Strict freshness cutoff kills stale noise.
Free, no key. Links are news.google.com redirects — resolved for top-3 only.
"""
from __future__ import annotations
import re
import requests
import feedparser
from .base import BaseSource
from ..normalizer import normalize

BASE = "https://news.google.com/rss/search"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
TIMEOUT = 12

RECENCY_RES = [
    re.compile(r"\bbreaking\b"), re.compile(r"\bright now\b"), re.compile(r"\bthis hour\b"),
    re.compile(r"\bjust\b"), re.compile(r"\btoday\b"), re.compile(r"\blatest\b"),
    re.compile(r"\btonight\b"), re.compile(r"\byesterday\b"), re.compile(r"\bthis morning\b"),
    re.compile(r"\bhours ago\b"), re.compile(r"\bthis week\b"), re.compile(r"\bpast week\b"),
]

EDITIONS = {
    "US": ("en-US", "US", "US:en"),
    "IN": ("en-IN", "IN", "IN:en"),
    "UK": ("en-GB", "GB", "GB:en"),
}


def has_recency(query: str) -> bool:
    q = (query or "").lower()
    return any(rx.search(q) for rx in RECENCY_RES)


# week-phrased queries ("developments this week") need the 7-day window, not 1-day
WEEK_RES = [re.compile(r"\bthis week\b"), re.compile(r"\bpast week\b")]


def recency_window_days(query: str, trends: bool) -> int:
    """Date-window for the GNews query + freshness cutoff basis."""
    if trends:
        return 7
    q = (query or "").lower()
    if any(rx.search(q) for rx in WEEK_RES):
        return 7
    return 1


def edition_params(edition: str | None) -> tuple[str, str, str]:
    if not edition:
        return EDITIONS["US"]
    key = edition.strip().upper()
    if key in EDITIONS:
        return EDITIONS[key]
    if ":" in edition:  # "IN:en" form
        gl, lang = (p.strip() for p in edition.split(":", 1))
        return (f"{lang}-{gl}".replace("--", "-"), gl.upper(), f"{gl.upper()}:{lang.lower()}")
    return EDITIONS["US"]


def resolve_url(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=8, stream=True, allow_redirects=True)
        final = r.url
        r.close()
        if final and "news.google.com" not in final:
            return final
    except Exception:
        pass
    return url


class GoogleNewsSource(BaseSource):
    name = "Google News"
    source_type = "rss"
    authority = 1
    intents = ["recent_news", "current_phenomenon", "mission_status"]
    entities = ["*"]
    timeout = 12

    def fetch(self, query: str, **kwargs) -> list[dict]:
        from datetime import datetime, timedelta, timezone
        from ..timeparse import reference_time
        now = reference_time(kwargs.get("now_utc"))
        trends = bool(kwargs.get("trends", False))
        if not (query or "").strip():
            return []
        # GNews ranks by relevance, not recency: force a date window or months-old
        # hits flood in and the freshness cutoff drops everything.
        q = query.strip()
        if not re.search(r"\b(after|before|when):", q, re.I):
            days = recency_window_days(query, trends)
            since = (now - timedelta(days=days)).strftime("%Y-%m-%d")
            q = f"{q} after:{since}"
        hl, gl, ceid = edition_params(kwargs.get("edition"))
        max_age_h = 168 if recency_window_days(query, trends) == 7 else 12
        try:
            r = requests.get(BASE, params={"q": q, "hl": hl, "gl": gl, "ceid": ceid},
                             headers=HEADERS, timeout=self.timeout)
            r.raise_for_status()
            feed = feedparser.parse(r.content)
        except Exception:
            self.report_error(kwargs)
            return []
        items = []
        for e in feed.entries[: 20 if trends else 10]:
            entry = e.get("title", "") if hasattr(e, "get") else getattr(e, "title", "")
            link = e.get("link", "") if hasattr(e, "get") else getattr(e, "link", "")
            pub = (e.get("published", "") or e.get("updated", "")) if hasattr(e, "get") else getattr(e, "published", "")
            src = ""
            try:
                s = e.get("source", {}) if hasattr(e, "get") else getattr(e, "source", {})
                src = (s.get("title", "") if isinstance(s, dict) else getattr(s, "title", "")) or ""
            except Exception:
                self.report_error(kwargs)
                src = ""
            items.append({"title": entry, "link": link, "pub": pub, "publisher": src})
        # newest first, resolve top-3 URLs only (redirect cost control)
        from ..normalizer import to_iso_utc
        items.sort(key=lambda x: to_iso_utc(x["pub"]), reverse=True)
        out = []
        for i, it in enumerate(items[: 8 if trends else 5]):
            resolved = False
            url = it["link"]
            if i < 3:
                direct = resolve_url(it["link"])
                resolved = direct != it["link"]
                url = direct
            rec = normalize({
                "title": it["title"], "summary": f"Via {it['publisher'] or 'Google News'}."[:400],
                "url": url, "published": it["pub"], "category": "news",
                "extra": {"publisher": it["publisher"], "via": "google_news_rss",
                          "resolved": resolved, "fetch_compatible": resolved},
            }, {"name": "Google News", "source_type": "rss", "authority": 1, "category": "news"})
            from ..normalizer import freshness_hours, freshness_display
            fh = freshness_hours(rec.get("published", ""), now)
            rec["freshness_h"] = fh
            rec["freshness_display"] = freshness_display(fh)
            if isinstance(fh, int) and not isinstance(fh, bool) and fh <= max_age_h:
                out.append(rec)
            elif fh is None and trends:
                out.append(rec)  # unknown age kept only for deliberate trend scans
        return out
