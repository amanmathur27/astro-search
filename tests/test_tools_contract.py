"""Public routing contracts with deterministic source fixtures."""
import json
import pytest
from astro_search import core, tools
from astro_search.intent import classify


def test_specialist_selection(monkeypatch):
    monkeypatch.setenv("ASTRO_ADS_KEY", "fixture-only")
    engine = core.AstroSearch()
    intent, entities = classify("where is the ISS")
    assert "Open Notify ISS" in {s.name for s in engine._select(intent, entities, "all")}
    intent, entities = classify("papers on exoplanet atmospheres")
    assert {s.name for s in engine._select(intent, entities, "papers")} == {"arXiv", "NASA ADS"}
    monkeypatch.delenv("ASTRO_ADS_KEY")
    assert [s.name for s in engine._select("research_lookup", ["solar flare"], "papers")] == ["arXiv"]


@pytest.mark.parametrize("query", ["emission spectrum", "explain fission", "transmission spectrum"])
def test_no_substring_mission_intent(query):
    assert classify(query)[0] != "mission_status"


def test_papers_public_contract(monkeypatch):
    engine = core.AstroSearch()
    calls = []

    class PaperSource:
        name = "arXiv"
        intents = ["research_lookup"]
        entities = ["*"]

        def is_available(self):
            return True

        def fetch(self, query, **kw):
            calls.append(kw)
            return [{"title": "Exoplanet atmospheres", "summary": "exoplanet study",
                     "url": "https://arxiv.org/abs/fixture", "source": self.name,
                     "category": "papers", "published": "2000-01-01T00:00:00Z"},
                    {"title": "News leak", "category": "news", "url": "https://example.org/news"}]

    engine._sources = [PaperSource()]
    monkeypatch.setattr(tools, "_engine", engine)
    out = json.loads(tools.tool_handler("astro_papers", {"query": "exoplanet atmospheres", "topic": "planets"}))["json"]
    assert out["intent"] == "research_lookup" and out["count"] == 1
    assert out["results"][0]["category"] == "papers"
    assert calls[0]["topic"] == "planets"
    engine.search_papers("exoplanet atmospheres", topic="cosmology")
    assert len(calls) == 2  # topic participates in cache identity


def test_empty_sources_are_not_an_error():
    engine = core.AstroSearch()
    engine._sources = []
    assert engine.search("explain gravity")["count"] == 0


def test_entity_family_alternatives():
    rows = [{"title": "Gaganyaan mission", "summary": "", "url": "https://example.org"}]
    kept, backstop = core.AstroSearch()._entity_gate(rows, ["isro"], 8)
    assert kept == rows and not backstop
