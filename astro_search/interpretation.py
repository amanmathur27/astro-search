"""Conservative query interpretation; unsupported phrasing is not verified evidence."""
from __future__ import annotations
import re
from dataclasses import asdict, dataclass, field
from .intent import CATALOG_RE, KNOWN_ENTITIES

# Identity aliases, not scientific facts. Bare ambiguous names need context.
MISSIONS = {
    "roman": ("Nancy Grace Roman Space Telescope", (
        "nancy grace roman space telescope", "roman space telescope",
        "roman nancy grace telescope", "nancy grace roman telescope",
        "nancy grace telescope", "roman telescope")),
    "webb": ("James Webb Space Telescope", ("james webb space telescope", "james webb", "jwst", "webb telescope")),
    "hubble": ("Hubble Space Telescope", ("hubble space telescope", "hubble telescope", "hubble")),
}
PROPERTY_PATTERNS = (
    ("distance", r"\b(?:how far|distance)\b"),
    ("parallax", r"\bparallax\b"),
    ("radial_velocity", r"\bradial velocit(?:y|ies)\b"),
    ("spectral_type", r"\bspectral (?:type|class)\b"),
    ("object_type", r"\bobject type\b|\bwhat (?:kind|type) of (?:object|star)\b"),
    ("launch_date", r"\blaunch date\b|\bwhen\b.*\blaunch(?:ed|ing)?\b"),
    ("payload_mass", r"\b(?:payload|instrument(?:s)?|scientific payload)\s+(?:mass|weight)\b"),
    ("launch_mass", r"\b(?:launch|wet|liftoff)\s+(?:mass|weight)\b"),
    ("dry_mass", r"\bdry\s+(?:mass|weight)\b"),
    ("mirror_diameter", r"\b(?:mirror|aperture)\s+(?:diameter|size)\b|\bdiameter\s+of\b.*\bmirror\b"),
    # "absolute magnitude" needs a distance and extinction model this resolver does not have.
    ("magnitude", r"(?<!absolute )\b(?:apparent\s+)?magnitude\b"),
    ("mass", r"\b(?:mass|weight|how heavy)\b"),
    ("diameter", r"\bdiameter\b"),
)
SCOPE_TERMS = re.compile(
    r"\b(?:astronomy|astronomical|astrophysics|cosmology|space|telescope|telescopes|"
    r"planet|planets|moon|lunar|sun|solar|star|stars|galaxies|comet|asteroid|"
    r"nebulae|exoplanets|orbit|orbital|eclipse|meteor|meteors|observatory|"
    r"supernovae|gravity|gravitational|redshift|spectroscopy|celestial|stargazing|constellation|constellations|sky)\b", re.I)
AMBIGUOUS_NAMES = {"roman", "mercury", "curiosity", "perseverance", "dragon", "falcon", "rocket", "launch", "satellite"}
NONSPACE = re.compile(r"\b(?:iphone|smartphone|macbook|horoscope|astrology|roman empire|roman numerals)\b", re.I)


def phrase(pattern: str, text: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(pattern) + r"(?!\w)", text, re.I))


@dataclass
class QuerySpec:
    task: str = "discovery"
    scope: str = "out_of_scope"
    subject: str | None = None
    subject_id: str | None = None
    aliases: list[str] = field(default_factory=list)
    property: str | None = None
    assumptions: list[dict] = field(default_factory=list)
    clarification: str | None = None
    distance: dict | None = None

    def to_dict(self):
        return asdict(self)


