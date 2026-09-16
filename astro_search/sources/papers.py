"""arXiv astro-ph API (Atom XML, no key, 3s politeness) + ADS (gated) + Exoplanet TAP + ISS."""
from __future__ import annotations
import os
import time
import requests
import xml.etree.ElementTree as ET
from .base import BaseSource
from ..normalizer import normalize

ARXIV = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}
CATS = {"astrophysics": "astro-ph", "cosmology": "astro-ph.CO", "galaxies": "astro-ph.GA",
        "high_energy": "astro-ph.HE", "solar": "astro-ph.SR", "planets": "astro-ph.EP",
        "instrumentation": "astro-ph.IM"}
_LAST = [0.0]


class ArxivSource(BaseSource):
    name = "arXiv"
    source_type = "api"
    authority = 2
    intents = ["research_lookup", "recent_news"]
    entities = ["deep_sky", "planets"]
    timeout = 20

    def fetch(self, query: str, **kwargs) -> list[dict]:
        topic = kwargs.get("topic", "astrophysics")
        cat = CATS.get(topic, "astro-ph")
        # politeness: 3s between calls
        dt = time.time() - _LAST[0]
        if dt < 3.0:
            time.sleep(3.0 - dt)
        try:
            r = requests.get(ARXIV, params={"search_query": f"all:{query} AND cat:{cat}",
                                            "start": 0, "max_results": kwargs.get("max_results", 5),
                                            "sortBy": "submittedDate", "sortOrder": "descending"}, timeout=self.timeout)
            _LAST[0] = time.time()
            r.raise_for_status()
            root = ET.fromstring(r.content)
            out = []
            for e in root.findall("a:entry", NS)[: kwargs.get("max_results", 5)]:
                title = (e.findtext("a:title", "", NS) or "").strip()
                summary = (e.findtext("a:summary", "", NS) or "").strip()
                url = (e.findtext("a:id", "", NS) or "").strip()
                pub = (e.findtext("a:published", "", NS) or "").strip()
                authors = [a.findtext("a:name", "", NS) for a in e.findall("a:author", NS)][:3]
                out.append(normalize({
                    "title": title, "summary": summary, "url": url, "published": pub,
                    "category": "papers", "authors": authors,
                    "extra": {"arxiv_id": url.split("/abs/")[-1] if "/abs/" in url else url},
                }, {"name": "arXiv", "source_type": "api", "authority": 2, "category": "papers"}))
            return out
        except Exception:
            return []


class ADSSource(BaseSource):
    name = "NASA ADS"
    source_type = "api"
    authority = 3
    intents = ["research_lookup"]
    entities = ["*"]
    timeout = 15

    def is_available(self) -> bool:
        return bool(os.environ.get("ASTRO_ADS_KEY"))

    def fetch(self, query: str, **kwargs) -> list[dict]:
        key = os.environ.get("ASTRO_ADS_KEY")
        if not key:
            return []
        try:
            r = requests.get("https://api.adsabs.harvard.edu/v1/search/query",
                             params={"q": query, "fl": "title,abstract,author,year,citation_count,doi,bibcode",
                                     "rows": kwargs.get("max_results", 5), "sort": "citation_count desc"},
                             headers={"Authorization": f"Bearer {key}"}, timeout=self.timeout)
            r.raise_for_status()
            out = []
            for d in (r.json().get("response", {}).get("docs", []) or [])[: kwargs.get("max_results", 5)]:
                title = (d.get("title") or [""])[0]
                out.append(normalize({
                    "title": title, "summary": str(d.get("abstract", "")),
                    "url": f"https://ui.adsabs.harvard.edu/link_gateway/{d.get('bibcode', '')}/ABSTRACT" if d.get("bibcode") else "https://ui.adsabs.harvard.edu/",
                    "published": str(d.get("year", "")), "category": "papers",
                    "authors": d.get("author", [])[:3],
                    "extra": {"citations": d.get("citation_count"), "doi": d.get("doi")},
                }, {"name": "NASA ADS", "source_type": "api", "authority": 3, "category": "papers"}))
            return out
        except Exception:
            return []


class ExoplanetSource(BaseSource):
    """NASA Exoplanet Archive TAP (pscomppars). No key."""
    name = "Exoplanet Archive"
    source_type = "api"
    authority = 3
    intents = ["object_lookup", "research_lookup"]
    entities = ["deep_sky", "planets"]
    timeout = 20

    def fetch(self, query: str, **kwargs) -> list[dict]:
        try:
            q = f"select top 5 hostname,pl_name,pl_orbper,sy_dist,disc_year from pscomppars where pl_name like '%{query.split()[-1]}%'"
            r = requests.get("https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
                             params={"query": q, "format": "json"}, timeout=self.timeout)
            r.raise_for_status()
            rows = r.json() if isinstance(r.json(), list) else r.json().get("data", [])
            out = []
            for row in rows[:5]:
                if isinstance(row, dict):
                    name = row.get("pl_name", query)
                else:
                    name = str(row[1]) if len(row) > 1 else query
                out.append(normalize({
                    "title": f"Exoplanet {name}", "summary": str(row)[:400],
                    "url": "https://exoplanetarchive.ipac.caltech.edu/",
                    "published": "", "category": "discoveries", "extra": {"row": row},
                }, {"name": "Exoplanet Archive", "source_type": "api", "authority": 3, "category": "discoveries"}))
            return out
        except Exception:
            return []


class ISSSource(BaseSource):
    name = "Open Notify ISS"
    source_type = "api"
    authority = 2
    intents = ["mission_status"]
    entities = ["missions"]
    timeout = 10

    def fetch(self, query: str, **kwargs) -> list[dict]:
        out: list[dict] = []
        try:
            r = requests.get("http://api.open-notify.org/iss-now.json", timeout=self.timeout)
            if r.ok:
                d = r.json()
                pos = d.get("iss_position", {})
                out.append(normalize({
                    "title": f"ISS now: {pos.get('latitude')}, {pos.get('longitude')}",
                    "summary": f"ISS at lat {pos.get('latitude')}, lon {pos.get('longitude')}."[:400],
                    "url": "http://open-notify.org/Open-Notify-API/ISS-Location-Now/",
                    "published": "", "category": "news",
                    "extra": {"position": pos, "timestamp": d.get("timestamp")},
                }, {"name": "Open Notify ISS", "source_type": "api", "authority": 2, "category": "news"}))
            r2 = requests.get("http://api.open-notify.org/astros.json", timeout=self.timeout)
            if r2.ok and "crew" in query.lower() or "who" in query.lower():
                d2 = r2.json()
                out.append(normalize({
                    "title": f"{d2.get('number', '?')} humans in space now",
                    "summary": ", ".join(p.get("name", "") for p in d2.get("people", []))[:400],
                    "url": "http://open-notify.org/", "published": "",
                    "category": "news", "extra": {"people": d2.get("people", [])},
                }, {"name": "Open Notify ISS", "source_type": "api", "authority": 2, "category": "news"}))
        except Exception:
            pass
        return out
