"""All declared tools preserve caller arguments and JSON envelopes."""
import json
from unittest.mock import Mock
import pytest
from astro_search import tools
from astro_search.sources import fetch, jpl


@pytest.mark.parametrize('name,method,args,expected', [
    ('astro_search', 'search',
     dict(query='moon', category='events', max_results=3, lat=0, lon=0,
          timezone='Asia/Kolkata', now_utc='2026-09-17T12:00:00Z', trends=True, edition='IN'),
     dict(query='moon', category='events', max_results=3, lat=0, lon=0,
          tz='Asia/Kolkata', now_utc='2026-09-17T12:00:00Z', trends=True, edition='IN')),
    ('astro_events', 'get_celestial_events',
     dict(year=2027, lat=0, lon=0, timezone='UTC', now_utc='2026-09-17T12:00:00Z'),
     dict(year=2027, lat=0, lon=0, tz='UTC', now_utc='2026-09-17T12:00:00Z')),
    ('astro_papers', 'search_papers',
     dict(query='atmospheres', topic='planets', max_results=7),
     dict(query='atmospheres', topic='planets', max_results=7)),
])
def test_argument_forwarding(monkeypatch, name, method, args, expected):
    engine = Mock()
    getattr(engine, method).return_value = {'count': 0, 'markdown': 'fixture'}
    monkeypatch.setattr(tools, '_engine', engine)
    result = json.loads(tools.tool_handler(name, args))
    getattr(engine, method).assert_called_once_with(**expected)
    assert result == {'json': {'count': 0, 'markdown': 'fixture'}, 'markdown': 'fixture'}


def test_fetch_argument_and_failure_envelope(monkeypatch):
    monkeypatch.setattr(tools, '_engine', Mock())
    response = dict(title='', text='', fetch_ok=False, error='fixture unavailable')
    mocked = Mock(return_value=response)
    monkeypatch.setattr(fetch, 'fetch_article', mocked)
    out = json.loads(tools.tool_handler('astro_fetch', {'url': 'https://example.org/article'}))
    mocked.assert_called_once_with('https://example.org/article')
    assert out['json'] == response
    assert isinstance(out['markdown'], str)


@pytest.mark.parametrize('payload', [{}, {'object': {}}, {'object': []}, {'object': {'fullname': 'Apophis'}}])
def test_sbdb_missing_identity_is_diagnostic(monkeypatch, payload):
    response = Mock(ok=True)
    response.json.return_value = payload
    monkeypatch.setattr(jpl.requests, 'get', Mock(return_value=response))
    errors = []
    assert jpl.JPLSource().fetch('asteroid Apophis', _errors=errors) == []
    assert errors == [{'source': 'JPL', 'error': 'ValueError'}]
