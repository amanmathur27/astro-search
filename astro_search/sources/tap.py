"""TAP services: Exoplanet Archive live (v2); SIMBAD/VizieR/NED/Gaia helper (v2.1). No keys."""
from __future__ import annotations
from ..intent import CATALOG_RE
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


def object_term(query: str, explicit=None) -> str | None:
    """Resolve common catalogue designations; do not guess from prose's last word."""
    if explicit:
        return str(explicit).strip()[:80] or None
    match = CATALOG_RE.search(query)
    return match.group(0).strip() if match else None


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
            name_term = object_term(query, kwargs.get("object_name"))
            if not name_term:
                return []
            term = name_term.replace("'", "''").replace("%", "").replace("_", "")
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
            self.report_error(kwargs)
            return []
