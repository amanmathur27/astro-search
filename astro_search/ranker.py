"""Field-aware lexical ranking, with bounded BM25 tie-breaking.

Titles/headings/descriptions/passages remain separate. Repeated identical fields
are deduplicated. Authority/freshness are small multiplicative preferences, not
standalone relevance. `_score` is relative rank, never factual confidence.
No numpy / torch / sklearn; safe for lightweight Actions jobs.
"""
from __future__ import annotations
import math
from collections import Counter

K1, B = 1.5, 0.75
_FRESH_WINDOW_H = 168.0  # 7 days


def _text(value: object) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _tok(s: object) -> list[str]:
    s = _text(s)
    return [t for t in "".join(c.lower() if c.isalnum() else " " for c in s).split() if t]


def _authority_norm(value: object) -> float:
    try:
        a = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        a = 2
    return (min(max(a, 1), 3) - 1) / 2.0


def _freshness(value: object) -> float:
    if isinstance(value, bool):
        return 0.5
    if isinstance(value, (int, float)):
        return max(0.0, 1.0 - (value / _FRESH_WINDOW_H))
    return 0.5


def rank(results: list[dict], query: str, intent: str, source_intents: dict | None = None) -> list[dict]:
    if not results:
        return []
    # unique query terms, order-preserved (duplicates must not inflate BM25)
    qterms = list(dict.fromkeys(_tok(query)))
    from .relevance import annotate, fields
    docs = [_tok(' '.join(text for _, text, _ in fields(r))) for r in results]
    doc_sets = [set(d) for d in docs]
    lens = [len(d) for d in docs]
    N = len(docs)
    df = Counter()
    for s in doc_sets:
        df.update(s)
    avgdl = max(sum(lens) / N, 1.0)  # never 0 -> no ZeroDivisionError on empty docs

    # Pre-extract target entities and publisher domain once for the query
    from .intent import CATALOG_RE, KNOWN_ENTITIES
    from .interpretation import interpret
    from .sources.gnews import detected_publisher_domain

    spec = interpret(query)
    raw_entities = []
    if spec.subject:
        raw_entities.append(spec.subject.lower())
    cat = CATALOG_RE.search(query)
    if cat:
        raw_entities.append(cat.group(0).lower())
    for group in ("planets", "deep_sky", "missions", "meteor_showers"):
        for ent in KNOWN_ENTITIES.get(group, []):
            if len(ent) > 3 and ent in query.lower() and ent not in raw_entities:
                raw_entities.append(ent)
    target_entities_normalized = [' '.join(_tok(e)) for e in raw_entities if _tok(e)]
    domain = detected_publisher_domain(query)
    domain_core = domain.split(".")[0] if domain else ""

    scored: list[dict] = []
    for r, d, ds, dl in zip(results, docs, doc_sets, lens):
        tf = Counter(d)
        dl_f = max(dl, 1)
        norm = K1 * (1.0 - B + B * dl_f / avgdl)
        bm = 0.0
        for t in qterms:
            c = tf.get(t)
            if not c:
                continue
            idf = math.log(1.0 + (N - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
            # Demote generic filler terms in favor of distinct scientific identifiers
            from .relevance import ASTRO_GENERIC_STOP
            if t in ASTRO_GENERIC_STOP:
                idf *= 0.3
            bm += idf * (c * (K1 + 1.0)) / (c + norm)
        overlap = sum(1 for t in qterms if t in ds) / len(qterms) if qterms else 0.0
        bm_mix = 0.7 * bm + 0.3 * overlap * 3.0
        intent_ok = True
        if source_intents:
            allowed = source_intents.get(r.get("source", "") or "")
            if allowed is not None:
                intent_ok = intent in allowed
        field_score, coverage = annotate(r, query, intent)
        fresh = _freshness(r.get("freshness_h")) if intent in {"recent_news", "mission_status", "current_phenomenon"} else 0.0
        # Credibility and freshness break ties; they cannot rescue zero relevance.
        final = (field_score + coverage + min(bm_mix, 4.0) * 0.05) if field_score or coverage else 0.0
        final *= 1 + _authority_norm(r.get("authority", 2)) * 0.05 + fresh * 0.03 + (0.02 if intent_ok else 0)

        # Strict Entity Anchor Check (token normalized)
        if target_entities_normalized:
            doc_str = ' '.join(d)
            if any(e_norm in doc_str for e_norm in target_entities_normalized):
                final *= 1.8  # Entity Anchor Boost

        # Publisher match boost when query explicitly targets a publisher or domain
        if domain:
            row_url = str(r.get("url") or "").lower()
            row_pub = str(r.get("extra", {}).get("publisher") or r.get("source") or "").lower()
            row_title = str(r.get("title") or "").lower()
            if (domain in row_url or domain in row_pub or domain_core in row_pub
                    or (r.get("source") == "Google News" and (domain in row_title or domain_core in row_title))):
                final *= 3.0

        r["_score"] = final  # relative ranking, never factual confidence
        scored.append(r)

    scored.sort(key=lambda x: x["_score"], reverse=True)
    mx = max(x["_score"] for x in scored)
    if mx <= 0:
        for x in scored:
            x["_score"] = 0.0
    else:
        for x in scored:
            x["_score"] = round(x["_score"] / mx, 4)
    return scored
