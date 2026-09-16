"""USNO AA API — moon phases, eclipses, seasons, rise/set. No key."""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize

BASE = "https://aa.usno.navy.mil/api"
TIMEOUT = 15


def _get(path: str, params: dict | None = None) -> dict:
    r = requests.get(f"{BASE}{path}", params=params or {}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


class USNOSource(BaseSource):
    name = "USNO"
    source_type = "api"
    authority = 3
    intents = ["celestial_event_lookup", "celestial_event_detail", "periodic_event"]
    entities = ["eclipses", "moon_phases", "planetary"]
    supports_location = True
    timeout = 15

    def fetch(self, query: str, **kwargs) -> list[dict]:
        from datetime import datetime, timezone
        q = query.lower()
        year = kwargs.get("year") or datetime.now(timezone.utc).year
        lat = kwargs.get("lat")
        lon = kwargs.get("lon")
        out: list[dict] = []
        try:
            if any(k in q for k in ["solar eclipse", "lunar eclipse", "eclipse"]):
                for kind in (["solar", "lunar"] if "eclipse" in q and "solar" not in q and "lunar" not in q
                             else (["solar"] if "solar" in q else ["lunar"])):
                    try:
                        data = _get(f"/eclipses/{kind}/year", {"year": year})
                        for ev in data.get("eclipses", data.get("events", [])) if isinstance(data, dict) else []:
                            out.append(normalize({
                                "title": f"{str(ev.get('type', kind)).title()} {kind} eclipse {ev.get('date', year)}",
                                "summary": f"{kind.title()} eclipse on {ev.get('date', '')}. {ev.get('region', ev.get('visibility', ''))}"[:400],
                                "url": "https://eclipse.gsfc.nasa.gov/",
                                "published": str(ev.get("date", "")),
                                "category": "events", "event_type": f"{kind}_eclipse",
                                "event_date": str(ev.get("date", "")), "event_date_utc": str(ev.get("date", "")),
                                "visibility": ev.get("region", ev.get("visibility")),
                                "visibility_url": "https://eclipse.gsfc.nasa.gov/",
                                "extra": {"raw": ev},
                            }, {"name": "USNO", "source_type": "api", "authority": 3, "category": "events"}))
                    except Exception:
                        continue
            if any(k in q for k in ["moon", "full moon", "new moon", "quarter", "supermoon"]) or not out:
                try:
                    data = _get("/moon/phases/date", {"date": kwargs.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"), "nump": 4})
                    for ph in data.get("phasedata", []):
                        iso = f"{ph.get('year')}-{int(ph.get('month', 1)):02d}-{int(ph.get('day', 1)):02d}T{ph.get('time', '00:00')}:00Z"
                        out.append(normalize({
                            "title": f"{ph.get('phase')} — {ph.get('month')}/{ph.get('day')}/{ph.get('year')}",
                            "summary": f"Next {ph.get('phase')} occurs {iso} UTC."[:400],
                            "url": "https://aa.usno.navy.mil/",
                            "published": iso, "category": "events", "event_type": "moon_phase",
                            "event_date": iso, "event_date_utc": iso,
                            "extra": {"phase": ph.get("phase")},
                        }, {"name": "USNO", "source_type": "api", "authority": 3, "category": "events"}))
                except Exception:
                    pass
            if any(k in q for k in ["solstice", "equinox", "season"]) and not out:
                try:
                    data = _get("/seasons", {"year": year})
                    for k, v in (data.items() if isinstance(data, dict) else []):
                        if isinstance(v, str):
                            out.append(normalize({
                                "title": f"{k} {year}", "summary": f"{k} occurs {v} UTC."[:400],
                                "url": "https://aa.usno.navy.mil/", "published": v,
                                "category": "events", "event_type": "season",
                                "event_date": v, "event_date_utc": v, "extra": {},
                            }, {"name": "USNO", "source_type": "api", "authority": 3, "category": "events"}))
                except Exception:
                    pass
            if lat is not None and lon is not None and any(k in q for k in ["sunrise", "sunset", "moonrise", "rise", "tonight"]):
                try:
                    data = _get("/rstt/oneday", {"date": kwargs.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                                                 "coords": f"{lat},{lon}", "tz": kwargs.get("tz", 0)})
                    out.append(normalize({
                        "title": f"Sun/Moon rise-set {kwargs.get('date', 'today')}",
                        "summary": str(data)[:400], "url": "https://aa.usno.navy.mil/",
                        "published": "", "category": "events", "event_type": "rise_set",
                        "extra": {"rstt": data},
                    }, {"name": "USNO", "source_type": "api", "authority": 3, "category": "events"}))
                except Exception:
                    pass
        except Exception:
            return out
        return out
