# Offline answer module.

"""Small offline answer resolvers; never substitute articles for a missing fact."""
from __future__ import annotations
import re

AU_KM = 149_597_870.7


class AnswerUnavailable(Exception):
    """Recognized request that available local resources cannot answer honestly."""

    def __init__(self, message, status="needs_clarification"):
        super().__init__(message)
        self.status = status


def body_distance(request, now):
    """Resolve a validated Earth-referenced body request without network access."""
    from .capabilities import BODIES, UNITS
    from .timeparse import reference_time
    import math
    if not request or request.get("error") or request.get("reference") != "earth":
        raise AnswerUnavailable("Unsupported distance relation; no reference body is inferred.")
    target = BODIES.get(request.get("target"))
    if not target or not target["ephem"] or request.get("unit") not in UNITS:
        raise AnswerUnavailable("Unsupported distance target or unit.")
    try:
        import ephem
    except ImportError:
        raise AnswerUnavailable("Current distance requires the optional local extra (PyEphem).") from None
    now = reference_time(now)
    try:
        au = float(getattr(ephem, target["ephem"])(now.replace(tzinfo=None)).earth_distance)
    except (ValueError, OverflowError, RuntimeError):
        raise AnswerUnavailable("The local ephemeris could not compute this distance.") from None
    if not math.isfinite(au) or au <= 0:
        raise AnswerUnavailable("Invalid local ephemeris distance; no answer is inferred.")
    unit = request["unit"]
    value = round(au * AU_KM * UNITS[unit], 8 if unit == "au" else 1)
    stamp = now.isoformat().replace("+00:00", "Z")
    return {"subject": target["name"] + " relative to Earth", "property": "distance",
            "value": value, "unit": unit, "method": "computed", "as_of": stamp,
            "provenance": {"model": "PyEphem", "version": ephem.__version__,
                           "target": request["target"], "reference": "earth",
                           "definition": "geocentric apparent center-to-center distance", "au_km": AU_KM},
            "qualifiers": ["Current distance, not an orbital average. Model accuracy is not independently certified."],
            "text": f"{target['name']} is approximately {value:,.8f} {unit} from Earth's center at {stamp} (center-to-center)." if unit == "au" else
                    f"{target['name']} is approximately {value:,.1f} {unit} from Earth's center at {stamp} (center-to-center)."}



def conjunction_answer(spec, now, lat=None, lon=None):
    """Compute the next close approach for a validated two-body request.

    A local minimum of the separation curve is not automatically a conjunction, so
    the engine claims one only at or below the stated threshold and otherwise
    abstains while reporting the smallest separation it actually found.
    """
    from .capabilities import BODIES
    from .geometry import (CLOSE_APPROACH_DEG, WINDOW_DAYS, STEP_DAYS, GeometryUnavailable,
                           conjunction_result, observer_for)
    from .timeparse import reference_time
    keys = [key for key in (spec.subject_id or "").split("+") if key]
    if len(keys) != 2 or any(key not in BODIES or key == "earth" for key in keys):
        raise AnswerUnavailable("Name exactly two supported bodies for a conjunction: "
                                + ", ".join(b["name"] for k, b in BODIES.items() if k != "earth") + ".")
    names = [BODIES[key]["name"] for key in keys]
    now = reference_time(now)
    try:
        import ephem
    except ImportError:
        raise AnswerUnavailable("Conjunction geometry requires the optional local extra (PyEphem).") from None
    try:
        observer = observer_for(ephem, names, lat, lon)
        result = conjunction_result(names, now, observer=observer,
                                    window_days=WINDOW_DAYS, step_days=STEP_DAYS)
    except GeometryUnavailable as exc:
        raise AnswerUnavailable(str(exc)) from None
    search = result["search"]
    if not result["approach"]:
        raise AnswerUnavailable(
            f"No close approach of {names[0]} and {names[1]} at or below "
            f"{result['threshold_deg']}° was found within {search['window_days']:.0f} days of "
            f"{now.date().isoformat()}. The smallest apparent separation found in that window was "
            f"{result['smallest']['separation_deg']:.4f}° at {result['smallest']['time_utc']}. "
            f"No conjunction time is inferred.", status="not_found")
    approach = result["approach"]
    qualifiers = [
        "Locally computed geometry (PyEphem), not an authoritative ephemeris service; model "
        "accuracy is not independently certified.",
        "Conjunction definitions vary (equal right ascension, equal ecliptic longitude, or minimum "
        f"separation); this is the minimum apparent angular separation, threshold "
        f"{result['threshold_deg']}°.",
        "No occultation, transit, grazing event, or visibility claim is derived from this separation.",
    ]
    if observer is not None:
        qualifiers.append(f"Topocentric apparent positions for lat {lat}, lon {lon}; the Moon's "
                          f"position is observer-dependent.")
    else:
        qualifiers.append("Geocentric apparent positions: no observer location was applied.")
    text = (f"{names[0]} and {names[1]} reach their next minimum apparent separation of "
            f"{approach['separation_deg']:.4f}° at {approach['time_utc']} ({search['frame']}, "
            f"no refraction).")
    return {"subject": f"{names[0]} and {names[1]}", "property": "conjunction",
            "value": approach["separation_deg"], "unit": "deg", "method": "computed",
            "time_utc": approach["time_utc"], "as_of": now.isoformat().replace("+00:00", "Z"),
            "positions": result.get("positions"), "smallest_in_window": result["smallest"],
            "provenance": {"model": "PyEphem", "version": ephem.__version__, "search": search},
            "qualifiers": qualifiers, "text": text}, []


