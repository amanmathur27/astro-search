"""USNO AA API v4.0.1 — moon phases, SOLAR eclipses, seasons, rise/set, sidereal. No key.

Docs: https://aa.usno.navy.mil/data/api.html
Verified 2026-09-16: solar/year uses key `eclipses_in_year`; NO lunar eclipse endpoint
exists (404) — lunar eclipses come from NASA eclipse site links + RSS + Local Sky.
Seasons returns `data` list of {phenom, month, day, year, time}.
"""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize

BASE = "https://aa.usno.navy.mil/api"
TIMEOUT = 15
META = {"name": "USNO", "source_type": "api", "authority": 3, "category": "events"}


def _get(path: str, params: dict | None = None) -> dict:
    r = requests.get(f"{BASE}{path}", params=params or {}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _iso(y, m, d, t: str = "00:00") -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}T{t[:5]}:00Z"


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
        from dateutil import parser as _p
        q = query.lower()
        year = kwargs.get("year") or datetime.now(timezone.utc).year
        today = kwargs.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lat, lon = kwargs.get("lat"), kwargs.get("lon")
        full_sweep = kwargs.get("intent") == "periodic_event" or "calendar" in q
        out: list[dict] = []

        # --- solar eclipses (only kind USNO serves) ---
        if full_sweep or "eclipse" in q:
            want_lunar_only = "lunar" in q and "solar" not in q
            if not want_lunar_only:
                try:
                    data = _get("/eclipses/solar/year", {"year": year})
                    for ev in data.get("eclipses_in_year", []):
                        label = ev.get("event", "Solar eclipse")
                        try:
                            dt = _p.parse(label, fuzzy=True)
                            iso = dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
                        except Exception:
                            iso = f"{ev.get('year', year)}-{int(ev.get('month', 1)):02d}-{int(ev.get('day', 1)):02d}T00:00:00Z"
                        out.append(normalize({
                            "title": f"{label} ({ev.get('year', year)})",
                            "summary": f"{label} occurs {iso[:10]}. Local circumstances: query with lat/lon for magnitude/obscuration."[:400],
                            "url": "https://eclipse.gsfc.nasa.gov/",
                            "published": iso, "category": "events", "event_type": "solar_eclipse",
                            "event_date": iso, "event_date_utc": iso,
                            "visibility": "See NASA eclipse maps for path",
                            "visibility_url": "https://eclipse.gsfc.nasa.gov/",
                            "extra": {"raw": ev},
                        }, META))
                    # local circumstances when location given
                    if lat is not None and lon is not None and ("detail" in kwargs.get("intent", "") or "visible" in q or "can i see" in q):
                        try:
                            loc = _get("/eclipses/solar/date", {"date": today, "coords": f"{lat},{lon}"})
                            props = loc.get("properties", {}) if isinstance(loc, dict) else {}
                            if props.get("description"):
                                out.append(normalize({
                                    "title": f"Solar eclipse circumstances {today} @ {lat},{lon}",
                                    "summary": f"{props.get('description')} Mag {props.get('magnitude')}, obscuration {props.get('obscuration')}%."[:400],
                                    "url": "https://aa.usno.navy.mil/data/SolarEclipses",
                                    "published": today, "category": "events", "event_type": "solar_eclipse",
                                    "visibility": props.get("description"),
                                    "extra": {"local_eclipse": props},
                                }, META))
                        except Exception:
                            pass
                except Exception:
                    pass
            if "lunar" in q or ("eclipse" in q and "solar" not in q):
                # USNO has no lunar endpoint: link out explicitly instead of failing silently
                out.append(normalize({
                    "title": f"Lunar eclipses {year} — NASA eclipse catalog",
                    "summary": f"USNO serves solar eclipses only. Full lunar list with visibility maps: NASA eclipse site."[:400],
                    "url": "https://eclipse.gsfc.nasa.gov/LEcat/LE1991-2030.html",
                    "published": "", "category": "events", "event_type": "lunar_eclipse",
                    "visibility_url": "https://eclipse.gsfc.nasa.gov/LEcat/LE1991-2030.html",
                    "extra": {"note": "USNO has no lunar eclipse API; see NASA catalog"},
                }, META))

        # --- moon phases ---
        if full_sweep or any(k in q for k in ["moon", "quarter", "supermoon"]) or not out:
            # yearly calendar mode: all phases of the year (static, ~50 entries)
            if full_sweep:
                try:
                    data = _get("/moon/phases/year", {"year": year})
                    for ph in data.get("phasedata", []):
                        iso = _iso(ph.get("year"), ph.get("month"), ph.get("day"), ph.get("time", "00:00"))
                        out.append(normalize({
                            "title": f"{ph.get('phase')} — {ph.get('month')}/{ph.get('day')}/{ph.get('year')}",
                            "summary": f"{ph.get('phase')} occurs {iso} UTC."[:400],
                            "url": "https://aa.usno.navy.mil/",
                            "published": iso, "category": "events", "event_type": "moon_phase",
                            "event_date": iso, "event_date_utc": iso,
                            "extra": {"phase": ph.get("phase")},
                        }, META))
                except Exception:
                    pass
            else:
                try:
                    data = _get("/moon/phases/date", {"date": today, "nump": 4})
                    for ph in data.get("phasedata", []):
                        iso = _iso(ph.get("year"), ph.get("month"), ph.get("day"), ph.get("time", "00:00"))
                        out.append(normalize({
                            "title": f"{ph.get('phase')} — {ph.get('month')}/{ph.get('day')}/{ph.get('year')}",
                            "summary": f"{ph.get('phase')} occurs {iso} UTC."[:400],
                            "url": "https://aa.usno.navy.mil/",
                            "published": iso, "category": "events", "event_type": "moon_phase",
                            "event_date": iso, "event_date_utc": iso,
                            "extra": {"phase": ph.get("phase")},
                        }, META))
                except Exception:
                    pass

        # --- seasons / apsides ---
        if full_sweep or any(k in q for k in ["solstice", "equinox", "season", "perihelion", "aphelion"]):
            try:
                data = _get("/seasons", {"year": year})
                for ev in data.get("data", []):
                    iso = _iso(ev.get("year", year), ev.get("month"), ev.get("day"), ev.get("time", "00:00"))
                    out.append(normalize({
                        "title": f"{ev.get('phenom')} {year}",
                        "summary": f"{ev.get('phenom')} occurs {iso} UTC (global instant)."[:400],
                        "url": "https://aa.usno.navy.mil/", "published": iso,
                        "category": "events", "event_type": "season",
                        "event_date": iso, "event_date_utc": iso, "visibility": "Global",
                        "extra": {"phenom": ev.get("phenom")},
                    }, META))
            except Exception:
                pass

        # --- rise/set/transit (GeoJSON aware) ---
        if lat is not None and lon is not None and any(k in q for k in ["sunrise", "sunset", "moonrise", "rise", "tonight"]):
            try:
                data = _get("/rstt/oneday", {"date": today, "coords": f"{lat},{lon}", "tz": kwargs.get("tz", 0)})
                props = data.get("properties", {}) if isinstance(data, dict) else {}
                info = props.get("data", props) if isinstance(props, dict) else {}
                sun = (info.get("sundata") or []) if isinstance(info, dict) else []
                moon = (info.get("moondata") or []) if isinstance(info, dict) else []
                if sun or moon:
                    sun_s = "; ".join(str(s.get("phen")) + " " + str(s.get("time")) for s in sun[:4])
                    moon_s = "; ".join(str(m.get("phen")) + " " + str(m.get("time")) for m in moon[:4])
                    summ = ("Sun: " + sun_s + ". Moon: " + moon_s +
                            ". Illum " + str(info.get("fracillum", "?")) + ", " + str(info.get("curphase", "")) + ".")[:400]
                else:
                    summ = str(data)[:400]
                out.append(normalize({
                    "title": f"Sun/Moon rise-set {today} @ {lat},{lon}",
                    "summary": summ, "url": "https://aa.usno.navy.mil/",
                    "published": "", "category": "events", "event_type": "rise_set",
                    "extra": {"rstt": data},
                }, META))
            except Exception:
                pass

        # --- sidereal (requires time param per docs) ---
        if lat is not None and lon is not None and any(k in q for k in ["sidereal", "lst", "transit"]):
            try:
                now_t = datetime.now(timezone.utc).strftime("%H:%M:%S")
                data = _get("/siderealtime", {"date": today, "time": now_t, "coords": f"{lat},{lon}"})
                out.append(normalize({
                    "title": "Local sidereal time (USNO)",
                    "summary": str(data)[:400], "url": "https://aa.usno.navy.mil/",
                    "published": "", "category": "events", "event_type": "sidereal_time",
                    "extra": {"sidereal": data},
                }, META))
            except Exception:
                pass
        return out
