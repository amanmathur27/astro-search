"""DOI detection and Crossref registration-metadata validation (no network here).

Crossref is the DOI registration agency for most astronomy publishers, so its
deposited metadata is authoritative for *bibliographic* fields (title, journal,
issue date, DOI). It is not evidence about a paper's scientific claims, and
retraction/correction status is reported only when the record declares it.
"""
from __future__ import annotations
import re

DOI_PATTERN = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)
CROSSREF = "https://api.crossref.org/works/{doi}"
TRAILING = ".,;:)]}>\"'"
# DOI registrants whose records are handled as astronomy literature.
ASTRO_HINTS = re.compile(
    r"\b(?:astro|apj|apjl|aj|mnras|aap|aj|icarus|jgr|pasp|phys|nature|science|"
    r"aanda|apjletters|psj|apss|solphys|grasp)\b", re.I)


def extract_doi(query) -> str | None:
    """Return a normalized DOI from free text, stripping trailing punctuation."""
    match = DOI_PATTERN.search(query or "")
    if not match:
        return None
    doi = match.group(1).rstrip(TRAILING)
    # A DOI must keep at least one character after the prefix slash.
    return doi if len(doi.split("/", 1)[1]) >= 2 else None


def is_doi_query(query) -> bool:
    """An explicit DOI is a self-identifying request for its registration metadata."""
    return extract_doi(query) is not None


def record_to_archive(message, doi) -> dict | None:
    """Convert a Crossref ``message`` into the shared archive-record contract."""
    if not isinstance(message, dict):
        return None
    returned = message.get("DOI")
    if not isinstance(returned, str) or returned.strip().lower() != doi.lower():
        return None
    titles = message.get("title") or []
    title = next((t for t in titles if isinstance(t, str) and t.strip()), None)
    if not title:
        return None
    containers = message.get("container-title") or []
    journal = next((c for c in containers if isinstance(c, str) and c.strip()), None)
    issued = message.get("issued") or message.get("published") or {}
    parts = issued.get("date-parts") if isinstance(issued, dict) else None
    date_parts = parts[0] if isinstance(parts, list) and parts and isinstance(parts[0], list) else []
    date = None
    if date_parts and all(isinstance(p, int) and not isinstance(p, bool) for p in date_parts):
        date = "-".join(f"{p:02d}" if i else f"{p:04d}" for i, p in enumerate(date_parts[:3]))
    authors = []
    for author in (message.get("author") or [])[:12]:
        if isinstance(author, dict):
            name = author.get("name") or " ".join(
                part for part in (author.get("given"), author.get("family")) if isinstance(part, str))
            if isinstance(name, str) and name.strip():
                authors.append(name.strip())
    updates = message.get("update-to") or []
    retraction = [u for u in updates if isinstance(u, dict)
                  and isinstance(u.get("type"), str) and "retract" in u["type"].lower()]
    return {"catalog": "Crossref registration metadata", "record_id": returned.strip(),
            "matched_identifier": doi.lower(), "property": "doi_metadata",
            "value": returned.strip(), "unit": "DOI", "value_kind": "identifier",
            "reference": CROSSREF.format(doi=returned.strip()),
            "uncertainty": None,
            "uncertainty_note": "Registration metadata is deposited by the publisher; "
                                "it carries no measurement uncertainty.",
            "journal": journal, "issued": date, "type": message.get("type"),
            "publisher": message.get("publisher"), "authors": authors,
            "volume": message.get("volume"), "page": message.get("page"),
            "cited_by": message.get("is-referenced-by-count"),
            "reference_count": message.get("reference-count"),
            "declared_updates": [u.get("type") for u in updates if isinstance(u, dict)
                                 and isinstance(u.get("type"), str)][:5],
            "retraction_declared": bool(retraction),
            "quote": (f"DOI {returned.strip()} is registered to “{title}”"
                      + (f" in {journal}" if journal else "")
                      + (f", issued {date}" if date else "")
                      + (f" by {', '.join(authors[:3])}" if authors else "") + ".")}