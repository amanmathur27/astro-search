"""Capability coverage, not one regression per user-discovered wording."""
import pytest
from astro_search.capabilities import BODIES, distance_request
from astro_search.core import AstroSearch

TARGETS = [key for key in BODIES if key != "earth"]
PHRASINGS = [
    "how far is {body} from earth",
    "how far is the earth from the {body} right now",
    "what is the distance between earth and {body}",
    "distance from {body} to earth",
    "what's the {body}'s distance from earth",
    "earth-{body} distance",
]
UNITS = [("km", 1.0), ("miles", 1 / 1.609344),
         ("AU", 1 / 149_597_870.7), ("meters", 1000.0)]
NOW = "2026-09-17T12:00:00Z"


@pytest.mark.parametrize("body", TARGETS)
@pytest.mark.parametrize("template", PHRASINGS)
@pytest.mark.parametrize("unit,factor", UNITS)
def test_distance_capability_matrix(monkeypatch, body, template, unit, factor):
    ephem = pytest.importorskip("ephem")
    engine = AstroSearch()
    monkeypatch.setattr(engine, "_fanout", lambda *a, **kw: pytest.fail("distance used network"))
    query = template.format(body=body) + " in " + unit
    out = engine.search(query, now_utc=NOW)
    assert out["answer_status"] == "answered", out
    assert out["interpretation"]["distance"]["target"] == body
    assert out["interpretation"]["distance"]["reference"] == "earth"
    # Checks dispatch and unit conversion against the declared computational backend,
    # not an independent scientific validation of PyEphem's model.
    expected = float(getattr(ephem, BODIES[body]["ephem"])("2026/9/17 12:00:00").earth_distance) * 149_597_870.7 * factor
    assert out["answer"]["value"] == pytest.approx(expected, abs=0.051)
    assert out["answer"]["provenance"]["target"] == body


@pytest.mark.parametrize("query", [
    "how far is sun from mars", "how far is sun from earth and moon",
    "average distance between sun and earth", "distance sun from earth tomorrow",
    "distance sun from earth in 2025", "distance sun from earth in light years",
    "distance between earth and sun and Sirius", "surface distance sun from earth",
    "how far is sun from earth if earth were near mars",
    "distance between earth and sun in km and miles",
    "how far is sun", "distance earth from earth",
])
def test_unsupported_constraints_never_disappear(query):
    assert distance_request(query)["error"]


@pytest.mark.parametrize("body", TARGETS)
def test_interpretation_works_without_optional_backend(body):
    from astro_search.interpretation import interpret
    spec = interpret(f"how far is {body} from earth")
    assert spec.scope == "in_scope"
    assert spec.subject_id == body
    assert spec.clarification is None
