"""NASA APIs: APOD, NeoWs, DONKI, Image Library, EONET. Key via ASTRO_NASA_KEY else DEMO_KEY."""
from __future__ import annotations
import os
import requests
from .base import BaseSource
from ..normalizer import normalize

BASE = "https://api.nasa.gov"
TIMEOUT = 15


def _key() -> str:
    # read at call time (not import) so .env/tests can set it any time before fetching
    return os.environ.get("ASTRO_NASA_KEY", "DEMO_KEY") or "DEMO_KEY"


def _neo_objects(start, end):
    """Read inclusive NeoWs windows without exceeding seven days per request."""
    from datetime import date, timedelta
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first or (last - first).days > 366:
        raise ValueError("NeoWs window must be ordered and at most 367 days")
    objects = {}
    while first <= last:
        stop = min(first + timedelta(days=6), last)
        response = requests.get(f"{BASE}/neo/rest/v1/feed", params={
            "start_date": first.isoformat(), "end_date": stop.isoformat(), "api_key": _key(),
        }, timeout=TIMEOUT)
        if not response.ok:
            response.raise_for_status()
        payload = response.json()
        days = payload.get("near_earth_objects") if isinstance(payload, dict) else None
        if not isinstance(days, dict):
            raise ValueError("Malformed NeoWs response")
        for day, rows in days.items():
            if first.isoformat() <= day <= stop.isoformat() and isinstance(rows, list):
                objects[day] = rows
        first = stop + timedelta(days=1)
    return objects



