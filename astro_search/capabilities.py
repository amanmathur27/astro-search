"""Shared capability definitions for interpretation and local distance resolution.

Only Earth-referenced apparent distances are supported; other pairs are never
silently converted to Earth distances. No model imports or network calls here.
"""
import re

BODIES = {name.lower(): {"name": name, "ephem": name, "aliases": (name.lower(),)}
          for name in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter",
                       "Saturn", "Uranus", "Neptune", "Pluto")}
BODIES["earth"] = {"name": "Earth", "ephem": None, "aliases": ("earth",)}
UNITS = {"km": 1.0, "mi": 1 / 1.609344, "au": 1 / 149_597_870.7,
         "m": 1000.0}
UNIT_ALIASES = {"km": "km", "kilometers": "km", "kilometres": "km",
                "miles": "mi", "mi": "mi", "au": "au", "astronomical units": "au",
                "meters": "m", "metres": "m", "m": "m"}


def distance_request(query):
    """Parse a supported distance relation, including complete phrase validation.

    Unknown modifiers/objects are rejected, not discarded after token matching.
    This is a capability grammar, not a general-purpose language model.
    """
    q = re.sub(r"[?!.]+$", "", query.lower().strip())
    q = re.sub(r"[–—-]", " ", q)
    q = re.sub(r"\s+", " ", q)
    found = [key for key, body in BODIES.items()
             if any(re.search(r"\b" + re.escape(a) + r"\b", q) for a in body["aliases"])]
    request = {"target": None, "reference": None, "unit": "km", "error": None}
    if len(found) == 2 and "earth" in found:
        request.update(target=next(b for b in found if b != "earth"), reference="earth")
    else:
        request["error"] = ("Specify one target and Earth as the reference. Supported targets: "
                            + ", ".join(b["name"] for k, b in BODIES.items() if k != "earth")
                            + ". Other body pairs and multiple targets are not supported.")
        return request
    # Remove only explicitly supported current-time and unit modifiers.
    q = re.sub(r"\b(?:right now|currently|now|today)\b", "", q)
    for alias in sorted(UNIT_ALIASES, key=len, reverse=True):
        match = re.search(r"\s+in " + re.escape(alias) + r"$", q.strip())
        if match:
            request["unit"] = UNIT_ALIASES[alias]
            q = q.strip()[:match.start()]
            break
    q = re.sub(r"\bthe\b", "", q)
    q = re.sub(r"\s+", " ", q).strip()
    body = r"(?:" + "|".join(BODIES) + r")"
    pair = body + r" (?:from|to|and) " + body
    shapes = [r"how far (?:is|are) " + body + r" (?:away )?from " + body,
              r"(?:what is |what's |tell me |give me )?(?:current )?distance (?:between |from |of )?" + pair,
              r"(?:what is |what's )?" + body + r"(?:'s)? distance (?:from|to) " + body,
              body + " " + body + r" distance"]
    if not any(re.fullmatch(shape, q) for shape in shapes):
        request["error"] = ("The bodies are recognized, but this distance formulation or constraint is not supported. "
                            "Ask for current center-to-center distance from Earth, in km, miles, meters or AU. "
                            "Averages, surface separation, archival dates and additional objects are not inferred.")
    return request
