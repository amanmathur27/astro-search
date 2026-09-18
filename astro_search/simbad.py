"""SIMBAD TAP queries and archive-record construction (no network here).

SIMBAD is a reference archive: values carry the reference they came from. The
identifier is validated and string-interpolated into ADQL, so it is restricted to
a strict character set - no quotes, comment markers, or statement separators.
Uncertainties are only reported when the provider's error field is usable.
"""
from __future__ import annotations
import re

TAP = "https://simbad.u-strasbg.fr/simbad/sim-tap/sync"
SAFE = re.compile(r"^[A-Za-z0-9 +\-_./*()]{1,40}$")
CATALOG = re.compile(
    r"\b(?:HD|HIP|NGC|IC|SAO|TYC|BD|CD|CPD|2MASS|SDSS|UCAC|Gaia|WDS|PSR|GJ|Gliese|"
    r"Kepler|K2|TOI|WASP|HAT-P|TRAPPIST|Proxima)\s?[\dA-Za-z][\dA-Za-z\-. ]{0,20}\b"
    r"|\bV\s?\d[\dA-Za-z\-. ]{0,20}\b", re.I)
PROPER = re.compile(r"\b([A-Z][a-z]{3,}(?:\s+[A-Z][a-z]{3,})?)\b")
NOT_A_NAME = re.compile(
    r"\b(?:what|which|when|where|how|tell|give|show|find|please|star|stars|planet|planets|"
    r"galaxy|galaxies|magnitude|parallax|velocity|velocities|spectral|type|distance|far|current|"
    r"radial|latest|telescope|mission|nasa|esa|jwst|webb|hubble|roman|earth|solar|system)\b", re.I)
BAND = re.compile(r"\b([UBVRIJHK])\s*-\s*band\b|\bband\s+([UBVRIJHKGr])\b|\b([UBVRIJHK])(?:\s*-\s*)?magnitude\b", re.I)
DEFAULT_BAND = "V"

PROPERTIES = {
    "parallax": {"unit": "mas", "kind": "numeric",
                 "label": "trigonometric parallax",
                 "columns": "b.main_id, b.plx_value, b.plx_err, b.plx_bibcode"},
    "radial_velocity": {"unit": "km/s", "kind": "numeric",
                        "label": "radial velocity",
                        "columns": "b.main_id, b.rvz_radvel, b.rvz_err, b.rvz_bibcode"},
    "spectral_type": {"unit": "catalog value", "kind": "categorical",
                      "label": "MK spectral type",
                      "columns": "b.main_id, b.sp_type, b.sp_bibcode"},
    "object_type": {"unit": "catalog value", "kind": "categorical",
                    "label": "object type",
                    "columns": "b.main_id, b.otype_txt"},
}
FLUX_PROPERTY = {"magnitude": {"unit": "mag", "kind": "numeric",
                               "label": "apparent magnitude"}}
DISTANCE_PROPERTY = {"stellar_distance": {"kind": "numeric", "label": "distance"}}
SUPPORTED = tuple(PROPERTIES) + tuple(FLUX_PROPERTY) + tuple(DISTANCE_PROPERTY)
JOIN = " JOIN ident AS i ON b.oid = i.oidref"


def safe_identifier(text) -> str | None:
    cleaned = " ".join(str(text or "").replace("\t", " ").split())
    return cleaned if SAFE.fullmatch(cleaned) else None


def candidate_identifier(query) -> str | None:
    """Extract a catalog designation or a proper name from free text; else None."""
    text = str(query or "")
    for match in CATALOG.finditer(text):
        candidate = safe_identifier(match.group(0))
        if candidate:
            return candidate
    for match in PROPER.finditer(text):
        if NOT_A_NAME.search(match.group(1)):
            continue
        candidate = safe_identifier(match.group(1))
        if candidate:
            return candidate
    return None


def requested_band(query) -> tuple[str, bool]:
    """Return (band, explicit). Only an explicit band sets explicit=True."""
    match = BAND.search(str(query or ""))
    if match:
        letter = next((g for g in match.groups() if g), None)
        if letter:
            return letter.upper(), True
    return DEFAULT_BAND, False


