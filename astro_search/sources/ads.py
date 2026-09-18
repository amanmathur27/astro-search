"""NASA ADS (gated on ASTRO_ADS_KEY, 5k/day)."""
from __future__ import annotations
import os
import requests
from .base import BaseSource
from ..normalizer import normalize


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
        from .arxiv import CATS
        topic = kwargs.get("topic", "astrophysics") or "astrophysics"
        scope = "database:astronomy"
        if topic in CATS and topic != "astrophysics":
            scope += f' AND arxiv_class:"{CATS[topic]}"'
        scoped_query = f"({query}) AND {scope}"
        try:
            r = requests.get("https://api.adsabs.harvard.edu/v1/search/query",
                             params={"q": scoped_query, "fl": "title,abstract,author,year,citation_count,doi,bibcode",
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
            self.report_error(kwargs)
            return []
