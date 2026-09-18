"""Exercise the registered adapter and public result contract, without live HTTP."""
import json
import pytest
from astro_search.core import AstroSearch
from astro_search import tools
from astro_search.sources import facts


def article(text):
    return {"fetch_ok": True, "title": "Mission specifications", "text": text,
            "final_url": "https://science.nasa.gov/mission/webb/", "truncated": False}


def test_registered_adapter_answers_explicit_fact(monkeypatch):
    calls = []
    def fetch(url):
        calls.append(url)
        return article("James Webb Space Telescope launch mass is 6000 kg.")
    monkeypatch.setattr(facts, "fetch_article", fetch)
    engine = AstroSearch()
    monkeypatch.setattr(tools, "_engine", engine)
    out = json.loads(tools.tool_handler("astro_search", {"query": "JWST launch mass"}))["json"]
    assert calls == [facts.DOCUMENTS["webb"]]
    assert out["answer_status"] == "answered" and out["coverage"] == "full"
    assert out["results"][0]["evidence"]["measurements"][0]["value"] == 6000
    assert out["results"][0]["evidence"]["retrieved_at"]


def test_adapter_failure_is_sanitized_and_not_response_cached(monkeypatch):
    monkeypatch.setattr(facts, "fetch_article", lambda url: {"fetch_ok": False, "error": "secret"})
    out = AstroSearch().search("JWST launch mass")
    assert out["answer_status"] == "retrieval_failed"
    assert out["count"] == 0 and not out["cached"]
    assert "secret" not in json.dumps(out)
    assert out["errors"] == [{"source": "Mission specifications", "error": "invalid_payload"}]


def test_adapter_truncated_or_nonprimary_redirect_is_not_evidence(monkeypatch):
    for changes in ({"truncated": True}, {"final_url": "https://example.org/not-nasa"}):
        payload = article("James Webb Space Telescope launch mass is 6000 kg.")
        payload.update(changes)
        monkeypatch.setattr(facts, "fetch_article", lambda url: payload)
        out = AstroSearch().search("JWST launch mass")
        assert out["answer_status"] == "not_found" and out["count"] == 0


def test_fallback_does_not_bypass_entity_filter(monkeypatch):
    engine = AstroSearch()
    calls = []
    def fanout(*args, **kwargs):
        calls.append(args)
        return ([{"title": "Hubble observes a galaxy", "summary": "Hubble news", "url": "https://example.org"}], [])
    monkeypatch.setattr(engine, "_fanout", fanout)
    out = engine.search("gaganyaan status")
    assert len(calls) == 2
    assert out["count"] == 0 and out["coverage"] == "none"


@pytest.mark.parametrize("query", ["JWST and Hubble launch mass", "JWST launch mass and mirror diameter"])
def test_multiple_requested_facts_need_clarification(monkeypatch, query):
    monkeypatch.setattr(facts, "fetch_article", lambda url: pytest.fail("Must not guess one requested fact"))
    assert AstroSearch().search(query)["answer_status"] == "needs_clarification"


def test_historical_fact_does_not_claim_current_page_is_historical(monkeypatch):
    monkeypatch.setattr(facts, "fetch_article", lambda url: pytest.fail("Not a historical archive"))
    out = AstroSearch().search("JWST launch mass in 2010")
    assert out["answer_status"] == "needs_clarification"
