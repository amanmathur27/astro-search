"""Field-aware candidate relevance and extractive snippets, never fact verification."""
import re

STOP = set('a an the is are was were of to from and or in on for with what when how tell me about latest recent news updates please'.split())


def tokens(text):
    return set(re.findall(r'\w+', str(text or '').lower())) - STOP


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
