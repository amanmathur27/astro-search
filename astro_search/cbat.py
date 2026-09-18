"""CBAT (IAU Central Bureau for Astronomical Telegrams) bounded ingestion.

Transport reality (verified 2026-09-18): the CBAT host completes no TLS
handshake, so only plaintext HTTP is reachable. Its RSS feeds answer 401
(subscription-only) and the TOCP Atom feed is ~8 MB, so neither is used here.
CBETs and the recent-supernova list are rapid reports, not peer-reviewed data.
"""
from __future__ import annotations
import re
from .relevance import tokens

HOST = "http://www.cbat.eps.harvard.edu"
CBET_LIST = HOST + "/cbet/RecentCBETs.html"
SUPERNOVA_LIST = HOST + "/lists/RecentSupernovae.html"
TRANSPORT = "plaintext_http"
TLS_STATUS = "handshake_failed"

PROVIDER = re.compile(r"\b(?:cbat|cbets?|iaucs?|central bureau|astronomical telegrams?)\b", re.I)
VETO = re.compile(r"\b(?:papers?|arxiv|preprints?|journals?|explain|define)\b|\bwhat (?:is|are)\b", re.I)
TRANSIENT = re.compile(
    r"\b(?:supernova\w*|sn\s?\d{4}|nova\w*|comets?|cbet\s*\d+|iauc\s*\d+|"
    r"meteor outburst|transient object)\b", re.I)
CBET_NUMBER = re.compile(r"\b(?:cbet|iauc)\s*#?\s*(\d{3,5})\b", re.I)
LIST_ITEM = re.compile(
    r"<li>\s*CBET\s+(?P<number>\d{3,5})\s*:\s*(?P<date>\d{8})\s*:\s*"
    r'<a[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.S | re.I)
SN_ANCHOR = re.compile(
    r'<a name="(?P<name>[^"]+)">.*?</a>(?P<tail>.*?)(?=<a name="|</pre>)', re.S | re.I)
TAGS = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def is_cbat_query(query) -> bool:
    q = query or ""
    if VETO.search(q):
        return False
    if PROVIDER.search(q):
        return True
    # "recent supernovae" / "latest CBETs" style browsing needs transient wording.
    return bool(TRANSIENT.search(q) and re.search(r"\b(?:latest|recent|new|list|reports?|circulars?|discover\w*)\b", q, re.I))


def cbet_number(query) -> str | None:
    match = CBET_NUMBER.search(query or "")
    return match.group(1) if match else None


def list_matches(query, title) -> bool:
    """Exact CBET number when supplied, otherwise all residual content terms.

    A browse request with no content terms after stop-word stripping (e.g.
    "latest CBETs") matches the recent-list scope rather than no titles.
    """
    number = cbet_number(query)
    if number:
        return bool(re.search(r"\b0*" + re.escape(number) + r"\b", title or ""))
    cleaned = CBET_NUMBER.sub("", query or "")
    cleaned = re.sub(r"\b(?:cbat|cbets?|iaucs?|central bureau|astronomical telegrams|latest|recent|"
                      r"new|list|lists|reports?|circulars?|discover\w*|about|please|show|find)\b", "", cleaned, flags=re.I)
    residual = tokens(cleaned)
    residual -= {"sn", "supernova", "supernovae"}
    if not residual:
        return True  # generic CBET browsing: the recent list itself is the scope
    return residual <= tokens(title or "")


def parse_cbet_list(html_text) -> list[dict]:
    """Parse the recent-CBET list; the provider markup is a flat <li> sequence."""
    entries = []
    for match in LIST_ITEM.finditer(html_text or ""):
        raw_date = match.group("date")
        title = WS.sub(" ", TAGS.sub("", match.group("title"))).strip()
        href = match.group("href")
        if not title or not href.startswith("/"):
            continue
        entries.append({"cbet_number": match.group("number"),
                        "issued": f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}",
                        "title": title, "url": HOST + href})
    return entries


def parse_supernova_list(html_text) -> list[dict]:
    """Parse only confidently matched recent-supernova rows; never guess fields."""
    entries = []
    for match in SN_ANCHOR.finditer(html_text or ""):
        name = match.group("name")
        if not re.fullmatch(r"(?:19|20)\d{2}[A-Za-z]{1,3}|SN\s?\d{4}[A-Za-z]*", name):
            continue
        tail = WS.sub(" ", TAGS.sub(" ", match.group("tail")))
        date = re.search(r"\b((?:19|20)\d{2})\s+(\d{2})\s+(\d{2})\b", tail)
        if not date:
            continue
        # Column layout after tag-stripping: "... YYYY MM DD RAh RAm DecD DecM
        # offsetE/W offsetN/S MAG ...". Splitting off the tag-stripped discovery
        # reference leaves "host YYYY MM DD RAh RAm ..." so the magnitude is the
        # last decimal token in that header, not the first (which can be RA).
        header, _, _ = tail.partition("CBET")
        header, _, _ = header.partition("IAUC")
        mags = re.findall(r"\b(\d{2}\.\d)\b", header)
        magnitude = mags[-1] if mags else None
        kind = re.search(r"\b(IIn|IIP|Ib/c|I[abc]n?|II[ab]?|Ibn?|Ic|Ia|Ib|II)\b", tail)
        host = tail.split(str(date.group(1)), 1)[0].strip()
        host = re.sub(r"^(?:19|20)\d{2}[A-Za-z]{1,3}\s*", "", host).strip()
        entries.append({"supernova": name,
                        "discovery_date": f"{date.group(1)}-{date.group(2)}-{date.group(3)}",
                        "host_galaxy": host[:60] or None,
                        "magnitude": float(magnitude) if magnitude else None,
                        "type": kind.group(1) if kind else None,
                        "url": f"{HOST}/lists/Supernovae.html"})
    return entries
