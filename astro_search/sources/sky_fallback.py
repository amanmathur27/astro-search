"""Location fallbacks: sunrise-sunset.org + ephemeris.fyi. No keys."""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize

TIMEOUT = 12


def sunrise_sunset(lat: float, lon: float, date: str) -> dict | None:
    try:
        r = requests.get("https://api.sunrise-sunset.org/json",
                         params={"lat": lat, "lng": lon, "date": date, "formatted": 0}, timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
        return d.get("results") if d.get("status") == "OK" else None
    except Exception:
        return None


def ephemeris_position(body: str, lat: float, lon: float, dt_iso: str) -> dict | None:
    try:
        r = requests.get("https://ephemeris.fyi/ephemeris/get_single_body_position",
                         params={"body": body, "latitude": lat, "longitude": lon, "datetime": dt_iso},
                         timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


class FallbackSkySource(BaseSource):
    name = "Twilight Fallback"
    source_type = "api"
    authority = 2
    intents = ["celestial_event_lookup", "celestial_event_detail"]
    entities = ["planetary", "moon_phases"]
    supports_location = True
    timeout = 12

    def fetch(self, query: str, **kwargs) -> list[dict]:
        lat, lon = kwargs.get("lat"), kwargs.get("lon")
        if lat is None or lon is None:
            return []
        q = (query or "").lower()
        out: list[dict] = []
        if any(k in q for k in ["sunrise", "sunset", "twilight", "golden hour", "rise", "set", "tonight"]):
            ss = sunrise_sunset(lat, lon, kwargs.get("date") or "today")
            if ss:
                out.append(normalize({
                    "title": f"Sunrise/sunset {kwargs.get('date', 'today')} (fallback)",
                    "summary": f"Sunrise {ss.get('sunrise')}, sunset {ss.get('sunset')}, solar noon {ss.get('solar_noon')} (UTC). Moon phase via USNO/Local Sky."[:400],
                    "url": "https://sunrise-sunset.org/",
                    "published": "", "category": "events", "event_type": "rise_set",
                    "extra": {"sunrise_sunset": ss, "fallback": True},
                }, {"name": "Sunrise-Sunset.org", "source_type": "api", "authority": 2, "category": "events"}))
        body = next((b for b in ["moon", "mars", "jupiter", "saturn", "venus"] if b in q), None)
        if body:
            from ..timeparse import now_utc_iso
            pos = ephemeris_position(body, lat, lon, kwargs.get("now_utc") or now_utc_iso())
            if pos:
                out.append(normalize({
                    "title": f"{body.title()} position now (fallback)",
                    "summary": str(pos)[:400], "url": "https://ephemeris.fyi/",
                    "published": "", "category": "events", "event_type": "ephemeris",
                    "extra": {"ephemeris": pos, "fallback": True},
                }, {"name": "ephemeris.fyi", "source_type": "api", "authority": 2, "category": "events"}))
        return out
