"""MPC ingestion: MPEC listing/parsing, orbital elements, bounded astrometry.

Verified 2026-09-18 against the live services:
  * ``/mpec/RecentMPECs.html`` and ``/mpec/Kyy/KyyLnn.html`` pages are reachable
    and list up to 100 recent MPECs with issue dates and designations.
  * ``data.minorplanetcenter.net/api/get-obs`` answers a GET carrying a JSON body
    and returns MPC-80 astrometry for explicit designations.

MPEC element blocks publish no formal uncertainties, so none are invented here.
Asteroid/comet designations and elements are archival records, not measurements
this engine has independently verified.
"""
from __future__ import annotations
import re
from .relevance import tokens

BASE = "https://www.minorplanetcenter.net"
LIST_URL = BASE + "/mpec/RecentMPECs.html"
OBS_API = "https://data.minorplanetcenter.net/api/get-obs"

PROVIDER = re.compile(r"\b(?:mpec|mpecs|minor planet center|minorplanet center|mpc)\b", re.I)
VETO = re.compile(r"\b(?:papers?|arxiv|preprints?|journals?|explain|define)\b|\bwhat (?:is|are)\b", re.I)
SUBJECT = re.compile(r"\b(?:orbital elements?|astrometry|observations?|neo\b|near[ -]earth|"
                     r"minor planets?|asteroids?|comets?|neocp|confirmation page)\b", re.I)
ELEMENTS_REQUEST = re.compile(r"\b(?:orbital elements?|elements?|orbit)\b", re.I)
OBSERVATION_REQUEST = re.compile(r"\b(?:observations?|astrometry|astrometric|measurements?)\b", re.I)
MPEC_ID = re.compile(r"\bmpec\s+(\d{4})-([A-Z])\s?(\d{1,3})\b", re.I)
PROVISIONAL = re.compile(r"\b((?:19|20)\d{2}\s?[A-Z]{1,2}\d{0,3})\b")
COMET = re.compile(r"\b([CPD]/\s?(?:19|20)\d{2}\s?[A-Z]\d{0,2})\b", re.I)
LIST_ENTRY = re.compile(
    r'href="(?P<href>/mpec/K\d{2}/K\d{2}[A-Z]\d{2,3}\.html)">\s*<i>MPEC</i>\s*'
    r'(?P<identifier>\d{4}-[A-Z]\s?\d{1,3})</a>\s*\((?P<issued>[^)]+)\)', re.I)
