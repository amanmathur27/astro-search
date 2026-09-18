"""Narrow extractive evidence checks, not a general semantic truth verifier."""
from __future__ import annotations
import math
import re
from urllib.parse import urlsplit
from .interpretation import phrase

LABELS = {"launch_mass": r"launch (?:mass|weight)", "dry_mass": r"dry (?:mass|weight)",
          "mirror_diameter": r"(?:primary )?mirror diameter"}
UNITS = {"launch_mass": r"kg|kilograms?|tonnes?|lb|pounds?",
         "dry_mass": r"kg|kilograms?|tonnes?|lb|pounds?",
         "mirror_diameter": r"m|meters?|metres?|cm|centimeters?|centimetres?"}
FACTORS = {"kg": 1, "kilogram": 1, "kilograms": 1, "tonne": 1000, "tonnes": 1000,
           "lb": .45359237, "pound": .45359237, "pounds": .45359237,
           "m": 1, "meter": 1, "meters": 1, "metre": 1, "metres": 1,
           "cm": .01, "centimeter": .01, "centimeters": .01, "centimetre": .01, "centimetres": .01}


def primary_url(url):
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        return (parsed.scheme == "https" and not parsed.username and not parsed.password
                and any(host == domain or host.endswith("." + domain) for domain in ("nasa.gov", "esa.int")))
    except ValueError:
        return False


def inspect_evidence(row, spec):
    """Require explicit subject + exact property + affirmative value in one clause.

    Title/summary matches are discovery only. No inferred table relationships,
    broad plausibility thresholds, assumed source authority, or nearby numbers.
    Structured archive records follow a stricter, separate path: the archive must
    itself have resolved the requested identifier and published a usable value.
    """
    extra = row.get("extra") or {}
    evidence = {"status": "irrelevant", "property": spec.property,
                "subject": spec.subject, "content_trust": "untrusted_external"}
    archive = extra.get("archive_record")
    if isinstance(archive, dict):
        return _archive_evidence(archive, spec, evidence)
    text = extra.get("document_text", "")
    url = extra.get("document_url", row.get("url", ""))
    blob = " ".join(str(row.get(k) or "") for k in ("title", "summary")) + " " + str(text)
    if not any(phrase(a, blob) for a in spec.aliases):
        return evidence
    evidence["status"] = "indirect"
    if (not isinstance(text, str) or not text or spec.property not in {*LABELS, "launch_date"}
            or not primary_url(url) or extra.get("document_truncated")
            or not extra.get("document_fetch_ok")):
        return evidence
    number = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    subject = "(?:" + "|".join(re.escape(a) for a in sorted(spec.aliases, key=len, reverse=True)) + ")"
    if spec.property == "launch_date":
        from datetime import datetime
        from .timeparse import reference_time
        month = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        date_pattern = month + r" \d{1,2}, \d{4}|\d{1,2} " + month + r" \d{4}|\d{4}-\d{2}-\d{2}"
        pattern = re.compile(r"(?:^|[.!?;]\s+)(?P<quote>(?:The\s+)?" + subject
                             + r"\s+(?:was\s+)?launched\s+on\s+(?P<value>" + date_pattern
                             + r"))(?=\s*\.(?:\s|$)|\s*$)", re.I)
        matches = []
        for match in pattern.finditer(text):
            parsed = None
            for fmt in ("%B %d, %Y", "%d %B %Y", "%Y-%m-%d"):
                try:
                    parsed = datetime.strptime(match.group("value"), fmt).date()
                    break
                except ValueError:
                    pass
            # A completed launch cannot occur after this document's retrieval.
            if parsed is None or not extra.get("retrieved_at"):
                continue
            if parsed > reference_time(extra["retrieved_at"]).date():
                continue
            matches.append({"quote": match.group("quote"), "value": parsed.isoformat(),
                            "unit": "date", "normalized_value": parsed.toordinal(),
                            "method": "primary_source", "reference": url, "uncertainty": None})
        if matches:
            evidence.update(status="direct_evidence", citation_url=url,
                            retrieved_at=extra.get("retrieved_at"), measurements=matches,
                            verification="explicit completed-launch statement; not independently certified")
        return evidence
    # Sentence/clause boundaries prevent binding another object's measurement.
    pattern = re.compile(
        r"(?:^|[.!?;]\s+)(?P<quote>(?:The\s+)?" + subject
        + r"(?:['’]s\s+|\s+has\s+(?:a\s+)?|\s+)"
        + LABELS[spec.property] + r"\s*(?:is\s+|of\s+|:\s*)"
        + r"(?P<value>" + number + r")\s*(?P<unit>" + UNITS[spec.property]
        + r")(?=\s*[.;](?:\s|$)|\s*$))", re.I)
    matches = []
    for match in pattern.finditer(text):
        value = float(match.group("value").replace(",", ""))
        if value <= 0:
            continue
        unit = match.group("unit").lower()
        matches.append({"quote": match.group("quote"), "value": value, "unit": unit,
                        "normalized_value": value * FACTORS[unit],
                        "method": "primary_source", "reference": url, "uncertainty": None})
    if matches:
        evidence.update(status="direct_evidence", citation_url=url,
                        retrieved_at=extra.get("retrieved_at"), measurements=matches,
                        verification="explicit_primary_source_statement; not independently certified")
    return evidence


