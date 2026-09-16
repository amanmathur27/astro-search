"""Keyword intent classifier (no ML) + entity extraction + fuzzy fix."""
from __future__ import annotations
import re

INTENTS = {
    "celestial_event_lookup": "dates/times of a specific event",
    "celestial_event_detail": "visibility/location info for an event",
    "current_phenomenon": "real-time data (aurora NOW, flare TODAY)",
    "recent_news": "latest news/discoveries",
    "concept_explanation": "understand something (what is a pulsar)",
    "research_lookup": "academic papers",
    "object_lookup": "data about a specific object",
    "mission_status": "spacecraft/mission status",
    "periodic_event": "recurring event calendar",
}

# Order matters — first match wins (handoff §5), with §6 patch for what-is collision.
INTENT_RULES = [
    ("mission_status", ["who is in space", "who's in space", "in space right now",
                        "mission", "spacecraft", "probe", "rover", "satellite",
                        "where is voyager", "iss position", "launch", "iss"]),
    ("current_phenomenon", ["tonight", "right now", "current kp", "aurora now",
                            "live", "forecast", "is there aurora", "solar wind", "kp index"]),
    ("celestial_event_detail", ["visible from", "can i see", "visibility",
                                "what time", "where to watch", "best place"]),
    ("research_lookup", ["paper", "study", "research", "arxiv", "published",
                         "journal", "findings", "peer reviewed", "abstract"]),
    ("mission_status", ["mission", "spacecraft", "probe", "rover", "satellite",
                        "where is voyager", "iss position", "launch", "who is in space"]),
    ("periodic_event", ["calendar", "all meteor showers", "this year events",
                        "celestial calendar", "schedule"]),
    ("celestial_event_lookup", ["next", "upcoming", "when is", "when will",
                                "date of", "eclipse", "meteor shower", "full moon",
                                "new moon", "conjunction", "opposition", "transit",
                                "solstice", "equinox", "supermoon", "alignment",
                                "moon phase", "phase of the moon", "phase of moon"]),
    ("recent_news", ["latest", "recent", "new discovery", "just announced",
                     "breaking", "discovered", "found", "detected", "today", "news"]),
    # object_lookup BEFORE concept_explanation to fix what-is collision
    ("object_lookup", ["how far", "distance to", "size of", "mass of",
                       "type of star", "magnitude", "coordinates of", "redshift"]),
    ("concept_explanation", ["what is", "explain", "how does", "why does",
                             "difference between", "define", "meaning of"]),
]

DEFAULT_INTENT = "recent_news"

KNOWN_ENTITIES = {
    "eclipses": ["solar eclipse", "lunar eclipse", "total eclipse", "annular eclipse", "partial eclipse", "blood moon"],
    "moon_phases": ["full moon", "new moon", "first quarter", "last quarter", "supermoon", "moon phase"],
    "meteor_showers": ["perseids", "leonids", "geminids", "eta aquariids", "orionids", "lyrids",
                       "ursids", "draconids", "taurids", "quadrantids", "delta aquariids", "meteor shower"],
    "planetary": ["conjunction", "opposition", "transit", "occultation", "retrograde",
                  "greatest elongation", "planetary alignment", "alignment"],
    "solar": ["solar flare", "cme", "coronal mass ejection", "sunspot", "solar storm",
              "geomagnetic storm", "aurora", "northern lights", "kp index", "solar wind"],
    "planets": ["mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"],
    "deep_sky": ["black hole", "neutron star", "pulsar", "nebula", "galaxy", "quasar",
                 "supernova", "white dwarf", "dark matter", "exoplanet"],
    "missions": ["jwst", "james webb", "hubble", "artemis", "voyager", "cassini",
                 "perseverance", "curiosity", "new horizons", "iss",
                 "isro", "gslv", "pslv", "lvm3", "sslv", "gaganyaan", "chandrayaan",
                 "spacex", "starship", "falcon", "dragon", "starlink",
                 "nasa", "esa", "jaxa", "cnsa", "roscosmos",
                 "rocket", "launch", "satellite", "space station"],
}

ALIASES = {"blood moon": "lunar eclipse", "jwst": "james webb", "shooting stars": "meteor shower"}

# precompiled whole-word patterns for short entities (built once, not per query)
_SHORT_RE: dict[str, "re.Pattern[str]"] = {
    ent: re.compile(r"\b" + re.escape(ent) + r"\b")
    for group in KNOWN_ENTITIES.values() for ent in group if len(ent) <= 4
}


def _edit_distance(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 2:
        return 99
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            prev, dp[j] = dp[j], min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
    return dp[n]


def fuzzy_fix(token: str) -> str:
    for group in KNOWN_ENTITIES.values():
        for ent in group:
            if _edit_distance(token.lower(), ent) <= 2 and len(token) > 5:
                return ent
    return token


def classify(query: str) -> tuple[str, list[str]]:
    q = (query or "").lower()
    for alias, target in ALIASES.items():
        if alias in q:
            q = q.replace(alias, target)
    intent = None
    for name, keywords in INTENT_RULES:
        if any(k in q for k in keywords):
            intent = name
            break
    if intent is None:
        # object-name fallback: planet/deep-sky/mission mention => object_lookup
        if any(e in q for e in KNOWN_ENTITIES["planets"] + KNOWN_ENTITIES["deep_sky"] + KNOWN_ENTITIES["missions"]):
            intent = "object_lookup"
        else:
            intent = DEFAULT_INTENT
    entities: list[str] = []
    for group in KNOWN_ENTITIES.values():
        for ent in group:
            if len(ent) <= 4:
                # short codes (iss, jwst, esa...) must match whole words, not substrings ("iss" in "mission")
                if _SHORT_RE.get(ent, re.compile(r"\b" + re.escape(ent) + r"\b")).search(q):
                    entities.append(ent)
            elif ent in q:
                entities.append(ent)
    # fuzzy on single tokens for misspellings like persieds
    for tok in re.findall(r"[a-z]{6,}", q):
        fixed = fuzzy_fix(tok)
        if fixed != tok and fixed not in entities:
            entities.append(fixed)
    return intent, entities