LIST_SUBJECT = re.compile(r"<li>\s*([^<>]{2,60}?)\s*(?:</ul>|<li>|$)", re.I)
TAGS = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")
MONTHS = {name: index for index, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"), start=1)}

# Element fields published in MPEC blocks, with the unit each carries.
ELEMENT_UNITS = {"epoch_jd": "TT Julian date", "mean_anomaly_deg": "deg",
                 "argument_of_perihelion_deg": "deg", "longitude_of_node_deg": "deg",
                 "inclination_deg": "deg", "eccentricity": "dimensionless",
                 "semi_major_axis_au": "AU", "mean_motion_deg_day": "deg/day",
                 "orbital_period_years": "years", "absolute_magnitude_h": "mag",
                 "slope_parameter_g": "dimensionless", "earth_moid_au": "AU",
                 "perihelion_time_tt": "TT calendar", "perihelion_distance_au": "AU"}


def is_mpec_query(query) -> bool:
    q = query or ""
    if VETO.search(q):
        return False
    if MPEC_ID.search(q):
        return True
    if PROVIDER.search(q):
        return True
    # an explicit minor-body designation plus an MPC-specific request
    return bool((PROVISIONAL.search(q) or COMET.search(q))
                and (SUBJECT.search(q) or ELEMENTS_REQUEST.search(q)))


def mpec_request(query) -> dict:
    """Return the requested MPEC identifier/URL and any explicit designation."""
    match = MPEC_ID.search(query or "")
    request = {"identifier": None, "url": None, "designation": None,
               "wants_elements": bool(ELEMENTS_REQUEST.search(query or "")),
               "wants_observations": bool(OBSERVATION_REQUEST.search(query or ""))}
    if match:
        year, letter, number = match.group(1), match.group(2).upper(), int(match.group(3))
        short = f"K{int(year) % 100:02d}{letter}{number:02d}"
        request["identifier"] = f"{year}-{letter}{number:02d}"
        request["url"] = f"{BASE}/mpec/K{int(year) % 100:02d}/{short}.html"
    body = COMET.search(query or "") or PROVISIONAL.search(query or "")
    if body:
        request["designation"] = WS.sub(" ", body.group(1)).strip()
    return request


def list_matches(query, identifier, subjects) -> bool:
    """Exact MPEC identifier when supplied, otherwise residual content terms."""
    request = mpec_request(query)
    wanted = request["identifier"]
    if wanted:
        return WS.sub("", (identifier or "")).upper() == WS.sub("", wanted).upper()
    residual = MPEC_ID.sub("", query or "")
    residual = re.sub(r"\b(?:mpecs?|minor planet center|minorplanet center|mpc|latest|recent|new|"
                      r"list|show|find|about|orbital elements?|elements?|observations?|astrometry)\b",
                      "", residual, flags=re.I)
    return tokens(residual) <= tokens(" ".join(subjects or []))


def parse_mpec_list(html_text) -> list[dict]:
    """Parse the 100-entry recent-MPEC list, keeping issue dates and subjects."""
    text = html_text or ""
    matches = list(LIST_ENTRY.finditer(text))
    entries = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        window = text[match.end():end]
        subjects = [WS.sub(" ", TAGS.sub("", item)).strip()
                    for item in LIST_SUBJECT.findall(window)]
        issued = WS.sub(" ", match.group("issued")).strip()
        date = re.match(r"(\d{4})\s+([A-Za-z]+)\s+(\d{1,2})", issued)
        entries.append({
            "identifier": WS.sub(" ", match.group("identifier")).strip(),
            "url": BASE + match.group("href"),
            "issued": (f"{date.group(1)}-{MONTHS[date.group(2).title()]:02d}-{int(date.group(3)):02d}"
                       if date and date.group(2).title() in MONTHS else None),
            "designations": [s for s in subjects if s and s.lower() != "and"][:10]})
    return entries


def parse_elements(text) -> dict | None:
    """Parse an MPEC orbital-element block; return None unless several fields match."""
    blob = WS.sub(" ", text or "")
    if "Orbital elements" not in blob:
        return None
    fields: dict = {}
    patterns = {
        "mean_anomaly_deg": r"\bM\s+(-?\d{1,3}\.\d+)\b",
        "mean_motion_deg_day": r"\bn\s+(\d+\.\d+)\b",
        "argument_of_perihelion_deg": r"\bPeri\.\s*(-?\d{1,3}\.\d+)\b",
        "longitude_of_node_deg": r"\bNode\s+(-?\d{1,3}\.\d+)\b",
        "inclination_deg": r"\bIncl\.\s*(-?\d{1,3}\.\d+)\b",
        "semi_major_axis_au": r"\ba\s+(\d+\.\d+)\b",
        "eccentricity": r"\be\s+(\d+\.\d+)\b",
        "orbital_period_years": r"\bP\s+(\d+\.\d+)\b",
        "absolute_magnitude_h": r"\bH\s+(\d+\.\d+)\b",
        "slope_parameter_g": r"\bG\s+(\d+\.\d+)\b",
        "perihelion_distance_au": r"\bq\s+(\d+\.\d+)\b",
    }
    for key, pattern in patterns.items():
        found = re.search(pattern, blob)
        if not found:
            continue
        try:
            fields[key] = float(found.group(1))
        except ValueError:
            continue
    epoch = re.search(r"Epoch\s+(\d{4})\s+([A-Z][a-z]{2})\.?\s+(\d+(?:\.\d+)?)\s+TT\s*=\s*JDT\s+(\d+\.\d+)", blob)
    if epoch:
        fields["epoch"] = f"{epoch.group(1)} {epoch.group(2)} {epoch.group(3)} TT"
        try:
            fields["epoch_jd"] = float(epoch.group(4))
        except ValueError:
            pass
    moid = re.search(r"Earth MOID\s*=\s*(\d+\.\d+)\s*AU", blob)
    if moid:
        try:
            fields["earth_moid_au"] = float(moid.group(1))
        except ValueError:
            pass
    perihelion = re.search(r"\bT\s+(\d{4}\s+[A-Z][a-z]{2}\.?\s+\d+\.\d+)\s+TT", blob)
    if perihelion:
        fields["perihelion_time_tt"] = WS.sub(" ", perihelion.group(1))
    designation = (re.search(r"Orbital elements:\s*(.+?)\s+(?:Earth MOID|Epoch)", blob)
                   or re.search(r"Orbital elements:\s*(\S+)", blob))
    if len([k for k in fields if k in ELEMENT_UNITS]) < 3:
        return None
    return {"designation": designation.group(1) if designation else None,
            "fields": fields,
            "units": {k: ELEMENT_UNITS[k] for k in fields if k in ELEMENT_UNITS},
            "uncertainty": None,
            "uncertainty_note": "MPEC element blocks publish no formal uncertainties."}


def parse_observations(payload, limit: int = 40) -> dict:
    """Parse MPC-80 astrometry defensively; non-conforming lines are skipped."""
    lines: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, str):
                        lines.extend(value.splitlines())
    observations, skipped = [], 0
    for line in lines:
        if len(line) < 56:
            skipped += 1
            continue
        # MPC 80-column layout: date cols 16-32, RA 33-44, Dec 45-56,
        # magnitude 66-70, band 71, observatory code 78-80.
        date = re.match(r"(\d{4}) (\d{2}) (\d{2}\.\d+)", line[15:32])
        ra = re.match(r"(\d{2}) (\d{2}) (\d{2}\.\d+)", line[32:44])
        dec = re.match(r"([+-])(\d{2}) (\d{2}) (\d{2}\.\d+)", line[44:56])
        if not (date and ra and dec):
            skipped += 1
            continue
        try:
            hours, minutes, seconds = int(ra.group(1)), int(ra.group(2)), float(ra.group(3))
            degrees, arcmin, arcsec = int(dec.group(2)), int(dec.group(3)), float(dec.group(4))
        except ValueError:
            skipped += 1
            continue
        if hours > 23 or minutes > 59 or seconds >= 60 or degrees > 90 or arcmin > 59 or arcsec >= 60:
            skipped += 1
            continue
        sign = -1 if dec.group(1) == "-" else 1
        magnitude = None
        if len(line) >= 70:
            found = re.match(r"\s*(\d{2}\.\d)", line[65:70])
            if found:
                try:
                    magnitude = float(found.group(1))
                except ValueError:
                    magnitude = None
        band = line[70] if len(line) >= 71 and line[70].isalpha() else None
        observations.append({
            "raw": line[:80].rstrip(),
            "date_utc": f"{date.group(1)}-{date.group(2)}-{date.group(3)}",
            "date_fraction": round(float(date.group(3)) - int(float(date.group(3))), 6),
            "ra_hms": f"{ra.group(1)}h{ra.group(2)}m{ra.group(3)}s",
            "dec_dms": f"{dec.group(1)}{dec.group(2)}d{dec.group(3)}m{dec.group(4)}s",
            "ra_deg": round((hours + minutes / 60 + seconds / 3600) * 15, 6),
            "dec_deg": round(sign * (degrees + arcmin / 60 + arcsec / 3600), 6),
            "magnitude": magnitude,
            "band": band,
            "observation_type": line[14] if len(line) >= 15 and not line[14].isspace() else None,
            "observatory_code": (line[77:80].strip() or None) if len(line) >= 80 else None,
            "provider_reference_field": (line[71:77].strip() or None) if len(line) >= 77 else None,
        })
        if len(observations) >= limit:
            break
    return {"observations": observations, "parsed": len(observations), "skipped": skipped,
            "format": "MPC 80-column", "truncated": len(observations) >= limit,
            "uncertainty_note": "MPC-80 lines carry no per-observation uncertainty.",
            "time_note": "Provider timestamps are UTC; only the calendar day and the "
                         "fractional day are exposed, without converting to a precise instant."}