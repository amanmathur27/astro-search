"""Keyword intent classifier (no ML) + entity extraction + fuzzy fix."""
from __future__ import annotations
import re

# Shared with the TAP adapter so parsing and routing recognize the same names.
CATALOG_RE = re.compile(
    r"\b(?:Kepler|K2|TOI|WASP|HAT-P|TRAPPIST)[ -]?\d+(?:\s*[b-i])?\b"
    r"|\b(?:HD|GJ|Gliese)\s*\d+(?:\s*[b-i])?\b"
    r"|\bProxima\s+Centauri(?:\s+[b-d])?\b", re.I)

INTENTS = {
    "alert_lookup": "preliminary astronomical rapid reports (not confirmed measurements)",
    "circular_lookup": "GCN circulars via the modern machine-readable exports",
    "mpec_lookup": "Minor Planet Center MPECs, elements and astrometry",
    "cbet_lookup": "CBAT CBETs and recent-supernova lists (plaintext transport)",
    "doi_lookup": "bibliographic metadata for an explicit DOI",
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
                 "supernova", "white dwarf", "dark matter", "exoplanet",
                 "andromeda", "betelgeuse", "rigel", "vega", "sirius", "antares",
                 "orion nebula", "crab nebula", "ring nebula"],
    "missions": ["jwst", "james webb", "hubble", "artemis", "voyager", "cassini",
                 "perseverance", "curiosity", "new horizons", "iss",
                 "nancy grace roman", "nancy grace", "roman space telescope", "roman telescope", "roman",
                 "isro", "gslv", "pslv", "lvm3", "sslv", "gaganyaan", "chandrayaan",
                 "spacex", "starship", "falcon", "dragon", "starlink",
                 "nasa", "esa", "jaxa", "cnsa", "roscosmos",
                 "rocket", "launch", "satellite", "space station"],
}

# Structural pre-pass: unambiguous query shapes, checked before keyword rules.
# Order: location/time-specific detail first, generic event lookup after.
ALIASES = {"blood moon": "lunar eclipse", "jwst": "james webb", "shooting stars": "meteor shower",
           "m31": "andromeda galaxy", "m87": "m87 black hole", "sgr a*": "sagittarius a black hole"}
STRUCTURAL = [
    (re.compile(r"\bvisible\s+from\b"), "celestial_event_detail"),
    (re.compile(r"\bwhere\s+(can|could|will|would|to)\b.{0,20}\b(see|watch|observe|view|spot)\b"), "celestial_event_detail"),
    (re.compile(r"\bwhat time\b"), "celestial_event_detail"),
    (re.compile(r"\b(is there|will there be|any)\b.{0,15}\b(aurora|northern lights)\b"), "current_phenomenon"),
    (re.compile(r"\b(papers?|arxiv|preprint)\b.{0,20}\b(on|about)\b"), "research_lookup"),
    # NOTE: no leading "what is/explain" pattern here on purpose — "what is the next
    # mission to Mars" must stay mission_status via keyword rules, not concept.
    (re.compile(r"\b(all|every|complete|full list)\b.{0,25}\b(calendar|schedule|in 20\d\d|this year|events)\b"), "periodic_event"),
    (re.compile(r"\bwhere is\b.{0,25}\b(iss|voyager|hubble|jwst|mars|jupiter|saturn|international space station)\b"), "mission_status"),
    (re.compile(r"\bwhen\s+(is|will|does)\b.{0,30}\b(next|upcoming|eclipse|shower|moon|visible|occur|happen)\b"), "celestial_event_lookup"),
]


def structural_intent(q: str) -> str | None:
    for rx, intent in STRUCTURAL:
        if rx.search(q):
            return intent
    return None


# Event nouns: bare "next"/"upcoming" fires event lookup ONLY beside one of these.
# Fixes "next big thing in telescope technology" -> event misfire.
EVENT_NOUNS = {
    "eclipse", "moon", "meteor", "shower", "supermoon", "conjunction", "opposition",
    "transit", "occultation", "solstice", "equinox", "alignment", "comet",
    "aurora", "perihelion", "aphelion",
}

_RESEARCH_MARKS = ["paper", "arxiv", "preprint", "peer review", "journal", "doi", "thesis", "publication"]
_CONCEPT_MARKS = ["what is", "what are", "how does", "how do", "explain", "define",
                  "difference between", "why does", "why do", "meaning of"]
_PAST_RES = [re.compile(r"\bhappened\b"), re.compile(r"\boccurred\b"),
             re.compile(r"\bhistory of\b"), re.compile(r"\bwas\b"), re.compile(r"\bwere\b")]


def _event_suppressed(q: str) -> bool:
    """Negative guards: research/concept/past markers veto event lookup."""
    if any(k in q for k in _RESEARCH_MARKS):
        return True
    if any(k in q for k in _CONCEPT_MARKS) and "when" not in q:
        return True
    if any(rx.search(q) for rx in _PAST_RES) and "next" not in q and "upcoming" not in q:
        return True
    return False

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
    from .gcn import is_gcn_query
    from .mpec import is_mpec_query
    from .cbat import is_cbat_query
    from .doi import is_doi_query
    from .alerts import is_alert_query
    # Provider-specific identifiers route before the broader ATel topic matcher so a
    # named provider is never silently served by a different provider.
    for name, detector in (("doi_lookup", is_doi_query), ("circular_lookup", is_gcn_query),
                           ("mpec_lookup", is_mpec_query), ("cbet_lookup", is_cbat_query),
                           ("alert_lookup", is_alert_query)):
        if detector(q):
            # The provider performs strict id/topic filtering; do not fuzzy-map
            # transient names to unrelated planet/mission entities.
            return name, []
    intent = structural_intent(q)
    if intent is None:
        for name, keywords in INTENT_RULES:
            if name == "celestial_event_lookup":
                # bare next/upcoming needs an event noun; research/concept/past vetoes
                if _event_suppressed(q):
                    continue
                if not any(n in q for n in EVENT_NOUNS) and not any(
                        k in q for k in ("when is", "when will", "date of")):
                    continue
            if any(re.search(r"\b" + re.escape(k) + r"\b", q) for k in keywords):
                intent = name
                break
    if intent is None:
        # object-name fallback: planet/deep-sky mention => object_lookup.
        # mission names with news-ish nouns ("telescope", "launch", "mission") want
        # news, not object data ("nancy grace telescope" is Roman launch news).
        hit = lambda e: (_SHORT_RE.get(e, re.compile(r"\b" + re.escape(e) + r"\b")).search(q)
                         if len(e) <= 4 else e in q)
        if any(hit(e) for e in KNOWN_ENTITIES["planets"] + KNOWN_ENTITIES["deep_sky"]):
            intent = "object_lookup"
        elif (any(hit(e) for e in KNOWN_ENTITIES["missions"])
                and not any(k in q for k in ("telescope", "launch", "mission", "news", "update", "status"))):
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
    catalog = CATALOG_RE.search(q)
    if catalog:
        entities.append(catalog.group(0))
        # Preserve explicit news, research and observing requests.
        explicit_news = any(re.search(r"\b" + re.escape(k) + r"\b", q)
                            for k in ("latest", "recent", "news", "discovered", "discovery", "breaking"))
        if intent == "concept_explanation" or (intent == DEFAULT_INTENT and not explicit_news):
            intent = "object_lookup"
    return intent, entities
