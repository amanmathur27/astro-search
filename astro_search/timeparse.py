"""Relative-date resolver. Stdlib + dateutil only. Server UTC is truth."""
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone

YEAR_RE = re.compile(r"\b(20[0-2][0-9])\b")
WORDS = {"today", "tonight", "tomorrow", "yesterday", "this weekend", "next week", "this month"}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def today_label() -> str:
    return datetime.now(timezone.utc).strftime("%A, %Y-%m-%d")


def resolve_dates(query: str, now: datetime | None = None) -> dict:
    """Return {date_min, date_max, is_historical, relative} for routing."""
    now = now or datetime.now(timezone.utc)
    q = query.lower()
    out = {"date_min": None, "date_max": None, "is_historical": False, "relative": None}
    years = [int(y) for y in YEAR_RE.findall(query)]
    if years and all(y < now.year for y in years):
        out["is_historical"] = True
    if "tonight" in q or "today" in q:
        out["relative"] = "today"
        out["date_min"] = now.strftime("%Y-%m-%d")
        out["date_max"] = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "tomorrow" in q:
        out["relative"] = "tomorrow"
        d = now + timedelta(days=1)
        out["date_min"] = d.strftime("%Y-%m-%d")
        out["date_max"] = d.strftime("%Y-%m-%d")
    elif "yesterday" in q:
        out["relative"] = "yesterday"
        d = now - timedelta(days=1)
        out["date_min"] = d.strftime("%Y-%m-%d")
        out["date_max"] = d.strftime("%Y-%m-%d")
    elif "this weekend" in q:
        out["relative"] = "weekend"
        # Saturday..Sunday of current week
        wd = now.weekday()  # Mon=0
        sat = now + timedelta(days=(5 - wd) % 7)
        sun = sat + timedelta(days=1)
        out["date_min"] = sat.strftime("%Y-%m-%d")
        out["date_max"] = sun.strftime("%Y-%m-%d")
    return out