def calendar_answer(query, spec, now, dates, tz="UTC"):
    """Use bundled calendars, preserving civil-date windows and provenance."""
    import json
    from datetime import date
    from importlib.resources import files
    from .calendar import validate_calendar_payload
    from .showers import load_showers
    from .timeparse import reference_time, timezone_for

    zone = timezone_for(tz)
    start = date.fromisoformat(dates["date_min"]) if dates.get("date_min") else now.astimezone(zone).date()
    end = date.fromisoformat(dates["date_max"]) if dates.get("date_max") else None
    phase = spec.property == "moon_phase_date"
    next_only = phase and (bool(re.search(r"\bnext\b", query, re.I)) or end is None)
    if not phase and end is None:
        raise AnswerUnavailable("Specify a period such as celestial events this month.")
    explicit_years = {int(y) for y in re.findall(r"\b(?:19|20|21)\d{2}\b", query)}
    if next_only and explicit_years:
        raise AnswerUnavailable("Use phase dates for a specified year, or 'next' relative to the reference time, separately.")
    if explicit_years and dates.get("relative"):
        raise AnswerUnavailable("Use either a relative interval or an explicit year, not both.")
    if (next_only and end and end < now.astimezone(zone).date()):
        raise AnswerUnavailable("The requested interval is in the past; ask for phase dates without 'next'.")
    if re.search(r"\b(?:next month|last month|previous)\b", query, re.I):
        raise AnswerUnavailable("This relative period is not supported yet; use this month or an explicit year.")
    if re.search(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b", query, re.I):
        raise AnswerUnavailable("Named-month filtering is not supported yet; use this month with a reference time.")
    years = list(range(start.year, (end.year if end else start.year) + 1))
    if next_only:
        years = [now.year] + ([now.year + 1] if now.year == 2026 else [])
    if not years or any(y not in (2026, 2027) for y in years):
        raise AnswerUnavailable("Bundled calendar coverage is 2026–2027; no date is inferred outside it.")
    rows = []
    for year in years:
        try:
            payload = json.loads(files("astro_search").joinpath("data", f"calendar_{year}.json").read_text(encoding="utf-8"))
            if validate_calendar_payload(payload, year, len(load_showers(year))):
                raise ValueError("invalid calendar")
        except (OSError, ValueError, TypeError):
            raise AnswerUnavailable("The bundled calendar is unavailable or failed validation.") from None
        rows.extend(payload["results"])
    selected = []
    for row in rows:
        if phase and str((row.get("extra") or {}).get("phase", "")).lower() != spec.subject:
            continue
        stamp = row.get("event_date_utc") or row["event_date"]
        day = date.fromisoformat(stamp) if row.get("date_only") else reference_time(stamp).astimezone(zone).date()
        if next_only:
            if row.get("date_only") or reference_time(stamp) <= now:
                continue
        elif not start <= day <= end:
            continue
        for key in ("freshness_h", "freshness_display"):
            row.pop(key, None)
        row.setdefault("extra", {})["local_display"] = str(day) if row.get("date_only") else reference_time(stamp).astimezone(zone).isoformat()
        selected.append(row)
    selected.sort(key=lambda r: r.get("event_date_utc") or r["event_date"])
    if next_only:
        selected = selected[:1]
    qualifiers = ["Bundled calendar: lunar eclipses are reference-only; planetary events and local visibility are not included."]
    outside = False
    if next_only and selected and end:
        day = reference_time(selected[0]["event_date_utc"]).astimezone(zone).date()
        outside = not start <= day <= end
        if outside:
            qualifiers.append("No next occurrence remains in the requested period; the displayed date is outside that period.")
    if phase and not selected:
        raise AnswerUnavailable("No matching phase remains within calendar coverage; no date is inferred.")
    value = selected[0]["event_date_utc"] if next_only and selected else [r.get("event_date_utc") or r["event_date"] for r in selected]
    text = (f"Next {spec.subject}: {selected[0]['extra']['local_display']} ({tz})." if next_only and selected
            else f"{len(selected)} recorded {spec.subject} occurrences from {start} to {end} ({tz}).")
    return {"subject": spec.subject, "property": spec.property, "value": value,
            "unit": "ISO-8601 dates", "method": "reference_calendar", "text": text,
            "as_of": now.isoformat().replace("+00:00", "Z"),
            "window": {"start": str(start), "end": str(end) if end else None, "timezone": str(tz)},
            "outside_requested_window": outside, "qualifiers": qualifiers,
            "provenance": {"sources": sorted({r["source"] for r in selected}),
                           "citations": sorted({r["url"] for r in selected}),
                           "validation": "structural; lunar instants cross-checked in tests within 120 seconds"}}, selected