class NASASource(BaseSource):
    name = "NASA"
    source_type = "api"
    authority = 3
    intents = ["recent_news", "celestial_event_lookup", "current_phenomenon", "object_lookup", "mission_status"]
    entities = ["*"]
    timeout = 15

    def fetch(self, query: str, **kwargs) -> list[dict]:
        from datetime import datetime, timedelta, timezone
        q = query.lower()
        out: list[dict] = []
        from ..timeparse import reference_time
        now = reference_time(kwargs.get("now_utc"))
        today = kwargs.get("date") or now.strftime("%Y-%m-%d")
        week_ago = kwargs.get("date") or (now - timedelta(days=7)).strftime("%Y-%m-%d")
        # APOD for news/discovery/object queries
        try:
            r = requests.get(f"{BASE}/planetary/apod", params={"api_key": _key(), "date": today}, timeout=TIMEOUT)
            if r.ok:
                d = r.json()
                out.append(normalize({
                    "title": f"APOD: {d.get('title', today)}", "summary": str(d.get("explanation", "")),
                    "url": f"https://apod.nasa.gov/apod/ap{datetime.strptime(d.get('date', today), '%Y-%m-%d'):%y%m%d}.html",
                    "published": d.get("date", today), "category": "discoveries",
                    "extra": {"media_type": d.get("media_type"), "media_url": d.get("hdurl") or d.get("url"),
                              "fetch_compatible": True},
                }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "discoveries"}))
        except Exception:
            self.report_error(kwargs)
            pass
        # NeoWs for asteroid queries or event lookups
        if any(k in q for k in ["asteroid", "near-earth", "neo", "close approach", "flyby"]):
            try:
                end = kwargs.get("date_max") or today
                objects = _neo_objects(today, end)
                objs = []
                for day, lst in sorted(objects.items()):
                    for o in lst[:5]:
                        ca = (o.get("close_approach_data") or [{}])[0]
                        hazardous = o.get("is_potentially_hazardous_asteroid")
                        hazard_label = "hazardous" if hazardous is True else "non-hazardous" if hazardous is False else "hazard classification unavailable"
                        objs.append(normalize({
                            "title": f"Asteroid {o.get('name')} close approach {day}",
                            "summary": f"{o.get('name')} ({hazard_label}), "
                                       f"miss {ca.get('miss_distance', {}).get('kilometers', '?')} km, vel {ca.get('relative_velocity', {}).get('kilometers_per_hour', '?')} km/h."[:400],
                            "url": "https://cneos.jpl.nasa.gov/", "published": day,
                            "category": "events", "event_type": "asteroid_flyby",
                            "event_date": day, "date_only": True, "precision": "day",
                            "extra": {"neo_id": o.get("id"), "hazardous": hazardous},
                        }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "events"}))
                out.extend(objs[:kwargs.get("max_results", 5)])
            except Exception:
                self.report_error(kwargs)
                pass
        # DONKI flares for solar queries
        if any(k in q for k in ["flare", "cme", "solar storm", "geomagnetic", "aurora", "space weather"]):
            donki_end = kwargs.get("date_max") or today
            for kind, path in [("flare", "/DONKI/FLR"), ("cme", "/DONKI/CME"), ("storm", "/DONKI/GST")]:
                try:
                    r = requests.get(f"{BASE}{path}", params={"startDate": week_ago, "endDate": donki_end, "api_key": _key()}, timeout=TIMEOUT)
                    if r.ok and isinstance(r.json(), list):
                        for ev in r.json()[:3]:
                            out.append(normalize({
                                "title": f"Solar {kind}: {ev.get('flrID', ev.get('cmeID', ev.get('gstID', kind)))}",
                                "summary": str(ev.get("note", ev))[:400],
                                "url": "https://ccmc.gsfc.nasa.gov/donki/",
                                "published": str(ev.get("beginTime", ev.get("startTime", ""))),
                                "event_date_utc": ev.get("beginTime") or ev.get("startTime"),
                                "event_type": kind,
                                "category": "space_weather", "extra": {"raw": ev},
                            }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "space_weather"}))
                except Exception:
                    self.report_error(kwargs)
                    continue
        # Image library for object lookups
        if any(k in q for k in ["image", "photo", "picture"]) or kwargs.get("intent") == "object_lookup":
            try:
                r = requests.get("https://images-api.nasa.gov/search", params={"q": query, "media_type": "image", "page_size": 5}, timeout=TIMEOUT)
                if r.ok:
                    for it in (r.json().get("collection", {}).get("items", []) or [])[:5]:
                        meta = (it.get("data") or [{}])[0]
                        link = (it.get("links") or [{}])[0].get("href", "https://images.nasa.gov/")
                        out.append(normalize({
                            "title": meta.get("title", query), "summary": str(meta.get("description", "")),
                            "url": link, "published": str(meta.get("date_created", "")),
                            "category": "discoveries", "extra": {"nasa_id": meta.get("nasa_id")},
                        }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "discoveries"}))
            except Exception:
                self.report_error(kwargs)
                pass
        # EONET is terrestrial weather, not solar/geomagnetic activity.
        if any(k in q for k in ["hurricane", "typhoon", "tropical storm", "terrestrial storm"]):
            try:
                r = requests.get("https://eonet.gsfc.nasa.gov/api/v3/events",
                                 params={"category": "severeStorms", "status": "open", "limit": 5}, timeout=TIMEOUT)
                if r.ok:
                    for ev in (r.json().get("events", []) or [])[:5]:
                        out.append(normalize({
                            "title": ev.get("title", "EONET severe storm"),
                            "summary": f"{ev.get('description', '')} Sources: {len(ev.get('sources', []))}."[:400],
                            "url": "https://eonet.gsfc.nasa.gov/",
                            "published": str((ev.get("geometry") or [{}])[0].get("date", "")),
                            "category": "news", "extra": {"eonet_id": ev.get("id"), "domain": "earth_weather"},
                        }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "news"}))
            except Exception:
                self.report_error(kwargs)
                pass
        # Mars rover photos for Mars queries
        if "mars" in q and any(k in q for k in ["photo", "image", "rover", "curiosity", "perseverance"]):
            try:
                r = requests.get(f"{BASE}/mars-photos/api/v1/rovers/curiosity/photos",
                                 params={"sol": 1000, "api_key": _key()}, timeout=TIMEOUT)
                if r.ok:
                    for p in (r.json().get("photos", []) or [])[:3]:
                        out.append(normalize({
                            "title": f"Mars photo {p.get('id')} sol {p.get('sol')} ({(p.get('camera') or {}).get('full_name', '')})",
                            "summary": f"Curiosity {p.get('earth_date')} sol {p.get('sol')}."[:400],
                            "url": p.get("img_src", "https://mars.nasa.gov/"),
                            "published": str(p.get("earth_date", "")), "category": "discoveries",
                            "extra": {"rover": "curiosity", "sol": p.get("sol")},
                        }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "discoveries"}))
            except Exception:
                self.report_error(kwargs)
                pass
        return out
