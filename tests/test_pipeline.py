from astro_search.normalizer import normalize, clean_text, to_iso_utc, freshness_display
from astro_search.deduplicator import deduplicate, title_similarity
from astro_search.ranker import rank
from astro_search.intent import classify
from astro_search.core import AstroSearch

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

def test_ranker_edge_cases():
    assert rank([], "moon", "recent_news") == []
    # empty query + empty docs must not raise (avgdl guard)
    docs = [normalize({"title": "", "summary": "", "url": "https://x/1"}, {"name": "S", "authority": 2})]
    out = rank(docs, "", "recent_news")
    assert out and 0.0 <= out[0]["_score"] <= 1.0  # single doc rescales to 1.0; key is no-crash
    # duplicate query terms must not inflate: same order as single mention
    docs = [normalize({"title": "Mars rover photo", "summary": "curiosity", "url": "https://x/2"}, {"name": "S", "authority": 2}),
            normalize({"title": "Venus clouds", "summary": "atmosphere", "url": "https://x/3"}, {"name": "S", "authority": 2})]
    r1 = [d["title"] for d in rank([dict(x) for x in docs], "mars mars mars", "recent_news")]
    r2 = [d["title"] for d in rank([dict(x) for x in docs], "mars", "recent_news")]
    assert r1 == r2
    # malformed authority / non-string fields never raise; scores bounded
    weird = [{"title": None, "summary": 123, "url": "https://x/4", "authority": "high", "freshness_h": True, "source": "S"}]
    out = rank(weird, "test query", "recent_news", {"S": ["recent_news"]})
    assert 0.0 <= out[0]["_score"] <= 1.0
    # determinism: same input -> same order
    docs = [normalize({"title": t, "summary": "", "url": f"https://x/{i}"}, {"name": "S", "authority": 2})
            for i, t in enumerate(["aurora forecast tonight kp", "lunar eclipse date", "aurora borealis kp storm"])]
    assert [d["title"] for d in rank([dict(x) for x in docs], "aurora kp tonight", "current_phenomenon")] == \
           [d["title"] for d in rank([dict(x) for x in docs], "aurora kp tonight", "current_phenomenon")]

def test_input_hardening(monkeypatch):
    from astro_search import core
    monkeypatch.setattr(core, "SQLiteCache", lambda: None)
    eng = AstroSearch()
    eng._sources = []

    class FixtureSource:
        name = "Input fixture"
        intents = ["recent_news"]

        def fetch(self, query, **kwargs):
            assert 1 <= kwargs["max_results"] <= 20
            return [{"title": f"Result {i}", "url": f"https://example.org/{i}",
                     "source": self.name, "summary": str(i)} for i in range(20)]

    monkeypatch.setattr(eng, "_select", lambda *a, **kw: [FixtureSource()])
    monkeypatch.setattr(core, "deduplicate", lambda rows: rows)
    # Clamp at the public entry point, independently of remote availability.
    for bad, expected in ((0, 1), (-5, 1), (10**6, 20), ("8", 8), ("abc", 8), (None, 8)):
        out = eng.search("latest astronomy news", max_results=bad)
        assert out["count"] == expected
    assert classify(None)[0] == "recent_news"  # type: ignore[arg-type]
    assert classify("")[1] == []
    r = normalize(None, None)  # type: ignore[arg-type]
    assert r["title"] == "Untitled" and r["authority"] == 2
    assert to_iso_utc(12345) == ""  # type: ignore[arg-type]
    assert clean_text("", limit=0) == ""
    assert freshness_display(394) == "16d ago" and freshness_display(0) == "just now"
    assert freshness_display(None) is None and freshness_display(True) is None
    assert normalize({"title": "t"}, {})["freshness_display"] is None
