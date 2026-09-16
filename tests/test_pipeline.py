from astro_search.normalizer import normalize, clean_text, to_iso_utc
from astro_search.deduplicator import deduplicate, title_similarity
from astro_search.ranker import rank

def test_normalize_html():
    r = normalize({"title": "<b>Hello</b>", "summary": "<p>" + "x"*500 + "</p>", "url": "https://a.com", "published": "2026-09-16"},
                  {"name": "NASA", "source_type": "api", "authority": 3})
    assert r["title"] == "Hello" and len(r["summary"]) <= 400 and r["authority"] == 3 and r["published"].endswith("Z") or r["published"] == ""

def test_normalize_defaults():
    r = normalize({}, {})
    assert all(k in r for k in ("title","summary","url","source","authority","category","published","freshness_h","event_date_utc","visibility"))

def test_dedup():
    a = normalize({"title": "Perseid meteor shower peaks tonight", "url": "https://a.com/1"}, {"name": "A", "authority": 2})
    b = normalize({"title": "Perseid meteor shower peak tonight", "url": "https://b.com/2"}, {"name": "B", "authority": 3})
    out = deduplicate([a, b])
    assert len(out) == 1 and out[0]["source"] == "B"

def test_ranker_bm25():
    docs = [normalize({"title": t, "summary": s, "url": f"https://x/{i}"}, {"name": "S", "authority": 2})
            for i,(t,s) in enumerate([("Perseid meteor shower peak August", "meteor shower peak date"), ("JWST galaxy image", "deep space"), ("Perseids tonight", "meteor shower tonight")])]
    ranked = rank(docs, "Perseid meteor shower peak", "celestial_event_lookup")
    assert ranked[0]["title"].lower().startswith("perseid")
