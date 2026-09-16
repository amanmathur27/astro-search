"""Enforces output contract. Never raises KeyError downstream. Stdlib + dateutil only."""
from __future__ import annotations
import html
import re
from datetime import datetime, timezone
from dateutil import parser as dateparser

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
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
        dt = dateparser.parse(value)
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def freshness_hours(published_iso: str) -> int | None:
    if not published_iso:
        return None
    try:
        dt = dateparser.parse(published_iso)
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
        h = int(delta.total_seconds() // 3600)
        return max(h, 0)
    except Exception:
        return None


def normalize(raw: dict, source_meta: dict) -> dict:
    """Merge raw + source_meta into strict contract (handoff §4 + supplement §5)."""
    if not isinstance(raw, dict):
        raw = {}
    if not isinstance(source_meta, dict):
        source_meta = {}
    out: dict = dict(REQUIRED_DEFAULTS)
    out["title"] = clean_text(str(raw.get("title", "")), limit=200) or "Untitled"
    out["summary"] = clean_text(str(raw.get("summary", "")), limit=400)
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
    out["entities"] = list(raw.get("entities", []) or [])[:10]
    out["location"] = raw.get("location")
    out["event_type"] = raw.get("event_type")
    out["event_date"] = to_iso_utc(raw.get("event_date")) or None
    # Supplement §5 precision fields (additive)
    out["event_date_utc"] = to_iso_utc(raw.get("event_date_utc") or raw.get("event_date")) or None
    out["event_end_utc"] = to_iso_utc(raw.get("event_end_utc")) or None
    out["visibility"] = raw.get("visibility")
    out["visibility_url"] = raw.get("visibility_url")
    out["authors"] = list(raw.get("authors", []) or [])[:5]
    extra = raw.get("extra", {})
    out["extra"] = extra if isinstance(extra, dict) else {"value": extra}
    return out
