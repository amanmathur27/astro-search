"""arXiv astro-ph API (Atom XML, no key, 3s politeness)."""
from __future__ import annotations
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
