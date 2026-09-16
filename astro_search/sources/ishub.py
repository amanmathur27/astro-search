"""IndianSpaceHub ISRO Data API v1 (indianspacehub.com/developers).

Free Hobby tier: 1000 req/day, Bearer key from dashboard -> ASTRO_ISH_KEY.
Gated like ADS: absent key => is_available() False, fetch [] (zero noise, zero cost).
Covers our ISRO gap: spacecrafts, launchers, upcoming launches, calendar events,
moon phase. Third-party aggregation (not official ISRO) — authority 3 for Indian
programme facts, cross-checkable via astro_fetch on isro.gov.in.
"""
from __future__ import annotations
import os
import requests
from .base import BaseSource
from ..normalizer import normalize

BASE = "https://indianspacehub.com/api/v1"
TIMEOUT = 15
META = {"name": "IndianSpaceHub", "source_type": "api", "authority": 3}


def _key() -> str | None:
    return os.environ.get("ASTRO_ISH_KEY") or None


def _get(path: str, params: dict | None = None) -> list | dict | None:
    key = _key()
    if not key:
        return None
    try:
        r = requests.get(f"{BASE}{path}", params=params or {},
                         headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
        if r.status_code in (401, 403, 429):
            return None
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, dict):
            return payload.get("data", payload)
        return payload
    except Exception:
        return None


class ISROHubSource(BaseSource):
    name = "IndianSpaceHub"
    source_type = "api"
    authority = 3
    intents = ["mission_status", "object_lookup", "celestial_event_lookup", "periodic_event"]
    entities = ["missions"]
    timeout = 15

    def is_available(self) -> bool:
        return bool(_key())

    def fetch(self, query: str, **kwargs) -> list[dict]:
        if not _key():
            return []
        q = (query or "").lower()
        out: list[dict] = []
        # spacecraft / mission profiles (Chandrayaan, Gaganyaan, Aditya-L1, EOS-05...)
        try:
            rows = _get("/spacecrafts", {"search": query[:60], "limit": kwargs.get("max_results", 5)})
            for row in (rows if isinstance(rows, list) else [])[: kwargs.get("max_results", 5)]:
                if not isinstance(row, dict):
                    continue
                name = row.get("name", query)
                out.append(normalize({
                    "title": f"{name} — {row.get('type', row.get('status', 'ISRO mission'))}",
                    "summary": f"{name}: {row.get('status', '')} {row.get('launch_date', '')} "
                               f"{row.get('type', '')} {row.get('agency', 'ISRO')}.".strip()[:400],
                    "url": "https://indianspacehub.com/missions",
                    "published": str(row.get("launch_date", "")), "category": "news",
                    "event_type": "mission_profile", "extra": {"ishub": row},
                }, {**META, "category": "news"}))
        except Exception:
            pass
        # launchers (PSLV/GSLV/LVM3/SSLV) + upcoming launches for launch queries
        if any(k in q for k in ["launch", "pslv", "gslv", "lvm3", "sslv", "rocket", "mission"]):
            try:
                rows = _get("/launchers", {"search": query[:60], "limit": 5})
                for row in (rows if isinstance(rows, list) else [])[:3]:
                    if not isinstance(row, dict):
                        continue
                    out.append(normalize({
                        "title": f"{row.get('name', 'Launcher')} — {row.get('status', 'ISRO launcher')}",
                        "summary": str(row)[:400], "url": "https://indianspacehub.com/launchers",
                        "published": "", "category": "news",
                        "event_type": "launcher_profile", "extra": {"ishub": row},
                    }, {**META, "category": "news"}))
            except Exception:
                pass
            try:
                rows = _get("/upcoming-launches", {"limit": 5})
                for row in (rows if isinstance(rows, list) else [])[:3]:
                    if not isinstance(row, dict):
                        continue
                    out.append(normalize({
                        "title": f"Upcoming: {row.get('name', row.get('mission', 'ISRO launch'))}",
                        "summary": f"{row.get('name', '')} {row.get('launch_date', row.get('date', ''))} "
                                   f"{row.get('status', '')} {row.get('vehicle', '')}.".strip()[:400],
                        "url": "https://indianspacehub.com/upcoming-launches",
                        "published": str(row.get("launch_date", row.get("date", ""))),
                        "category": "events", "event_type": "upcoming_launch",
                        "event_date": str(row.get("launch_date", row.get("date", ""))),
                        "event_date_utc": str(row.get("launch_date", row.get("date", ""))),
                        "extra": {"ishub": row},
                    }, {**META, "category": "events"}))
            except Exception:
                pass
        # calendar events for periodic queries
        if kwargs.get("intent") == "periodic_event":
            try:
                rows = _get("/calendar-events", {"limit": 10})
                for row in (rows if isinstance(rows, list) else [])[:5]:
                    if not isinstance(row, dict):
                        continue
                    out.append(normalize({
                        "title": str(row.get("name", row.get("title", "ISRO event"))),
                        "summary": str(row)[:400], "url": "https://indianspacehub.com/calendar",
                        "published": str(row.get("date", "")), "category": "events",
                        "event_type": "isro_event",
                        "event_date": str(row.get("date", "")), "event_date_utc": str(row.get("date", "")),
                        "extra": {"ishub": row},
                    }, {**META, "category": "events"}))
            except Exception:
                pass
        return out