def build_query(prop: str, identifier: str, band: str = DEFAULT_BAND) -> str | None:
    safe = safe_identifier(identifier)
    if not safe or prop not in SUPPORTED:
        return None
    literal = "'" + safe + "'"
    if prop in PROPERTIES:
        return (f"SELECT {PROPERTIES[prop]['columns']} FROM basic AS b{JOIN} "
                f"WHERE i.id = {literal}")
    if prop in FLUX_PROPERTY:
        return (f"SELECT b.main_id, f.filter, f.flux, f.flux_err, f.bibcode FROM flux AS f"
                f" JOIN ident AS i ON f.oidref = i.oidref JOIN basic AS b ON b.oid = i.oidref"
                f" WHERE i.id = {literal} AND f.filter = '{band}'")
    return (f"SELECT b.main_id, d.dist, d.unit, d.minus_err, d.plus_err, d.method, d.bibcode"
            f" FROM mesDistance AS d JOIN ident AS i ON d.oidref = i.oidref"
            f" JOIN basic AS b ON b.oid = i.oidref WHERE i.id = {literal}")


def _number(value):
    import math
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _uncertainty(minus, plus, value) -> dict | None:
    """Report an uncertainty only when the provider error field is usable.

    SIMBAD sometimes carries placeholder errors (an observed row with -5 for a
    1.3 pc distance); those are dropped rather than presented as a real error.
    """
    usable = {}
    for key, raw in (("minus", minus), ("plus", plus)):
        error = _number(raw)
        if error is not None and 0 <= abs(error) < abs(value):
            usable[key] = abs(error)
    if not usable:
        return None
    if usable.get("minus") is not None and usable.get("minus") == usable.get("plus"):
        return {"value": usable["plus"], "kind": "symmetric"}
    return {**usable, "kind": "asymmetric"}


