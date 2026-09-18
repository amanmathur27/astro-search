"""GCN Circulars: modern machine-readable access to NASA's GCN archive.

GCN replaced the frozen legacy archive with per-circular JSON/text exports.
Circulars are rapid reports, not peer-reviewed publications. Detection and
matching are conservative and exact-id based; parsing never invents fields.
"""
from __future__ import annotations
import re
from .relevance import tokens

PROVIDER = re.compile(r"\b(?:gcn|gcn\s+circulars?)\b", re.I)
CIRCULAR = re.compile(r"\bcirculars?\b", re.I)
VETO = re.compile(r"\b(?:papers?|arxiv|preprints?|journals?|explain|define)\b|\bwhat (?:is|are)\b", re.I)
# "Circular 45525", "GCN Circular #45525", "circular 45525"
IDENTIFIER = re.compile(r"\bcircular\s*#?\s*(\d{1,6})\b", re.I)
TRANSIENT = re.compile(
    r"\b(?:grb|gamma[ -]?ray bursts?|gravitational[ -]?waves?|gw|neutrinos?|sgr|frb|tde|"
    r"fermi|swift|chime|lvk|icecube|localization|transients?)\b", re.I)
SCOPE = re.compile(
    r"\b(?:astronom\w*|astrophys\w*|space|telescope|sky|burst|neutron star|black hole|"
    r"supernova\w*|afterglow|x-ray|optical follow)\b", re.I)
# Vocabulary that identifies the GCN provider even without the acronym.
GCN_SPECIFIC = re.compile(r"\b(?:gbm|barycenter|trigger|localization|circular)\b", re.I)
LIST_ITEM = re.compile(
    r'<li[^>]*\bvalue="(?P<value>\d+)"[^>]*>\s*<a[^>]*href="/circulars/(?P<id>\d+)"[^>]*>(?P<subject>.*?)</a>',
    re.S | re.I)
TAGS = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def is_gcn_query(query) -> bool:
    """True only for explicit GCN/circular requests, not generic news."""
    q = query or ""
    if VETO.search(q):
        return False
    if PROVIDER.search(q):
        return True
    if CIRCULAR.search(q) and (TRANSIENT.search(q) or SCOPE.search(q)):
        return True
    # Strong GCN-only vocabulary plus a transient context; a bare "GRB follow-up"
    # request stays with the default rapid-report provider.
    return bool(TRANSIENT.search(q) and GCN_SPECIFIC.search(q))


def circular_id(query) -> str | None:
    match = IDENTIFIER.search(query or "")
    return match.group(1) if match else None


def report_matches(query, subject, body="") -> bool:
    """Exact circular id when supplied, otherwise all residual content terms."""
    ident = circular_id(query)
    if ident:
        found = IDENTIFIER.search(subject or "")
        return bool(found and found.group(1) == ident)
    blob = f"{subject or ''} {body or ''}"
    residual = IDENTIFIER.sub("", query or "")
    residual = re.sub(r"\b(?:gcn|circulars?|latest|recent|new|news|updates?|list|about|"
                      r"please|find|show)\b", "", residual, flags=re.I)
    return tokens(residual) <= tokens(blob)


def parse_list(html_text) -> list[dict]:
    """Parse the server-rendered /circulars list into id/subject/url records."""
    entries, seen = [], set()
    for match in LIST_ITEM.finditer(html_text or ""):
        ident = match.group("id")
        subject = WS.sub(" ", TAGS.sub("", match.group("subject"))).strip()
        if not ident.isdigit() or not subject or ident in seen:
            continue
        seen.add(ident)
        entries.append({"circular_id": ident, "subject": subject,
                        "url": f"https://gcn.nasa.gov/circulars/{ident}"})
    return entries


def parse_circular(payload) -> dict | None:
    """Validate a /circulars/{id}.json payload; never guess missing fields."""
    if not isinstance(payload, dict):
        return None
    ident = payload.get("circularId")
    subject = payload.get("subject")
    if not isinstance(ident, int) or isinstance(ident, bool) or ident <= 0:
        return None
    if not isinstance(subject, str) or not subject.strip():
        return None
    created = payload.get("createdOn")
    published = ""
    if isinstance(created, (int, float)) and not isinstance(created, bool) and created > 0:
        from datetime import datetime, timezone
        try:
            published = datetime.fromtimestamp(created / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        except (OverflowError, OSError, ValueError):
            published = ""
    body = payload.get("body")
    return {"circular_id": str(ident), "subject": subject.strip(),
            "body": body.strip() if isinstance(body, str) else "",
            "bibcode": payload.get("bibcode") if isinstance(payload.get("bibcode"), str) else None,
            "event_id": payload.get("eventId") if isinstance(payload.get("eventId"), str) else None,
            "submitter": payload.get("submitter") if isinstance(payload.get("submitter"), str) else None,
            "published": published,
            "url": f"https://gcn.nasa.gov/circulars/{ident}"}
