"""Scope, ambiguity, and extractive evidence acceptance tests."""
import pytest
from astro_search.core import AstroSearch
from astro_search.interpretation import interpret
from astro_search.evidence import filter_evidence


@pytest.mark.parametrize("query", ["iPhone 17 Pro price", "latest iPhone price", "roman numerals", "mercury poisoning"])
def test_out_of_scope_never_fans_out(monkeypatch, query):
    engine = AstroSearch()
    def forbidden(*args, **kwargs):
        pytest.fail("Out-of-scope query reached retrieval")
    monkeypatch.setattr(engine, "_fanout", forbidden)
    out = engine.search(query, trends=True)
    assert out["answer_status"] == "out_of_scope"
    assert out["count"] == 0 and out["results"] == []


def test_roman_payload_asks_for_definition_before_retrieval(monkeypatch):
    engine = AstroSearch()
    monkeypatch.setattr(engine, "_fanout", lambda *a, **kw: pytest.fail("Ambiguous mass retrieval"))
    out = engine.search("what is the payload weight of the recently launched roman nancy grace telescope")
    assert out["answer_status"] == "needs_clarification"
    spec = out["interpretation"]
    assert spec["subject"] == "Nancy Grace Roman Space Telescope"
    assert spec["property"] == "payload_mass"
    assert spec["assumptions"] == [{"claim": "recently_launched", "status": "unverified"}]
    assert out["results"] == []


def document(text, url="https://science.nasa.gov/fixture"):
    return {"title": "James Webb Space Telescope", "summary": text, "url": url,
            "extra": {"document_text": text, "document_url": url,
                      "document_fetch_ok": True, "retrieved_at": "2026-09-17T00:00:00Z"}}


@pytest.mark.parametrize("text", [
    "James Webb Space Telescope launch mass is 6000 kg.",
    "The James Webb Space Telescope has a launch mass of 6,000 kilograms.",
])
def test_explicit_evidence_has_quote_units_and_citation(text):
    rows, status = filter_evidence([document(text)], interpret("JWST launch mass"))
    assert status == "answered"
    assert rows[0]["evidence"]["measurements"][0]["normalized_value"] == 6000
    assert rows[0]["evidence"]["citation_url"] == "https://science.nasa.gov/fixture"


@pytest.mark.parametrize("text", [
    "James Webb Space Telescope launch mass is not 6000 kg.",
    "James Webb Space Telescope launch mass is 6000 km.",
    "James Webb Space Telescope launch mass is 6000 kg according to a rumor.",
    "James Webb Space Telescope launch mass is 6000 kg?",
    "James Webb Space Telescope launch mass is 6000 kg/s.",
    "James Webb Space Telescope mirror diameter is 6 m.",
    "James Webb Space Telescope launches. Falcon launch mass is 6000 kg.",
    "James Webb Space Telescope launch mass is 0 kg.",
    "James Webb Space Telescope launch mass is -6000 kg.",
])
def test_wrong_property_subject_units_and_negation_rejected(text):
    rows, status = filter_evidence([document(text)], interpret("JWST launch mass"))
    assert rows == [] and status == "not_found"


def test_snippet_and_tertiary_source_are_not_direct_evidence():
    text = "James Webb Space Telescope launch mass is 6000 kg."
    snippet = document(text)
    snippet["extra"] = {}
    for row in (snippet, document(text, "https://en.wikipedia.org/wiki/James_Webb_Space_Telescope"),
                document(text, "https://nasa.gov.example.com/fake")):
        assert filter_evidence([row], interpret("JWST launch mass"))[1] == "not_found"


def test_conflict_is_checked_before_result_limit(monkeypatch):
    engine = AstroSearch()
    engine._sources = []
    rows = [document(f"James Webb Space Telescope launch mass is {n} kg.") for n in (6000, 7000)]
    monkeypatch.setattr(engine, "_fanout", lambda *a, **kw: (rows, []))
    out = engine.search("JWST launch mass", max_results=1)
    assert out["answer_status"] == "conflicting_evidence"
    assert out["coverage"] != "full"


def test_entity_gate_has_no_filler():
    rows, backstop = AstroSearch()._entity_gate([{"title": "Hubble news", "summary": ""}], ["gaganyaan"], 8)
    assert rows == [] and not backstop