def _archive_evidence(archive, spec, evidence):
    """A structured archive record is direct evidence only when the archive itself
    resolved the requested identifier and published a usable value with a reference.

    No text proximity, no unit conversion, no merging of alternate determinations.
    """
    if archive.get("property") != spec.property:
        return evidence
    matched = archive.get("matched_identifier")
    if not isinstance(matched, str) or not matched.strip():
        return evidence
    identifiers = {str(a).strip().lower() for a in (spec.aliases or []) if str(a).strip()}
    if spec.subject:
        identifiers.add(str(spec.subject).strip().lower())
    if matched.strip().lower() not in identifiers:
        return evidence
    for field in ("catalog", "record_id", "unit", "reference"):
        if not isinstance(archive.get(field), str) or not archive[field].strip():
            return evidence
    value = archive.get("value")
    if archive.get("value_kind", "numeric") == "numeric":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return evidence
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            return evidence
        if not math.isfinite(normalized):
            return evidence
    else:
        if not isinstance(value, str) or not value.strip():
            return evidence
        normalized = None
    quote = archive.get("quote")
    if not isinstance(quote, str) or not quote.strip():
        return evidence
    verification = (f"{archive['catalog']} published this value for {archive['record_id']} with "
                    f"reference {archive['reference']}; this is an archive record, not an "
                    f"independent certification by this engine.")
    if archive.get("retraction_declared"):
        verification += " The registration record declares a retraction; check the notice."
    evidence.update(status="direct_evidence", citation_url=archive["reference"],
                    retrieved_at=archive.get("retrieved_at"), content_trust="archive_record",
                    measurements=[{"quote": quote.strip(), "value": value, "unit": archive["unit"],
                                   "normalized_value": normalized,
                                   "uncertainty": archive.get("uncertainty"),
                                   "reference": archive["reference"], "method": "archive_record",
                                   "catalog": archive["catalog"], "record_id": archive["record_id"],
                                   "band": archive.get("band"),
                                   "alternate_determinations": archive.get("alternate_determinations")}],
                    verification=verification)
    if archive.get("uncertainty") is None and archive.get("uncertainty_note"):
        evidence["uncertainty_note"] = archive["uncertainty_note"]
    return evidence


def filter_evidence(rows, spec):
    direct = []
    for row in rows:
        ev = inspect_evidence(row, spec)
        if ev["status"] == "direct_evidence":
            row = dict(row)
            row["evidence"] = ev
            # Do not expose unrelated article prose as the answer summary.
            row["summary"] = ev["measurements"][0]["quote"]
            direct.append(row)
    # Only finite numeric measurements can conflict; categorical catalog values cannot.
    values = [m["normalized_value"] for r in direct for m in r["evidence"]["measurements"]
              if isinstance(m.get("normalized_value"), (int, float))
              and not isinstance(m["normalized_value"], bool)]
    conflict = bool(values) and max(values) - min(values) > max(abs(v) for v in values) * 1e-6
    return direct, "conflicting_evidence" if conflict else ("answered" if direct else "not_found")
