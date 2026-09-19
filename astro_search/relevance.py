"""Field-aware candidate relevance and extractive snippets, never fact verification."""
import re

STOP = set('a an the is are was were of to from and or in on for with what when how tell me about latest recent news updates please'.split())
ASTRO_GENERIC_STOP = set('space astronomy astrophysics universe science telescope observatory article articles website page post posted'.split())

POLYSEMY_GUARDS = {
    "eclipse": {
        "negatives": ["ide", "java", "plugin", "compiler", "mitsubishi", "twilight", "vampire", "soundtrack"],
        "positives": ["solar", "lunar", "sun", "moon", "totality", "annular", "umbra", "penumbra", "celestial", "sky", "path"],
    },
    "cluster": {
        "negatives": ["kubernetes", "k8s", "server", "headache", "headaches", "symptom", "medical", "covid", "outbreak"],
        "positives": ["star", "globular", "open", "galaxy", "galaxies", "virgo", "pleiades", "hyades", "stellar"],
    },
    "transit": {
        "negatives": ["bus", "train", "subway", "metro", "fare", "commute", "station", "customs"],
        "positives": ["planet", "exoplanet", "venus", "mercury", "star", "light", "curve", "kepler", "tess", "photometry"],
    },
    "curiosity": {
        "negatives": ["psychology", "mindset", "habit", "curiosity killed", "childhood", "philosophical"],
        "positives": ["rover", "mars", "nasa", "gale", "crater", "red planet", "jpl", "msl"],
    },
    "spirit": {
        "negatives": ["ghost", "holy spirit", "alcohol", "liquor", "vodka", "whiskey", "airline", "airways", "team spirit"],
        "positives": ["rover", "mars", "opportunity", "gusev", "crater", "nasa", "jpl"],
    },
    "flare": {
        "negatives": ["pants", "jeans", "fashion", "dress", "arthritis", "inflammation"],
        "positives": ["solar", "sun", "sunspot", "cme", "geomagnetic", "x-class", "m-class", "star", "stellar", "magnetic"],
    },
    "rings": {
        "negatives": ["jewelry", "diamond", "gold", "wedding", "engagement", "lord of the rings", "tolkien"],
        "positives": ["saturn", "uranus", "neptune", "jupiter", "planetary", "cassini", "ring system", "debris"],
    },
}


def tokens(text):
    return set(re.findall(r'\w+', str(text or '').lower())) - STOP


def check_polysemy_collision(query_toks: set[str], doc_text: str) -> float:
    """Return penalty multiplier (0.05 to 1.0) if non-astronomical polysemy collision detected."""
    doc_lower = str(doc_text or "").lower()
    for word, guard in POLYSEMY_GUARDS.items():
        if word in query_toks:
            has_negative = any(re.search(r"\b" + re.escape(neg) + r"\b", doc_lower) for neg in guard["negatives"])
            has_positive = any(re.search(r"\b" + re.escape(pos) + r"\b", doc_lower) for pos in guard["positives"])
            if has_negative and not has_positive:
                return 0.05  # Severe collision penalty
    return 1.0


def fields(row):
    md = row.get('metadata') or {}
    md = md if isinstance(md, dict) else {}
    entries = [('title', row.get('title'), 2.0)]
    for key in ('feed_title', 'html_title', 'og_title', 'structured_title'):
        entries.append((key, md.get(key), 2.0))
    entries.append(('summary', row.get('summary'), 1.0))
    for key in ('feed_description', 'meta_description', 'og_description', 'structured_description'):
        entries.append((key, md.get(key), 1.0))
    for key, weight in [('headings', 1.7), ('passages', 1.2)]:
        values = md.get(key, [])
        if isinstance(values, list):
            entries.extend((key, v, weight) for v in values[:100] if isinstance(v, str))
    seen = set()
    for name, text, weight in entries:
        if text is None:
            continue
        text = str(text)[:8000]
        identity = ' '.join(text.lower().split())
        if identity and identity not in seen:
            seen.add(identity)
            yield name, text, weight


def annotate(row, query, intent):
    q = tokens(query)
    data = list(fields(row))
    matches = [(name, text, weight, len(q & tokens(text)) / max(1, len(q)))
               for name, text, weight in data]
    # Best field, not additive repetition across publisher-controlled fields.
    best = max((weight * match for _, _, weight, match in matches), default=0.0)
    union = set().union(*(tokens(text) for _, text, _ in data)) if data else set()
    coverage = len(q & union) / max(1, len(q))
    matched = [name for name, _, _, score in matches if score]
    from .interpretation import interpret, phrase, PROPERTY_PATTERNS
    spec = interpret(query)
    aliases = spec.aliases or ([spec.subject] if spec.subject else [])
    subject_fields = [name for name, text, _ in data if any(phrase(a, text) for a in aliases)]
    pattern = next((p for prop, p in PROPERTY_PATTERNS if prop == spec.property), None)
    property_fields = [name for name, text, _ in data if pattern and re.search(pattern, text, re.I)]
    if aliases and not subject_fields:
        best *= 0.2
        coverage *= 0.2
    if pattern and not property_fields:
        best *= 0.4
        coverage *= 0.4

    # Polysemy Collision Guard
    combined_doc_text = " ".join(t for _, t, _ in data)
    poly_multiplier = check_polysemy_collision(q, combined_doc_text)
    if poly_multiplier < 1.0:
        best *= poly_multiplier
        coverage *= poly_multiplier

    row['relevance'] = {'subject_match': bool(subject_fields) if aliases else None,
                        'property_match': bool(property_fields) if pattern else None,
                        'subject_property_cooccurrence': any(any(phrase(a, text) for a in aliases) and re.search(pattern, text, re.I) for _, text, _ in data) if aliases and pattern else None,
                        'query_coverage': round(coverage, 4), 'field_score': round(best, 4),
                        'matched_fields': list(dict.fromkeys(matched)),
                        'evidence_status': 'unverified', 'method': 'lexical_field_matching'}
    # Prefer a relevant article passage over a generic publisher description.
    passages = [item for item in matches if item[0] == 'passages' and item[3] > 0]
    has_body = any(name == 'passages' for name, _, _, _ in matches)
    body_coverage = max((score for name, _, _, score in matches if name == 'passages'), default=0.0)
    row['relevance']['body_query_coverage'] = round(body_coverage, 4) if has_body else None
    row['relevance']['body_support'] = ('lexical_match' if passages else 'no_matching_passage') if has_body else 'not_assessed'
    if has_body and not passages:
        best *= 0.25  # keyword-rich title unsupported by extracted body; not a factual contradiction check
    descriptions = [item for item in matches if item[0] not in ('title', 'feed_title', 'html_title', 'og_title', 'structured_title', 'headings')]
    pool = passages or descriptions
    if pool:
        name, text, _, score = max(pool, key=lambda item: item[3])
        # Whole bounded paragraph: do not remove negations/qualifiers or join fragments.
        row['excerpt'] = {'text': text, 'source': 'article_passage' if name == 'passages' else name,
                          'query_match': bool(score), 'verified': False}
    if not best:
        coverage = 0.0
    row['relevance']['field_score'] = round(best, 4)
    return best, coverage
