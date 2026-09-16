"""Lexical BM25 (pure Python, Actions-safe) + intent/authority/freshness blend.

final = bm25_mix*0.35 + intent_match*0.25 + authority_norm*0.20 + freshness*0.20,
min-max scaled to [0, 1] as `_score` on each result dict (mutation is intentional:
core sorts and serialises the same objects).

Hardening notes:
- Floored (always >= 0) IDF variant — no negative-IDF bug of the classic formula.
- IDF corpus N = len(results) (small-set BM25, correct at 5-100 docs).
- All numeric inputs coerced/clamped; empty/malformed inputs return sane output, never raise.
- No numpy / torch / sklearn.
"""
from __future__ import annotations
import math
from collections import Counter

K1, B = 1.5, 0.75
_FRESH_WINDOW_H = 168.0  # 7 days


def _tok(s: object) -> list[str]:
    if not isinstance(s, str):
        s = "" if s is None else str(s)
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
    docs = [_tok((r.get("title", "") or "") + " " + (r.get("summary", "") or "")) for r in results]
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
        final = (bm_mix * 0.35 + (1.0 if intent_ok else 0.3) * 0.25
                 + _authority_norm(r.get("authority", 2)) * 0.20 + _freshness(r.get("freshness_h")) * 0.20)
        r["_score"] = final  # rescaled below
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
