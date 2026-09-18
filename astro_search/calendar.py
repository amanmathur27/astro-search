"""Annual event partitioning and publication validation (no network)."""
from collections import Counter
from datetime import date

ANNUAL_TYPES = {"moon_phase", "solar_eclipse", "season", "meteor_shower"}


def partition_events(rows, year):
    annual, snapshots, references = [], [], []
    for original in rows:
        row = dict(original)
        stamp = row.get("event_date_utc") or row.get("event_date")
        extra = dict(row.get("extra") or {})
        row["extra"] = extra
        if not stamp and row.get("event_type") == "lunar_eclipse":
            references.append(row)
            continue
        if row.get("event_type") not in ANNUAL_TYPES or extra.get("computed"):
            snapshots.append(row)
            continue
        if not stamp or not str(stamp).startswith(f"{year}-"):
            continue
        if row.get("precision") in (None, "unspecified"):
            row["precision"] = "approximate" if extra.get("exact") is False else "source_reported"
        extra["provenance"] = {"source": row.get("source"), "url": row.get("url")}
        extra["visibility_status"] = "provided" if row.get("visibility") else "not_computed"
        annual.append(row)
    annual.sort(key=lambda r: r.get("event_date_utc") or r.get("event_date"))
    return annual, snapshots, references


def validate_calendar_payload(payload, year, expected_meteors):
    """Structural completeness, not independent astronomical certification."""
    from datetime import datetime, timezone
    from dateutil.parser import isoparse
    if not isinstance(payload, dict):
        return ["payload must be an object"]
    rows = payload.get("results")
    if not isinstance(rows, list):
        return ["results must be a list"]
    errors, stamps, seen = [], [], set()
    counts, phases, seasons = Counter(), Counter(), Counter()
    phase_names = {"new moon", "first quarter", "full moon", "last quarter"}
    for row in rows:
        if not isinstance(row, dict):
            errors.append("event must be an object")
            continue
        kind = row.get("event_type")
        if not isinstance(kind, str) or kind not in ANNUAL_TYPES:
            errors.append("nonannual record in results")
            continue
        extra = row.get("extra", {})
        if not isinstance(extra, dict):
            errors.append("event extra must be an object")
            extra = {}
        title = row.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append("missing event title")
        if not isinstance(row.get("date_only", False), bool):
            errors.append("date_only must be boolean")
        stamp = row.get("event_date_utc") or row.get("event_date")
        try:
            if not isinstance(stamp, str):
                raise ValueError()
            if row.get("date_only"):
                if row.get("event_date_utc"):
                    errors.append("date-only event has fabricated instant")
                if len(stamp) != 10 or row.get("precision") != "day":
                    raise ValueError()
                instant = datetime.combine(date.fromisoformat(stamp), datetime.min.time(), timezone.utc)
            else:
                instant = isoparse(stamp)
                if "T" not in stamp or instant.tzinfo is None:
                    raise ValueError()
                instant = instant.astimezone(timezone.utc)
            if instant.year != year:
                errors.append("out-of-year event")
            stamps.append(instant)
        except (ValueError, TypeError, OverflowError):
            errors.append("missing/invalid event date")
            continue
        identity = (kind, instant, str(extra.get("name", title)) if kind == "meteor_shower" else "")
        if identity in seen:
            errors.append("duplicate event")
            continue
        seen.add(identity)
        counts[kind] += 1
        if kind == "moon_phase":
            phase = extra.get("phase")
            phase = phase.casefold().strip() if isinstance(phase, str) else ""
            if phase not in phase_names:
                errors.append("unknown lunar phase")
            else:
                phases[phase] += 1
        if kind == "season":
            phenom = str(extra.get("phenom", "")).casefold()
            if "equinox" in phenom or "solstice" in phenom:
                seasons[instant.month] += 1
    if not 48 <= counts["moon_phase"] <= 52 or any(not 12 <= phases[p] <= 13 for p in phase_names):
        errors.append("incomplete four-phase lunar calendar")
    if not isinstance(expected_meteors, int) or isinstance(expected_meteors, bool) or expected_meteors < 1:
        errors.append("meteor dataset unavailable")
    elif counts["meteor_shower"] != expected_meteors:
        errors.append("incomplete meteor calendar")
    if seasons != Counter({3: 1, 6: 1, 9: 1, 12: 1}):
        errors.append("missing or duplicate equinox/solstice events")
    if not 2 <= counts["solar_eclipse"] <= 5:
        errors.append("incomplete solar eclipses")
    if stamps != sorted(stamps):
        errors.append("events not chronological")
    if type(payload.get("count")) is not int or payload["count"] != len(rows):
        errors.append("count mismatch")
    if payload.get("year", year) != year:
        errors.append("payload year mismatch")
    return list(dict.fromkeys(errors))

