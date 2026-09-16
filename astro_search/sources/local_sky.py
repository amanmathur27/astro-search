"""Local celestial computation — ephem primary (no downloads), skyfield opportunistically.

Role: co-primary verifier + USNO fallback (SUPPLEMENT §5, FALLBACK_CHAINS USNO->local).
No network required for moon phase/illumination. Skyfield ephemeris used only if cached/available.
"""
from __future__ import annotations
from datetime import datetime, timezone
from .base import BaseSource
from ..normalizer import normalize


def _ephem_moon(date_utc: datetime) -> dict:
    import ephem
    m = ephem.Moon(date_utc)
    illum = float(m.phase)  # 0-100
    # phase angle -> 8 names
    # ephem doesn't expose named phase directly; derive from previous/new/full cycle
    obs = ephem.Observer()
    obs.date = date_utc
    try:
        prev_new = ephem.next_new_moon(obs.date - 30) if hasattr(ephem, "next_new_moon") else None
    except Exception:
        prev_new = None
    # illumination + waxing/waning via Sun-Moon elongation sign
    sun = ephem.Sun(date_utc)
    elong = (float(m.elong) + 360) % 360 if hasattr(m, "elong") else 0.0
    waxing = elong < 180
    if illum < 2:
        name = "New Moon"
    elif illum > 98:
        name = "Full Moon"
    elif illum < 48:
        name = "First Quarter" if waxing else "Last Quarter"
        # refine crescent vs quarter
        name = ("Waxing Crescent" if waxing else "Waning Gibbous") if illum < 40 else name
    else:
        name = "Waxing Gibbous" if waxing else "Waning Crescent"
        if 48 <= illum <= 52:
            name = "First Quarter" if waxing else "Last Quarter"
    out = {"phase": name, "illumination_pct": round(illum, 1), "waxing": waxing}
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
        cache.mkdir(parents=True, exist_ok=True)
        load = Loader(str(cache))
        ts = load.timescale()
        eph = load("de421.bsp")  # downloads once into cache dir, reused after
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
            base = _p.parse(date_s).replace(tzinfo=timezone.utc) if date_s else datetime.now(timezone.utc)
        except Exception:
            base = datetime.now(timezone.utc)
        try:
            info = _ephem_moon(base)
        except Exception as e:
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
