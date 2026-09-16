"""Lexical BM25 (pure Python, Actions-safe) + intent/authority/freshness blend.

final = bm25_norm*0.35 + intent_match*0.25 + authority_norm*0.20 + freshness*0.20
No numpy / torch / sklearn. N = len(results) for IDF (small-set BM25).
"""
from __future__ import annotations
import math
from collections import Counter

K1, B = 1.5, 0.75


def _tok(s: str) -> list[str]:
    return [t for t in "".join(c.lower() if c.isalnum() else " " for c in s).split() if t]


def rank(results: list[dict], query: str, intent: str, source_intents: dict | None = None) -> list[dict]:
    qterms = _tok(query)
    docs = [_tok((r.get("title", "") or "") + " " + (r.get("summary", "") or "")) for r in results]
    N = max(len(docs), 1)
    df = Counter()
    for d in docs:
        for t in set(d):
            df[t] += 1
    avgdl = sum(len(d) for d in docs) / N if N else 1.0
    scored = []
    for r, d in zip(results, docs):
        tf = Counter(d)
        dl = max(len(d), 1)
        bm = 0.0
        for t in qterms:
            if t not in tf:
                continue
            idf = math.log(1 + (N - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
            bm += idf * (tf[t] * (K1 + 1)) / (tf[t] + K1 * (1 - B + B * dl / avgdl))
        entity_overlap = sum(1 for t in qterms if t in set(d)) / max(len(qterms), 1)
        bm_mix = 0.7 * bm + 0.3 * entity_overlap * 3.0
        intent_ok = True
        if source_intents and r.get("source") in source_intents:
            intent_ok = intent in source_intents[r["source"]]
        intent_score = 1.0 if intent_ok else 0.3
        auth_score = ((r.get("authority", 2) or 2) - 1) / 2
        fh = r.get("freshness_h")
        fresh = max(0.0, 1 - (fh / 168)) if isinstance(fh, (int, float)) else 0.5
        final = bm_mix * 0.35 + intent_score * 0.25 + auth_score * 0.20 + fresh * 0.20
        r["_score"] = round(final, 4)
        scored.append(r)
    # normalize bm influence: min-max on _score already blended; just sort
    scored.sort(key=lambda x: x["_score"], reverse=True)
    # scale to 0-1 for readability
    if scored:
        mx = max(x["_score"] for x in scored) or 1.0
        for x in scored:
            x["_score"] = round(x["_score"] / mx, 4)
    return scored
