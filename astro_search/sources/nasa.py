"""NASA APIs: APOD, NeoWs, DONKI, Image Library, EONET. Key via ASTRO_NASA_KEY else DEMO_KEY."""
from __future__ import annotations
import os
import requests
from .base import BaseSource
from ..normalizer import normalize

BASE = "https://api.nasa.gov"
TIMEOUT = 15
KEY = os.environ.get("ASTRO_NASA_KEY", "DEMO_KEY")


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
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        # APOD for news/discovery/object queries
        try:
            r = requests.get(f"{BASE}/planetary/apod", params={"api_key": KEY, "date": today}, timeout=TIMEOUT)
            if r.ok:
                d = r.json()
                out.append(normalize({
                    "title": f"APOD: {d.get('title', today)}", "summary": str(d.get("explanation", "")),
                    "url": d.get("hdurl") or d.get("url", "https://apod.nasa.gov/"),
                    "published": d.get("date", today), "category": "discoveries",
                    "extra": {"media_type": d.get("media_type")},
                }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "discoveries"}))
        except Exception:
            pass
        # NeoWs for asteroid queries or event lookups
        if any(k in q for k in ["asteroid", "near-earth", "neo", "close approach", "flyby"]) or kwargs.get("category") in ("events", "all", None):
            try:
                r = requests.get(f"{BASE}/neo/rest/v1/feed", params={"start_date": today, "api_key": KEY}, timeout=TIMEOUT)
                if r.ok:
                    objs = []
                    for day, lst in (r.json().get("near_earth_objects", {}) or {}).items():
                        for o in lst[:5]:
                            ca = (o.get("close_approach_data") or [{}])[0]
                            objs.append(normalize({
                                "title": f"Asteroid {o.get('name')} close approach {day}",
                                "summary": f"{o.get('name')} ({'hazardous' if o.get('is_potentially_hazardous_asteroid') else 'non-hazardous'}), "
                                           f"miss {ca.get('miss_distance', {}).get('kilometers', '?')} km, vel {ca.get('relative_velocity', {}).get('kilometers_per_hour', '?')} km/h."[:400],
                                "url": "https://cneos.jpl.nasa.gov/", "published": day,
                                "category": "events", "event_type": "asteroid_flyby",
                                "extra": {"neo_id": o.get("id"), "hazardous": o.get("is_potentially_hazardous_asteroid")},
                            }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "events"}))
                    out.extend(objs[:5])
            except Exception:
                pass
        # DONKI flares for solar queries
        if any(k in q for k in ["flare", "cme", "solar storm", "geomagnetic", "aurora", "space weather"]):
            for kind, path in [("flare", "/DONKI/FLR"), ("cme", "/DONKI/CME"), ("storm", "/DONKI/GST")]:
                try:
                    r = requests.get(f"{BASE}{path}", params={"startDate": week_ago, "api_key": KEY}, timeout=TIMEOUT)
                    if r.ok and isinstance(r.json(), list):
                        for ev in r.json()[:3]:
                            out.append(normalize({
                                "title": f"Solar {kind}: {ev.get('flrID', ev.get('cmeID', ev.get('gstID', kind)))}",
                                "summary": str(ev.get("note", ev))[:400],
                                "url": "https://ccmc.gsfc.nasa.gov/donki/",
                                "published": str(ev.get("beginTime", ev.get("startTime", ""))),
                                "category": "space_weather", "extra": {"raw": ev},
                            }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "space_weather"}))
                except Exception:
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
                pass
        # EONET natural events (severeStorms) for space-weather queries
        if any(k in q for k in ["storm", "space weather", "aurora", "geomagnetic", "solar"]):
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
                            "category": "space_weather", "extra": {"eonet_id": ev.get("id")},
                        }, {"name": "NASA", "source_type": "api", "authority": 3, "category": "space_weather"}))
            except Exception:
                pass
        # Mars rover photos for Mars queries
        if "mars" in q and any(k in q for k in ["photo", "image", "rover", "curiosity", "perseverance"]):
            try:
                r = requests.get(f"{BASE}/mars-photos/api/v1/rovers/curiosity/photos",
                                 params={"sol": 1000, "api_key": KEY}, timeout=TIMEOUT)
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
                pass
        return out
