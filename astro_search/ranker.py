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
