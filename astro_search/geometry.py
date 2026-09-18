"""Local conjunction geometry with PyEphem.

Only apparent angular separation between two named bodies is computed. Bodies are
geocentric by default; a Moon pair requires an observer, because topocentric
parallax moves the Moon by up to about a degree. "Conjunction" has several
published definitions (equal right ascension, equal ecliptic longitude, minimum
angular separation); this module computes the minimum angular separation and says
so. No occultation or transit claim is ever derived from a small separation.
"""
from __future__ import annotations
import math

STEP_DAYS = 0.5
WINDOW_DAYS = 800.0
MAX_COARSE_SAMPLES = 2400
REFINE_ROUNDS = 60
MAX_CANDIDATES = 3
# A conjunction is only claimed when the refined minimum is at or below this
# separation. The threshold is this engine's stated operational convention; the
# separation actually found is always reported, whatever it is.
CLOSE_APPROACH_DEG = 5.0
BODY_NAMES = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
              "Uranus", "Neptune", "Pluto")


class GeometryUnavailable(Exception):
    """Recognized request that local geometry cannot resolve honestly."""


def _ephem():
    try:
        import ephem
    except ImportError:
        raise GeometryUnavailable("Conjunction geometry requires the optional local "
                                  "extra (PyEphem).") from None
    return ephem


def _mutable(ephem, name):
    if name not in BODY_NAMES:
        raise GeometryUnavailable("Unsupported body for conjunction geometry.")
    return getattr(ephem, name)()


def _positions(ephem, names, when, observer=None):
    out = []
    moment = when.replace(tzinfo=None)
    if observer is not None:
        # This PyEphem build rejects compute(observer, date): set the observer's
        # own date and call compute(observer).
        observer.date = moment
    for name in names:
        body = _mutable(ephem, name)
        try:
            body.compute(moment) if observer is None else body.compute(observer)
        except (ValueError, OverflowError, RuntimeError):
            raise GeometryUnavailable("The local ephemeris could not compute this body.") from None
        # ra/dec are apparent (epoch of date): topocentric with an observer.
        out.append((body.ra, body.dec))
    return out


def separation_deg(names, when, observer=None) -> float:
    """Apparent angular separation in degrees (no refraction, no aberration claim)."""
    ephem = _ephem()
    (ra1, dec1), (ra2, dec2) = _positions(ephem, names, when, observer)
    value = float(ephem.separation((ra1, dec1), (ra2, dec2))) * 180.0 / math.pi
    if not math.isfinite(value):
        raise GeometryUnavailable("The local ephemeris returned an invalid separation.")
    return value


def _refine(names, low, high, observer) -> tuple[float, object]:
    """Ternary refinement of a separation minimum inside one bracketing step."""
    third = (high - low) / 3
    left, right = low + third, high - third
    for _ in range(REFINE_ROUNDS):
        if separation_deg(names, left, observer) < separation_deg(names, right, observer):
            high = right
        else:
            low = left
        third = (high - low) / 3
        left, right = low + third, high - third
    best_time = left
    return separation_deg(names, best_time, observer), best_time


def conjunction_result(names, start, observer=None, window_days: float = WINDOW_DAYS,
                       step_days: float = STEP_DAYS,
                       threshold_deg: float = CLOSE_APPROACH_DEG) -> dict:
    """Earliest close approach in the window, plus the smallest separation found.

    A local minimum of the apparent separation curve is not by itself a conjunction:
    the curve has unrelated local minima, so a conjunction is claimed only when the
    refined minimum is at or below the stated close-approach threshold. The smallest
    separation actually found is always reported so a negative answer is informative.
    """
    from datetime import timedelta
    if len(names) != 2 or names[0] == names[1]:
        raise GeometryUnavailable("Exactly two distinct bodies are required.")
    if not (0 < step_days <= 5):
        raise GeometryUnavailable("Search step must be between 0 and 5 days.")
    if not (0 < threshold_deg <= 30):
        raise GeometryUnavailable("Close-approach threshold must be between 0 and 30 degrees.")
    samples = int(min(MAX_COARSE_SAMPLES, max(8, window_days / step_days)))
    times = [start + timedelta(days=index * step_days) for index in range(samples + 1)]
    values = [separation_deg(names, when, observer) for when in times]
    candidates = [index for index in range(1, len(values) - 1)
                  if values[index] <= values[index - 1] and values[index] <= values[index + 1]]
    refined = [_refine(names, times[index - 1], times[index + 1], observer)
               for index in candidates[:MAX_CANDIDATES]]
    # Smallest separation anywhere in the window, refined around the best sample.
    floor_index = min(range(len(values)), key=lambda index: values[index])
    floor_low = times[max(0, floor_index - 1)]
    floor_high = times[min(len(times) - 1, floor_index + 1)]
    floor_value, floor_time = _refine(names, floor_low, floor_high, observer)
    approaches = sorted(((value, when) for value, when in refined if value <= threshold_deg),
                        key=lambda item: item[1])
    search = {"window_days": window_days, "coarse_step_days": step_days,
              "refinement_rounds": REFINE_ROUNDS, "samples": samples,
              "close_approach_threshold_deg": threshold_deg,
              "method": "coarse sampling then ternary refinement of the apparent angular separation",
              "frame": "topocentric apparent" if observer is not None else "geocentric apparent",
              "refraction": False, "definition": "minimum apparent angular separation",
              "conjunction_note": "Conjunction definitions vary (equal right ascension, equal "
                                  "ecliptic longitude, or minimum separation); this engine reports "
                                  "the minimum apparent angular separation."}
    result = {"threshold_deg": threshold_deg,
              "smallest": {"separation_deg": round(floor_value, 6),
                           "time_utc": floor_time.isoformat().replace("+00:00", "Z")},
              "approach": None, "search": search}
    if approaches:
        value, when = approaches[0]
        result["approach"] = {"separation_deg": round(value, 6),
                             "time_utc": when.isoformat().replace("+00:00", "Z")}
        positions = _positions(_ephem(), names, when, observer)
        result["positions"] = {name: {"ra_deg": round(float(ra) * 180.0 / math.pi, 6),
                                      "dec_deg": round(float(dec) * 180.0 / math.pi, 6)}
                               for name, (ra, dec) in zip(names, positions)}
    return result


def observer_for(ephem, pair, lat, lon, elevation_m: float = 0.0):
    """Observer for Moon-involving pairs; without one the Moon stays geocentric."""
    if not any(name == "Moon" for name in pair):
        return None
    if lat is None or lon is None:
        raise GeometryUnavailable("A Moon conjunction is observer-dependent: supply lat and lon "
                                  "(topocentric parallax moves the Moon by up to about one degree).")
    site = ephem.Observer()
    site.lat = str(float(lat))
    site.lon = str(float(lon))
    site.elevation = float(elevation_m or 0.0)
    site.pressure = 0  # no refraction: an unmodelled atmosphere is worse than none
    return site