"""Enforces output contract. Never raises KeyError downstream. Stdlib + dateutil only."""
from __future__ import annotations
import html
import re
from datetime import datetime, timezone
from dateutil import parser as dateparser

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
# US zone abbreviations used by news feeds (Phys.org, Spaceweather.com, ...).
# dateutil does not know these; without this table they silently parse as naive
# and would be stamped UTC, shifting every timestamp by the DST offset.
US_TZINFOS = {
    "EDT": -4 * 3600, "EST": -5 * 3600, "CDT": -5 * 3600, "CST": -6 * 3600,
    "MDT": -6 * 3600, "MST": -7 * 3600, "PDT": -7 * 3600, "PST": -8 * 3600,
    "AKDT": -8 * 3600, "AKST": -9 * 3600, "HDT": -9 * 3600, "HST": -10 * 3600,
}
BOILERPLATE = [
    re.compile(r"subscribe to.*newsletter", re.I),
    re.compile(r"sign up for.*free", re.I),
    re.compile(r"click here to read more", re.I),
    re.compile(r"this article first appeared", re.I),
    re.compile(r"©\s*\d{4}"),
    re.compile(r"all rights reserved", re.I),
]

REQUIRED_DEFAULTS = {
    "title": "", "summary": "", "url": "", "source": "Unknown",
    "source_type": "api", "authority": 2, "category": "news",
    "published": "", "freshness_h": None,
}


def clean_text(s: str, limit: int = 400) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = TAG_RE.sub("", s)
    s = WS_RE.sub(" ", s).strip()
    for pat in BOILERPLATE:
        s = pat.sub("", s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut if cut else s[:limit]


def to_iso_utc(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = dateparser.parse(value, tzinfos=US_TZINFOS)
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def freshness_hours(published_iso: str, now=None) -> int | None:
    if not published_iso:
        return None
    try:
        dt = dateparser.parse(published_iso, tzinfos=US_TZINFOS)
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        from .timeparse import reference_time
        delta = reference_time(now) - dt.astimezone(timezone.utc)
        h = int(delta.total_seconds() // 3600)
        return max(h, 0)
    except Exception:
        return None


def freshness_display(hours: int | None) -> str | None:
    """Humanized age: minutes/hours/days/months. Numeric freshness_h stays for ranking."""
    if hours is None:
        return None
    if not isinstance(hours, (int, float)) or isinstance(hours, bool):
        return None
    h = max(int(hours), 0)
    if h < 1:
        return "just now"
    if h < 24:
        return f"{h}h ago"
    d = h // 24
    if d < 30:
        return f"{d}d ago"
    mo = d // 30
    if mo < 12:
        return f"{mo}mo ago"
    return f"{mo // 12}y ago"


def normalize(raw: dict, source_meta: dict) -> dict:
    """Merge raw + source_meta into strict contract (handoff §4 + supplement §5)."""
    if not isinstance(raw, dict):
        raw = {}
    if not isinstance(source_meta, dict):
        source_meta = {}
    out: dict = dict(REQUIRED_DEFAULTS)
    out["title"] = clean_text(str(raw.get("title", "")), limit=200) or "Untitled"
    out["summary"] = clean_text(str(raw.get("summary", "")), limit=400)
    metadata = raw.get("metadata")
    out["metadata"] = dict(metadata) if isinstance(metadata, dict) else {}
    out["metadata"].setdefault("feed_title", out["title"])
    out["metadata"].setdefault("feed_description", clean_text(str(raw.get("summary", "")), limit=8000))
    out["metadata"].setdefault("field_sources", {"feed_title": "source_title", "feed_description": "source_summary"})
    out["modified"] = to_iso_utc(raw.get("modified"))
    out["published_kind"] = raw.get("published_kind", "published" if raw.get("published") else "unknown")
    out["url"] = str(raw.get("url", ""))
    out["source"] = str(source_meta.get("name", raw.get("source", "Unknown")))
    out["source_type"] = str(source_meta.get("source_type", "api"))
    try:
        out["authority"] = int(source_meta.get("authority", 2))
    except Exception:
        out["authority"] = 2
    out["authority"] = min(max(out["authority"], 1), 3)
    out["category"] = str(raw.get("category", source_meta.get("category", "news")))
    pub = to_iso_utc(raw.get("published") or raw.get("event_date_utc") or "")
    out["published"] = pub
    out["freshness_h"] = freshness_hours(pub)
    out["freshness_display"] = freshness_display(out["freshness_h"])
    out["entities"] = list(raw.get("entities", []) or [])[:10]
    out["location"] = raw.get("location")
    out["event_type"] = raw.get("event_type")
    date_only = bool(raw.get("date_only"))
    out["date_only"] = date_only
    out["precision"] = raw.get("precision", "day" if date_only else "unspecified")
    out["event_date"] = (str(raw.get("event_date", ""))[:10] or None) if date_only else (to_iso_utc(raw.get("event_date")) or None)
    out["event_date_utc"] = None if date_only else (to_iso_utc(raw.get("event_date_utc") or raw.get("event_date")) or None)
    out["event_end_utc"] = to_iso_utc(raw.get("event_end_utc")) or None
    out["visibility"] = raw.get("visibility")
    out["visibility_url"] = raw.get("visibility_url")
    out["authors"] = list(raw.get("authors", []) or [])[:5]
    extra = raw.get("extra", {})
    out["extra"] = extra if isinstance(extra, dict) else {"value": extra}
    return out
