"""Caught adapter failures must reach the orchestrator without leaking secrets."""
import time
import pytest
from astro_search.core import AstroSearch
from astro_search.sources import ads, arxiv, gnews, iss, jpl, nasa, noaa, rss, tap, usno


@pytest.mark.parametrize('factory,query,context', [
    (ads.ADSSource, 'galaxies', {}),
    (arxiv.ArxivSource, 'galaxies', {}),
    (gnews.GoogleNewsSource, 'latest astronomy news', {}),
    (iss.ISSSource, 'where is the ISS', {}),
    (jpl.JPLSource, 'asteroid Apophis', {'intent': 'object_lookup'}),
    (nasa.NASASource, 'asteroid close approach', {}),
    (noaa.NOAASource, 'aurora', {}),
    (lambda: rss.RSSSource({'name': 'Fixture feed', 'url': 'https://example.org/feed'}), 'moon', {}),
    (tap.ExoplanetSource, 'Kepler-22 b', {}),
    (usno.USNOSource, 'moon phases', {'intent': 'periodic_event', 'year': 2026}),
])
def test_adapter_errors_are_visible_and_not_cached(monkeypatch, factory, query, context):
    monkeypatch.setenv('ASTRO_ADS_KEY', 'fixture-secret')
    monkeypatch.setattr(arxiv, '_throttle', lambda: None)
    engine = AstroSearch()
    rows, errors = engine._fanout([factory()], query, time.monotonic() + 2,
                                  now_utc='2026-09-17T12:00:00Z', **context)
    assert errors
    assert all(set(error) == {'source', 'error'} for error in errors)
    assert 'fixture-secret' not in str(errors)
    assert not engine._runtime.cache._store


def test_failed_search_is_not_response_cached():
    from astro_search.sources.base import BaseSource
    class Source(BaseSource):
        name = 'Failure fixture'
        intents = ['concept_explanation']
        def fetch(self, query, **kwargs):
            raise ValueError('do not cache an outage')
    engine = AstroSearch()
    engine._sources = [Source()]
    result = engine.search('explain gravity')
    assert result['errors']
    assert not engine.mem._store
