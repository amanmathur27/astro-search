"""JPL SSD APIs: CAD, SBDB, Sentry, Fireball, Scout, Horizons (OBSERVER). No key."""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize

BASE = "https://ssd-api.jpl.nasa.gov"
TIMEOUT = 15


def object_name_from(query: str) -> str | None:
    """Extract a small-body designation from prose, or None if absent."""
    import re
    for pattern in (r"\b[CPDX]/\d{4}\s+[A-Z]\d+(?:-[A-Z])?\b",
                    r"\b\d+[PD](?:/[A-Za-z][A-Za-z-]*)?\b",
                    r"\b(?:18|19|20)\d{2}\s+[A-Z]{2}\d*\b"):
        match = re.search(pattern, query or "", re.I)
        if match:
            return match.group()
    match = re.search(r"\b(apophis|ceres|vesta|eros|bennu|ryugu|halley)\b", query or "", re.I)
    if match:
        return match.group()
    match = re.search(r"\b(?:asteroid|comet)\s+(\d+|[A-Za-z][A-Za-z'-]*)\b", query or "", re.I)
    excluded = {"orbit", "orbits", "data", "position", "positions", "close", "flyby",
                "impact", "risk", "news", "discovery", "discovered", "is", "the", "of"}
    if match and match[1].lower() not in excluded:
        return match[1]
    return None


def parse_horizons(payload: dict) -> dict:
    """Parse decimal-degree, UTC OBSERVER CSV; reject malformed tables."""
    import csv
    import math
    from datetime import timezone
    from dateutil.parser import parse

    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("Horizons error payload")
    text = payload.get("result")
    if not isinstance(text, str):
        raise ValueError("Missing Horizons text")
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "$$SOE")
        end = next(i for i, line in enumerate(lines) if line.strip() == "$$EOE")
        header = next(line for line in reversed(lines[:start]) if line.strip().startswith("Date__"))
    except StopIteration as exc:
        raise ValueError("Missing ephemeris table") from exc
    if end <= start or "(UT)" not in header:
        raise ValueError("Invalid table boundaries or time scale")
    columns = [c.strip() for c in next(csv.reader([header]))]
    fields = (("ra_deg", "R.A._(ICRF)", 0, 360),
              ("dec_deg", "DEC_(ICRF)", -90, 90),
              ("azimuth_deg", "Azi_(a-app)", 0, 360),
              ("elevation_deg", "Elev_(a-app)", -90, 90),
              ("apparent_magnitude", "APmag", None, None))
    if any(columns.count(column) != 1 for _, column, _, _ in fields):
        raise ValueError("Missing or duplicate observer columns")
    samples = []
    previous = None
    for cells in csv.reader(lines[start + 1:end]):
        if not cells or not any(c.strip() for c in cells):
            continue
        if len(cells) != len(columns):
            raise ValueError("Truncated observer row")
        try:
            instant = parse(cells[0].strip()).replace(tzinfo=timezone.utc)
            if previous is not None and instant <= previous:
                raise ValueError("Non-increasing sample times")
            previous = instant
            sample = {"time_utc": instant.isoformat().replace("+00:00", "Z")}
            for key, column, low, high in fields:
                raw = cells[columns.index(column)].strip()
                value = None if raw.lower() in ("", "n.a.") else float(raw)
                if value is not None and (not math.isfinite(value) or
                        (low is not None and not low <= value <= high)):
                    raise ValueError("Invalid observer quantity")
                if value is None and key != "apparent_magnitude":
                    raise ValueError("Missing observer position")
                sample[key] = value
            samples.append(sample)
        except (ValueError, OverflowError) as exc:
            raise ValueError("Invalid observer row") from exc
    if not samples:
        raise ValueError("No ephemeris samples")
    if any((parse(b["time_utc"]) - parse(a["time_utc"])).total_seconds() != 3600
           for a, b in zip(samples, samples[1:])):
        raise ValueError("Unexpected observer sample interval")
    return {"samples": samples, "sample_interval": "1h", "time_scale": "UTC",
            "coordinate_frame": "ICRF", "angle_units": "degrees"}


