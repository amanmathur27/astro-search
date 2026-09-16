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
        # Sentry impact risk (defensive parse — schema varies)
        if any(k in q for k in ["impact", "risk", "sentry", "hazard", "collision"]):
            try:
                r = requests.get(f"{BASE}/sentry.api", timeout=TIMEOUT)
                if r.ok:
                    d = r.json()
                    rows = d.get("data", []) if isinstance(d, dict) else []
                    fields = d.get("fields", []) if isinstance(d, dict) else []
                    summ = d.get("summary", "") if isinstance(d, dict) else ""
                    for row in rows[:5]:
                        rec = dict(zip(fields, row)) if fields else (row if isinstance(row, dict) else {"raw": row})
                        out.append(normalize({
                            "title": f"Impact risk: {rec.get('des', rec.get('fullname', 'object'))}",
                            "summary": f"{summ} {rec}".strip()[:400],
                            "url": "https://cneos.jpl.nasa.gov/sentry/",
                            "published": "", "category": "events",
                            "event_type": "impact_risk", "extra": {"sentry": rec},
                        }, {"name": "JPL", "source_type": "api", "authority": 3, "category": "events"}))
            except Exception:
                pass
        # Scout fresh NEO candidates (defensive parse)
        if any(k in q for k in ["newly discovered", "new asteroid", "scout", "fresh discovery", "just discovered"]):
            try:
                r = requests.get(f"{BASE}/scout.api", timeout=TIMEOUT)
                if r.ok:
                    d = r.json()
                    rows = d.get("data", []) if isinstance(d, dict) else (d if isinstance(d, list) else [])
                    for row in rows[:5]:
                        rec = row if isinstance(row, dict) else {"raw": row}
                        out.append(normalize({
                            "title": f"New NEO candidate: {rec.get('objectName', rec.get('des', 'unknown'))}",
                            "summary": str(rec)[:400],
                            "url": "https://cneos.jpl.nasa.gov/scout/",
                            "published": str(rec.get("firstObs", "")), "category": "discoveries",
                            "extra": {"scout": rec},
                        }, {"name": "JPL", "source_type": "api", "authority": 3, "category": "discoveries"}))
            except Exception:
                pass
        # Horizons OBSERVER table when lat/lon + planetary/body query
        if kwargs.get("lat") is not None and kwargs.get("lon") is not None and any(
                k in q for k in ["conjunction", "opposition", "position", "rise", "set", "where is", "jupiter", "saturn", "mars", "venus", "mercury"]):
            bodies = {"sun": "10", "moon": "301", "mercury": "199", "venus": "299", "mars": "499",
                      "jupiter": "599", "saturn": "699", "uranus": "799", "neptune": "899"}
            cmd = next((c for name, c in bodies.items() if name in q), "499")
            try:
                # NOTE: JPL tolerates unquoted scalars; quotes kept only where docs require them
                r = requests.get("https://ssd.jpl.nasa.gov/api/horizons.api", params={
                    "format": "json", "COMMAND": cmd, "OBJ_DATA": "NO",
                    "MAKE_EPHEM": "YES", "EPHEM_TYPE": "OBSERVER",
                    "CENTER": "coord@399", "COORD_TYPE": "GEODETIC",
                    "SITE_COORD": f"{kwargs['lon']},{kwargs['lat']},0",
                    "START_TIME": today, "STOP_TIME": today,
                    "STEP_SIZE": "1d", "QUANTITIES": "1,4,9",
                }, timeout=25)
                if r.ok:
                    d = r.json()
                    txt = d.get("result", "") or ""
                    out.append(normalize({
                        "title": f"Horizons ephemeris {cmd} for {kwargs['lat']},{kwargs['lon']} on {today}",
                        "summary": txt[-1200:][:400] if txt else "Horizons returned no ephemeris text.",
                        "url": "https://ssd.jpl.nasa.gov/horizons/",
                        "published": today, "category": "events", "event_type": "ephemeris",
                        "extra": {"horizons_command": cmd, "raw_tail": txt[-1500:]},
                    }, {"name": "JPL", "source_type": "api", "authority": 3, "category": "events"}))
            except Exception:
                pass
        return out
