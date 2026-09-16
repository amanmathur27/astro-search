"""JPL SSD APIs: CAD, SBDB, Sentry, Fireball, Scout, Horizons (OBSERVER). No key."""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize

BASE = "https://ssd-api.jpl.nasa.gov"
TIMEOUT = 15


class JPLSource(BaseSource):
    name = "JPL"
    source_type = "api"
    authority = 3
    intents = ["celestial_event_lookup", "object_lookup", "recent_news"]
    entities = ["planets", "deep_sky", "meteor_showers"]
    timeout = 15

    def fetch(self, query: str, **kwargs) -> list[dict]:
        from datetime import datetime, timezone
        q = query.lower()
        out: list[dict] = []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Named object lookup via SBDB
        if kwargs.get("intent") == "object_lookup" or any(k in q for k in ["asteroid", "comet", "apophis", "ceres"]):
            name = kwargs.get("object_name") or query.split(" of ")[-1].split(" about ")[-1][:40]
            try:
                r = requests.get(f"{BASE}/sbdb.api", params={"sstr": name}, timeout=TIMEOUT)
                if r.ok:
                    d = r.json()
                    obj = d.get("object", {})
                    out.append(normalize({
                        "title": f"{obj.get('fullname', name)} — small-body data",
                        "summary": f"Orbit: {d.get('orbit', {}).get('elements', '?')}. {str(d)[:200]}"[:400],
                        "url": f"https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr={name}",
                        "published": "", "category": "discoveries", "event_type": "asteroid_data",
                        "extra": {"object": obj},
                    }, {"name": "JPL", "source_type": "api", "authority": 3, "category": "discoveries"}))
            except Exception:
                pass
        # Close approaches (default for event lookups)
        try:
            r = requests.get(f"{BASE}/cad.api", params={"date-min": today, "dist-max": "0.05", "limit": 5, "fullname": True}, timeout=TIMEOUT)
            if r.ok:
                d = r.json()
                fields = d.get("fields", [])
                for row in (d.get("data") or [])[:5]:
                    rec = dict(zip(fields, row))
                    out.append(normalize({
                        "title": f"Close approach {rec.get('fullname', rec.get('des'))} on {rec.get('cd')}",
                        "summary": f"Dist {rec.get('dist')} AU, v_rel {rec.get('v_rel')} km/s, H {rec.get('h')}."[:400],
                        "url": "https://cneos.jpl.nasa.gov/ca/",
                        "published": str(rec.get("cd", "")), "category": "events",
                        "event_type": "asteroid_flyby", "event_date": str(rec.get("cd", "")),
                        "event_date_utc": str(rec.get("cd", "")), "extra": {"cad": rec},
                    }, {"name": "JPL", "source_type": "api", "authority": 3, "category": "events"}))
        except Exception:
            pass
        # Fireballs
        if any(k in q for k in ["fireball", "bolide", "meteor"]):
            try:
                r = requests.get(f"{BASE}/fireball.api", params={"limit": 5}, timeout=TIMEOUT)
                if r.ok:
                    d = r.json()
                    fields = d.get("fields", [])
                    for row in (d.get("data") or [])[:5]:
                        rec = dict(zip(fields, row))
                        out.append(normalize({
                            "title": f"Fireball {rec.get('date', '')} — {rec.get('energy', '?')} kt",
                            "summary": str(rec)[:400], "url": "https://cneos.jpl.nasa.gov/fireballs/",
                            "published": str(rec.get("date", "")), "category": "events",
                            "event_type": "fireball", "extra": {"fireball": rec},
                        }, {"name": "JPL", "source_type": "api", "authority": 3, "category": "events"}))
            except Exception:
                pass
        return out
