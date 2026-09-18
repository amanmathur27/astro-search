"""Validated reference times and inclusive civil-date windows."""
from __future__ import annotations
import calendar
import re
from datetime import datetime, timedelta, timezone
from dateutil import parser, tz as dateutil_tz

YEAR_RE = re.compile(r"\b((?:19|20|21)\d{2})\b")
WORDS = {"today", "tonight", "tomorrow", "yesterday", "this weekend", "next week", "this month"}


def reference_time(value=None) -> datetime:
    """Return an aware UTC instant; never guess a naive override's timezone."""
    if value is None or value == "":
        return datetime.now(timezone.utc)
    dt = value if isinstance(value, datetime) else parser.isoparse(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("now_utc must include a timezone offset")
    return dt.astimezone(timezone.utc)


def timezone_for(value="UTC"):
    if isinstance(value, bool):
        raise ValueError("Invalid timezone")
    if isinstance(value, (int, float)):
        import math
        if not math.isfinite(value) or not -14 <= value <= 14:
            raise ValueError("Timezone offset must be finite and between -14 and 14 hours")
        return timezone(timedelta(hours=value))
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Timezone must be an IANA name or numeric UTC offset")
    zone = dateutil_tz.gettz(value)
    if zone is None:
        raise ValueError(f"Unknown timezone: {value}")
    return zone


def now_utc_iso(now=None) -> str:
    return reference_time(now).isoformat().replace("+00:00", "Z")


def today_label(now=None, tz="UTC") -> str:
    return reference_time(now).astimezone(timezone_for(tz)).strftime("%A, %Y-%m-%d")


def resolve_dates(query: str, now: datetime | None = None, tz="UTC") -> dict:
    """Inclusive local dates; next week means next Monday through Sunday."""
    today = reference_time(now).astimezone(timezone_for(tz)).date()
    q = (query or "").lower()
    years = list(dict.fromkeys(int(y) for y in YEAR_RE.findall(q)))
    out = {"date_min": None, "date_max": None,
           "is_historical": bool(years) and all(y < today.year for y in years),
           "relative": None, "year": years[0] if len(years) == 1 else None}
    start = end = None
    if re.search(r"\b(today|tonight)\b", q):
        out["relative"] = "tonight" if "tonight" in q else "today"
        start = today
        end = today + timedelta(days=1 if out["relative"] == "tonight" else 0)
    elif re.search(r"\btomorrow\b", q):
        out["relative"] = "tomorrow"
        start = end = today + timedelta(days=1)
    elif re.search(r"\byesterday\b", q):
        out["relative"] = "yesterday"
        start = end = today - timedelta(days=1)
        out["is_historical"] = True
    elif "this weekend" in q:
        out["relative"] = "weekend"
        start = today + timedelta(days=5 - today.weekday())
        end = start + timedelta(days=1)
    elif "next week" in q:
        out["relative"] = "next week"
        start = today + timedelta(days=7 - today.weekday())
        end = start + timedelta(days=6)
    elif "this month" in q:
        out["relative"] = "this month"
        start = today.replace(day=1)
        end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    elif years:
        start = today.replace(year=min(years), month=1, day=1)
        end = today.replace(year=max(years), month=12, day=31)
    if start:
        out.update(date_min=start.isoformat(), date_max=end.isoformat())
    return out