def interpret(query: str) -> QuerySpec:
    q = query.lower()
    spec = QuerySpec()
    terms = bool(SCOPE_TERMS.search(q))
    known = [e for group in KNOWN_ENTITIES.values() for e in group if phrase(e, q)]
    if terms or CATALOG_RE.search(q) or any(e not in AMBIGUOUS_NAMES for e in known):
        spec.scope = "in_scope"
    if NONSPACE.search(q):
        spec.scope = "uncertain" if terms else "out_of_scope"
    matched_missions = []
    for ident, (name, aliases) in MISSIONS.items():
        if any(phrase(a, q) for a in aliases) or (ident == "roman" and phrase("roman", q) and phrase("telescope", q)):
            matched_missions.append(ident)
            if spec.subject is None:
                spec.subject_id, spec.subject = ident, name
                spec.aliases = list(aliases)
    if not spec.subject:
        catalog = CATALOG_RE.search(q)
        if catalog:
            spec.subject = catalog.group(0)
        elif known:
            spec.subject = max(known, key=len)
        spec.aliases = [spec.subject] if spec.subject else []
    for prop, pattern in PROPERTY_PATTERNS:
        if re.search(pattern, q):
            spec.property = prop
            spec.task = "fact_lookup"
            break
    if re.search(r"\brecently\s+launched\b", q):
        spec.assumptions.append({"claim": "recently_launched", "status": "unverified"})
    if spec.property in {"mass", "payload_mass", "diameter", "distance"} and not spec.subject:
        spec.clarification = "Which astronomical object or mission do you mean?"
    if spec.property in {"mass", "payload_mass", "diameter"}:
        spec.clarification = "Specify launch mass, dry mass, or scientific instrument mass." if spec.property != "diameter" else "Specify mirror diameter or the dimensions of the whole observatory."
    if spec.task == "fact_lookup" and not spec.subject:
        spec.clarification = "Which astronomical object or mission do you mean?"
    specific_properties = [prop for prop, pattern in PROPERTY_PATTERNS
                           if prop not in {"mass", "diameter"} and re.search(pattern, q)]
    if spec.task == "fact_lookup" and (len(matched_missions) > 1 or len(specific_properties) > 1):
        spec.clarification = "Please request one subject and one property at a time."
    if spec.task == "fact_lookup" and re.search(r"\b(?:in|as of|before|after|during)\s+(?:19|20)\d{2}\b", q):
        spec.clarification = "Historical specifications require dated archival evidence, which this lookup does not provide."
    # Temporal event requests are not news queries. Explanations remain discovery.
    phases = [p for p in ("full moon", "new moon", "first quarter", "last quarter") if phrase(p, q)]
    temporal = bool(re.search(r"\b(?:when|next|this month|today|tonight|tomorrow|dates?|calendar|20\d{2})\b", q))
    if not spec.property and phases and temporal:
        spec.task, spec.property = "local_answer", "moon_phase_date"
        spec.subject, spec.aliases = phases[0], phases
        if len(phases) > 1:
            spec.clarification = "Please request one lunar phase at a time."
    event_words = re.search(r"\b(?:celestial|astronomical|astronomy|sky|stargazing)\b", q)
    if not spec.property and event_words and re.search(r"\b(?:events?|happening|calendar)\b", q):
        spec.task, spec.property, spec.subject = "local_answer", "event_dates", "celestial events"
    if spec.property == "distance":
        from .capabilities import BODIES, distance_request
        spec.distance = distance_request(query)
        target = spec.distance["target"]
        if target:
            spec.subject_id = target
            spec.subject = BODIES[target]["name"] + " relative to Earth"
            spec.aliases = list(BODIES[target]["aliases"]) + ["earth"]
            if not NONSPACE.search(q):
                spec.scope = "in_scope"
        spec.clarification = spec.distance["error"]
        if len(specific_properties) > 1 or matched_missions:
            spec.clarification = "Please request one body pair and one property at a time."
        recognized = [key for key, body in BODIES.items()
                      if any(phrase(alias, q) for alias in body["aliases"])]
        if not target and not recognized and not matched_missions:
            # A named object outside the solar-system table: the distance comes from
            # the SIMBAD archive, never from a solar-system computation.
            from .simbad import candidate_identifier, safe_identifier
            candidate = candidate_identifier(query)
            if candidate and safe_identifier(candidate):
                spec.property, spec.subject, spec.subject_id = "stellar_distance", candidate, None
                spec.aliases, spec.clarification, spec.distance = [candidate], None, None
                if not NONSPACE.search(q):
                    spec.scope = "in_scope"
    if spec.scope == "out_of_scope" and not NONSPACE.search(q) and re.search(r"\bevents?\b.*\b(?:this month|today|next week)\b", q):
        spec.scope = "uncertain"
    if spec.property == "launch_date" and re.search(r"\b(?:will|scheduled|planned)\b", q):
        spec.clarification = "Planned launch dates require current schedule evidence; this resolver verifies completed launches only."
    if spec.scope == "uncertain":
        spec.clarification = "Please clarify the astronomy-related subject and requested fact."
    # Conjunction geometry is computed locally; it is never read out of an article.
    if not spec.property and re.search(r"\bconjunctions?\b|\bin conjunction\b", q):
        from .capabilities import BODIES
        named = [key for key, body in BODIES.items() if key != "earth"
                 and any(phrase(alias, q) for alias in body["aliases"])]
        if not NONSPACE.search(q):
            spec.scope = "in_scope"
        if len(named) == 2:
            spec.property, spec.task = "conjunction", "local_answer"
            spec.subject_id = "+".join(named)
            spec.subject = " and ".join(BODIES[key]["name"] for key in named)
            spec.aliases = [BODIES[key]["name"] for key in named]
            spec.clarification = None
        elif len(named) > 2:
            spec.clarification = ("Conjunction geometry is supported for exactly two bodies; "
                                  "name two of: "
                                  + ", ".join(b["name"] for k, b in BODIES.items() if k != "earth") + ".")
        else:
            spec.clarification = ("Name two supported bodies for a conjunction ("
                                  + ", ".join(b["name"] for k, b in BODIES.items() if k != "earth")
                                  + "). Other object pairs are not inferred.")
    from .doi import extract_doi
    doi = extract_doi(query)
    if doi:
        # An explicit DOI is self-identifying: its registration metadata is resolved
        # regardless of the surrounding words, and never read from article prose.
        spec.scope, spec.task, spec.property = "in_scope", "doi_lookup", "doi_metadata"
        spec.subject, spec.subject_id, spec.aliases = doi, doi.lower(), [doi]
        spec.distance, spec.clarification = None, None
        return spec
    from .gcn import is_gcn_query
    from .mpec import is_mpec_query
    from .cbat import is_cbat_query
    from .alerts import is_alert_query
    if not NONSPACE.search(q):
        # Rapid-report providers are provider-explicit: a named provider is never
        # served by a different provider with a different coverage window. These
        # identifiers (e.g. "CBET 5000", "latest CBET reports") are self-identifying
        # and resolve even without broader astronomy vocabulary, mirroring the DOI
        # path above.
        for task, detector in (("circular_lookup", is_gcn_query), ("mpec_lookup", is_mpec_query),
                               ("cbet_lookup", is_cbat_query), ("alert_lookup", is_alert_query)):
            if detector(query):
                spec.scope, spec.task = "in_scope", task
                break
    return spec
