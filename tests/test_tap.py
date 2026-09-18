"""Object-name resolution and request propagation without live TAP queries."""
from astro_search.sources import tap


def test_name_not_final_query_word(monkeypatch):
    queries = []
    def query(base, adql, **kwargs):
        queries.append(adql)
        return [{"pl_name": "Kepler-22 b"}]
    monkeypatch.setattr(tap, "query_tap", query)
    rows = tap.ExoplanetSource().fetch("What is the orbital period of Kepler-22 b in days?")
    assert rows[0]["title"] == "Exoplanet Kepler-22 b"
    assert "Kepler-22 b" in queries[0] and "days" not in queries[0]
    assert tap.ExoplanetSource().fetch("exoplanet atmospheres") == []
    assert len(queries) == 1


def test_explicit_name_and_sql_literal_escaping(monkeypatch):
    queries = []
    monkeypatch.setattr(tap, "query_tap", lambda base, adql, **kw: queries.append(adql) or [])
    tap.ExoplanetSource().fetch("lookup", object_name="O'Brien")
    assert "O''Brien" in queries[0]


def test_catalog_queries_reach_tap_through_public_tool(monkeypatch):
    import json
    from astro_search import core, tools
    from astro_search.intent import classify

    for query, name in (("HD 209458", "HD 209458 b"),
                        ("What is the orbital period of Kepler-22 b in days?", "Kepler-22 b")):
        engine = core.AstroSearch()
        # Keep actual routing and adapters; only replace external data access.
        queries = []
        def query_tap(base, adql, **kwargs):
            queries.append(adql)
            return [{"pl_name": name, "pl_orbper": 3.5}]
        monkeypatch.setattr(tap, "query_tap", query_tap)
        monkeypatch.setattr(tools, "_engine", engine)
        out = json.loads(tools.tool_handler("astro_search", {"query": query}))["json"]
        assert out["intent"] == "object_lookup"
        assert len(queries) == 1
        assert any(r["source"] == "Exoplanet Archive" and name in r["title"]
                   for r in out["results"])
        assert out["entity_coverage"] == "matched"
        # relevance only: object data returned, not verified evidence for the value
        assert out["coverage"] == "partial"

    assert classify("latest news about HD 209458")[0] == "recent_news"
    assert classify("research on Kepler-22 b")[0] == "research_lookup"

