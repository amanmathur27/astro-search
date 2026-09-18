"""Precision retrieval regressions. All source responses are offline fixtures."""
from astro_search.core import AstroSearch


def test_webb_launch_mass_rejects_related_news(monkeypatch):
    engine = AstroSearch()
    engine._sources = []
    monkeypatch.setattr(engine, "_fanout", lambda *a, **kw: ([{
        "title": "James Webb Space Telescope images a galaxy",
        "summary": "James Webb Space Telescope observes distant galaxies.",
        "url": "https://science.nasa.gov/example", "source": "Fixture",
        "authority": 3,
    }], []))
    out = engine.search("James Webb launch mass")
    assert out["results"] == []
    assert out["answer_status"] == "not_found"
    assert out["coverage"] == "none"
    assert out["interpretation"]["property"] == "launch_mass"
