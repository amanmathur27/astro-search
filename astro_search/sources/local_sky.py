"""Local celestial computation — ephem primary (no downloads), skyfield opportunistically.

Role: co-primary verifier + USNO fallback (SUPPLEMENT §5, FALLBACK_CHAINS USNO->local).
No network required for moon phase/illumination. Skyfield ephemeris used only if cached/available.
"""
from __future__ import annotations
from datetime import datetime, timezone
from .base import BaseSource
from ..normalizer import normalize


def _phase_name(illum: float, waxing: bool) -> str:
    """Approximate display label from illumination (0-100) and direction.

    New/full use <2%/>98%; quarters use 48-52%. These display bands
    describe the current appearance, not exact phase-event instants.
    """
    if illum < 2:
        return "New Moon"
    if illum > 98:
        return "Full Moon"
    if 48 <= illum <= 52:
        return "First Quarter" if waxing else "Last Quarter"
    if waxing:
        return "Waxing Crescent" if illum < 50 else "Waxing Gibbous"
    return "Waning Crescent" if illum < 50 else "Waning Gibbous"


def _ephem_moon(date_utc: datetime) -> dict:
    import ephem
    m = ephem.Moon(date_utc)
    illum = float(m.phase)  # 0-100, illuminated fraction
    # PyEphem elongation is signed radians: east/positive is waxing,
    # west/negative is waning. No degree conversion or mean-cycle cutoff.
    waxing = float(m.elong) >= 0
    out = {"phase": _phase_name(illum, waxing),
           "illumination_pct": round(illum, 1), "waxing": waxing}
    try:
        out["next_full"] = str(ephem.next_full_moon(date_utc))
        out["next_new"] = str(ephem.next_new_moon(date_utc))
    except Exception:
        pass
    return out


def _skyfield_moon(date_utc: datetime) -> dict | None:
    try:
        import os
        from pathlib import Path
        from skyfield.api import Loader, Topos
        cache = Path(os.environ.get("ASTRO_SKYFIELD_DIR", str(Path.home() / ".skyfield")))
        if not (cache / "de421.bsp").is_file():
            return None
        load = Loader(str(cache))
        ts = load.timescale(builtin=True)
        eph = load("de421.bsp")
        t = ts.from_datetime(date_utc)
        sun, moon, earth = eph["sun"], eph["moon"], eph["earth"]
        elong = earth.at(t).observe(moon).apparent().separation_from(
            earth.at(t).observe(sun).apparent()).degrees
        return {"elongation_deg": round(float(elong), 2)}
    except Exception:
        return None


class LocalSkySource(BaseSource):
    name = "Local Sky"
    source_type = "computed"
    authority = 2
    intents = ["celestial_event_lookup", "celestial_event_detail", "periodic_event", "current_phenomenon"]
    entities = ["moon_phases", "eclipses", "planetary"]
    supports_location = True
    timeout = 5

    def fetch(self, query: str, **kwargs) -> list[dict]:
        q = (query or "").lower()
        if not any(k in q for k in ["moon", "quarter", "supermoon", "phase", "eclipse", "season", "solstice", "equinox", "event"]):
            return []
        date_s = kwargs.get("date")
        try:
            from dateutil import parser as _p
            from ..timeparse import reference_time, timezone_for
            base = _p.parse(date_s) if date_s else reference_time(kwargs.get("now_utc"))
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone_for(kwargs.get("tz", "UTC")))
            base = base.astimezone(timezone.utc)
        except (ValueError, TypeError):
            self.report_error(kwargs)
            return []
        try:
            info = _ephem_moon(base)
        except Exception as e:
            self.report_error(kwargs)
            return []
        sky = _skyfield_moon(base)
        iso = base.isoformat().replace("+00:00", "Z")
        summary = (f"Local computation for {base.strftime('%Y-%m-%d')}: {info['phase']}, "
                   f"illumination {info['illumination_pct']}%. "
                   + (f"Next full {info.get('next_full')}, next new {info.get('next_new')}. " if info.get("next_full") else "")
                   + "Global visibility (moon phase is geocentric).")[:400]
        return [normalize({
            "title": f"Moon: {info['phase']} — {base.strftime('%Y-%m-%d')} (local compute)",
            "summary": summary, "url": "https://aa.usno.navy.mil/",
            "published": iso, "category": "events", "event_type": "moon_phase",
            "event_date": iso, "event_date_utc": iso, "visibility": "Global",
            "extra": {"local_verify": info, "skyfield": sky, "computed": True},
        }, {"name": "Local Sky", "source_type": "computed", "authority": 2, "category": "events"})]
