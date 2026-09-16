"""TAP services: Exoplanet Archive live (v2); SIMBAD/VizieR/NED/Gaia helper (v2.1). No keys."""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize


def query_tap(base_url: str, adql: str, timeout: int = 20) -> list:
    """Generic TAP sync query. Returns rows (list of dicts or lists)."""
    r = requests.get(f"{base_url.rstrip('/')}/sync",
                     params={"REQUEST": "doQuery", "LANG": "ADQL", "QUERY": adql, "FORMAT": "json"},
                     timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("data", []) or payload.get("rows", [])
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
            term = (query.split() or [""])[-1].replace("'", "''")[:40]
            rows = query_tap("https://exoplanetarchive.ipac.caltech.edu/TAP",
                             f"select top 5 hostname,pl_name,pl_orbper,sy_dist,disc_year from pscomppars where pl_name like '%{term}%'",
                             timeout=self.timeout)
            out = []
            for row in rows[:5]:
                name = row.get("pl_name", query) if isinstance(row, dict) else (str(row[1]) if len(row) > 1 else query)
                out.append(normalize({
                    "title": f"Exoplanet {name}", "summary": str(row)[:400],
                    "url": "https://exoplanetarchive.ipac.caltech.edu/",
                    "published": "", "category": "discoveries", "extra": {"row": row},
                }, {"name": "Exoplanet Archive", "source_type": "api", "authority": 3, "category": "discoveries"}))
            return out
        except Exception:
            return []