def _rows(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    metadata, data = payload.get("metadata"), payload.get("data")
    if not isinstance(metadata, list) or not isinstance(data, list):
        return []
    names = [m.get("name") for m in metadata if isinstance(m, dict)]
    if len(names) != len(metadata) or not all(isinstance(n, str) for n in names):
        return []
    rows = []
    for row in data:
        if isinstance(row, list) and len(row) == len(names):
            rows.append(dict(zip(names, row)))
    return rows


def record_from_payload(payload, prop: str, identifier: str, band: str = DEFAULT_BAND) -> dict | None:
    """Build the shared archive-record contract from a SIMBAD TAP response."""
    rows = _rows(payload)
    if not rows or prop not in SUPPORTED:
        return None
    if len({str(r.get("main_id")) for r in rows}) > 1:
        return None  # the identifier maps to more than one object: never choose one
    base = {"catalog": "SIMBAD (CDS)", "matched_identifier": identifier.lower(),
            "property": prop, "uncertainty": None}
    if prop in PROPERTIES:
        spec = PROPERTIES[prop]
        row = rows[0]
        if prop == "parallax":
            value, error, reference = _number(row.get("plx_value")), row.get("plx_err"), row.get("plx_bibcode")
        elif prop == "radial_velocity":
            value, error, reference = _number(row.get("rvz_radvel")), row.get("rvz_err"), row.get("rvz_bibcode")
        elif prop == "spectral_type":
            value, error, reference = row.get("sp_type"), None, row.get("sp_bibcode")
        else:
            value, error, reference = row.get("otype_txt"), None, None
        main_id = row.get("main_id")
        if not isinstance(main_id, str) or not main_id.strip():
            return None
        if spec["kind"] == "numeric":
            if value is None:
                return None
        elif not isinstance(value, str) or not value.strip():
            return None
        record_url = ("https://simbad.u-strasbg.fr/simbad/sim-id?Ident="
                      + str(main_id).strip().replace(" ", "%20"))
        record = {**base, "record_id": main_id.strip(), "value": value, "unit": spec["unit"],
                  "value_kind": spec["kind"], "reference": (reference or record_url),
                  "reference_is_catalog_record_url": not bool(reference),
                  "label": spec["label"],
                  "uncertainty": (_uncertainty(error, error, abs(value))
                                  if spec["kind"] == "numeric" and error is not None else None),
                  "uncertainty_note": ("SIMBAD publishes no uncertainty for this field in this table."
                                       if spec["kind"] == "numeric" and error is None else None)}
        record["quote"] = _quote(prop, record)
        return record
    if prop in FLUX_PROPERTY:
        row = rows[0]
        value, main_id = _number(row.get("flux")), row.get("main_id")
        actual = row.get("filter")
        if value is None or not isinstance(main_id, str) or not main_id.strip():
            return None
        if not isinstance(actual, str) or actual.strip().upper() != band.upper():
            return None  # never present a different filter's magnitude as the requested one
        reference = row.get("bibcode")
        if not isinstance(reference, str) or not reference.strip():
            return None
        record = {**base, "record_id": main_id.strip(), "value": value, "unit": "mag",
                  "value_kind": "numeric", "band": band.upper(), "label": "apparent magnitude",
                  "reference": reference,
                  "uncertainty": _uncertainty(row.get("flux_err"), row.get("flux_err"), abs(value))}
        record["quote"] = _quote(prop, record)
        return record
def _distance_record(rows, base, identifier) -> dict | None:
    """Choose the best-determined distance; keep other determinations as alternates.

    Disagreement between determinations is reported as alternates rather than as
    engine-defined conflicting evidence, because SIMBAD methods differ legitimately.
    """
    candidates = []
    for row in rows:
        value = _number(row.get("dist"))
        unit = (row.get("unit") or "").strip()
        if value is None or value <= 0 or not unit:
            continue
        uncertainty = _uncertainty(row.get("minus_err"), row.get("plus_err"), value)
        symmetric = (uncertainty.get("value") if uncertainty
                     and uncertainty.get("kind") == "symmetric" else None)
        reference = row.get("bibcode")
        if not isinstance(reference, str) or not reference.strip():
            continue
        candidates.append({"value": value, "unit": unit, "uncertainty": uncertainty,
                           "reference": reference, "method": (row.get("method") or "").strip() or None,
                           "rank": symmetric if symmetric is not None else float("inf")})
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["rank"])
    best = candidates[0]
    alternates = [{"value": c["value"], "unit": c["unit"], "uncertainty": c["uncertainty"],
                   "reference": c["reference"], "method": c["method"]} for c in candidates[1:6]]
    record = {**base, "record_id": str(rows[0].get("main_id") or identifier).strip(),
              "value": best["value"], "unit": best["unit"], "value_kind": "numeric",
              "reference": best["reference"], "uncertainty": best["uncertainty"],
              "method": best["method"], "label": "distance",
              "alternate_determinations": alternates,
              "selection_note": "Smallest reported symmetric uncertainty; other determinations are "
                                "listed as alternates and never merged into one value.",
              "uncertainty_note": (None if best["uncertainty"] else
                                   "The provider error field was unusable for the selected "
                                   "determination, so no uncertainty is reported.")}
    record["quote"] = _quote("stellar_distance", record)
    return record


def _quote(prop: str, record) -> str:
    value, unit = record["value"], record.get("unit")
    if isinstance(value, float):
        part = f"{value:,.10f}".rstrip("0").rstrip(".")
    else:
        part = str(value)
    uncertainty = record.get("uncertainty")
    if uncertainty:
        if uncertainty.get("kind") == "symmetric":
            part += f" ± {uncertainty['value']}"
        else:
            part += f" (+{uncertainty.get('plus')} / -{uncertainty.get('minus')})"
    if unit and unit != "catalog value":
        part += f" {unit}"
    reference = f" (reference {record['reference']})" if record.get("reference") else ""
    extra = f" in the {record['band']} band" if record.get("band") else ""
    if record.get("method"):
        extra += f" ({record['method']} method)"
    verb = "as" if record.get("value_kind") == "categorical" else "of"
    return (f"SIMBAD reports the {record.get('label') or prop} for {record['record_id']}"
            f"{extra} {verb} {part}{reference}.")