class JPLSource(BaseSource):
    name = "JPL"
    source_type = "api"
    authority = 3
    intents = ["celestial_event_lookup", "object_lookup", "recent_news"]
    entities = ["planets", "deep_sky", "meteor_showers"]
    timeout = 15

    def fetch(self, query: str, **kwargs) -> list[dict]:
        from datetime import datetime, timedelta, timezone
        q = query.lower()
        out: list[dict] = []
        from ..timeparse import reference_time
        today = kwargs.get("date") or reference_time(kwargs.get("now_utc")).strftime("%Y-%m-%d")
        # Named object lookup via SBDB
        name = kwargs.get("object_name") or object_name_from(query)
        if name:
            try:
                r = requests.get(f"{BASE}/sbdb.api", params={"sstr": name}, timeout=TIMEOUT)
                if r.ok:
                    d = r.json()
                    if d.get("message"):  # e.g. "specified object was not found"
                        return out
                    obj = d.get("object", {})
                    if not isinstance(obj, dict) or not obj.get("des") or not obj.get("fullname"):
                        raise ValueError("Missing SBDB object identity")
                    out.append(normalize({
                        "title": f"{obj.get('fullname', name)} — small-body data",
                        "summary": f"Orbit: {d.get('orbit', {}).get('elements', '?')}. {str(d)[:200]}"[:400],
                        "url": f"https://ssd.jpl.nasa.gov/tools/sbdb_lookup.html#/?sstr={name}",
                        "published": "", "category": "discoveries", "event_type": "asteroid_data",
                        "extra": {"object": obj},
                    }, {"name": "JPL", "source_type": "api", "authority": 3, "category": "discoveries"}))
            except Exception:
                self.report_error(kwargs)
                pass
        # Only retrieve close approaches when explicitly requested.
        try:
            if any(term in q for term in ("close approach", "flyby", "near-earth", "near earth")):
                params = {"date-min": today, "dist-max": "0.05", "limit": 5, "fullname": True}
                if kwargs.get("date_max"):
                    params["date-max"] = kwargs["date_max"]
                if name:
                    params["des"] = name
                r = requests.get(f"{BASE}/cad.api", params=params, timeout=TIMEOUT)
            else:
                r = None
            if r is not None and r.ok:
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
            self.report_error(kwargs)
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
                self.report_error(kwargs)
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
                self.report_error(kwargs)
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
                self.report_error(kwargs)
                pass
        # Horizons OBSERVER table when lat/lon + planetary/body query
        if kwargs.get("lat") is not None and kwargs.get("lon") is not None and any(
                k in q for k in ["conjunction", "opposition", "position", "rise", "set", "where is", "jupiter", "saturn", "mars", "venus", "mercury"]):
            bodies = {"sun": "10", "moon": "301", "mercury": "199", "venus": "299", "mars": "499",
                      "jupiter": "599", "saturn": "699", "uranus": "799", "neptune": "899"}
            import re
            cmd = next((c for name, c in bodies.items() if re.search(r"\b" + name + r"\b", q)), None)
            if cmd is None:
                return out
            try:
                # NOTE: JPL tolerates unquoted scalars; quotes kept only where docs require them
                r = requests.get("https://ssd.jpl.nasa.gov/api/horizons.api", params={
                    "format": "json", "COMMAND": cmd, "OBJ_DATA": "NO",
                    "MAKE_EPHEM": "YES", "EPHEM_TYPE": "OBSERVER",
                    "CENTER": "coord@399", "COORD_TYPE": "GEODETIC",
                    "SITE_COORD": f"{kwargs['lon']},{kwargs['lat']},0",
                    "START_TIME": today,
                    "STOP_TIME": (datetime.strptime(today, "%Y-%m-%d") + timedelta(days=1)).date().isoformat(),
                    "STEP_SIZE": "1h", "QUANTITIES": "1,4,9",
                    "CSV_FORMAT": "YES", "ANG_FORMAT": "DEG", "TIME_TYPE": "UT",
                }, timeout=25)
                if r.ok:
                    parsed = parse_horizons(r.json())
                    out.append(normalize({
                        "title": f"Horizons ephemeris {cmd} for {kwargs['lat']},{kwargs['lon']} on {today}",
                        "summary": f"{len(parsed['samples'])} hourly observer samples in UTC; angles in degrees. Samples are not exact rise/set events.",
                        "url": "https://ssd.jpl.nasa.gov/horizons/",
                        "published": "", "category": "events", "event_type": "ephemeris",
                        "event_date_utc": parsed["samples"][0]["time_utc"],
                        "extra": {"horizons_command": cmd, **parsed},
                    }, {"name": "JPL", "source_type": "api", "authority": 3, "category": "events"}))
            except Exception:
                self.report_error(kwargs)
                pass
        return out
