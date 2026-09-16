"""Three-pass dedup: URL exact, title Jaccard>0.65, same event/date merge."""
from __future__ import annotations

STOPWORDS = {"a", "an", "the", "in", "on", "at", "of", "to", "and", "or", "is", "are", "was"}


def title_similarity(a: str, b: str) -> float:
    ta = set(a.lower().split()) - STOPWORDS
    tb = set(b.lower().split()) - STOPWORDS
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def deduplicate(results: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    out: list[dict] = []
    for r in results:
        url = (r.get("url") or "").strip().lower().rstrip("/")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        dup_idx = -1
        for i, kept in enumerate(out):
            if title_similarity(r.get("title", ""), kept.get("title", "")) > 0.65:
                dup_idx = i
                break
            if r.get("event_date_utc") and r.get("event_date_utc") == kept.get("event_date_utc") \
                    and r.get("event_type") and r.get("event_type") == kept.get("event_type"):
                dup_idx = i
                break
        if dup_idx >= 0:
            kept = out[dup_idx]
            # keep higher authority; record co-coverage
            if r.get("authority", 2) > kept.get("authority", 2):
                r.setdefault("extra", {}).setdefault("also_covered_by", []).append(kept.get("source"))
                out[dup_idx] = r
            else:
                kept.setdefault("extra", {}).setdefault("also_covered_by", []).append(r.get("source"))
        else:
            out.append(r)
    return out
