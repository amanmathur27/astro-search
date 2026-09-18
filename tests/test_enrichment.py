"""Operational budgets and metadata-only fallback, offline."""
import time
from copy import deepcopy
from astro_search.enrichment import Enricher
from astro_search.normalizer import normalize


def candidates():
    return [normalize({'title': 'Roman spectroscopy', 'summary': 'Roman research',
                       'url': f'https://host{i % 2}.example/{i}'},
                      {'name': 'fixture', 'source_type': 'rss'}) for i in range(8)]


def test_budget_cache_and_no_evidence_promotion(monkeypatch):
    from astro_search import enrichment
    calls = []
    def fetch(url, **kw):
        calls.append(url)
        return {'fetch_ok': True, 'metadata': {'passages': ['Roman spectroscopy observations.']}}
    monkeypatch.setattr(enrichment, 'fetch_article', fetch)
    enricher = Enricher()
    for _ in range(2):
        rows = candidates()
        report = enricher.enrich(rows, time.monotonic() + 5)
        assert report['selected'] == report['completed'] == 3
        assert report['errors'] == []
        assert all('evidence' not in r for r in rows)
    assert len(calls) == 3


def test_expired_deadline_never_fetches(monkeypatch):
    from astro_search import enrichment
    def forbidden(*a, **kw):
        raise AssertionError('must not fetch')
    monkeypatch.setattr(enrichment, 'fetch_article', forbidden)
    report = Enricher().enrich(candidates(), time.monotonic() - 1)
    assert report['completed'] == 0
    assert all(e['error'] == 'deadline_exceeded' for e in report['errors'])


def test_failed_fetch_preserves_source_metadata(monkeypatch):
    from astro_search import enrichment
    monkeypatch.setattr(enrichment, 'fetch_article', lambda *a, **kw: {'fetch_ok': False})
    rows = candidates()
    before = deepcopy(rows)
    report = Enricher().enrich(rows, time.monotonic() + 5)
    assert report['completed'] == 0
    assert len(report['errors']) == 3
    assert [r['metadata'] for r in rows] == [r['metadata'] for r in before]


def test_entity_beyond_summary_cutoff_survives():
    from astro_search.core import AstroSearch
    row = normalize({'title': 'Technical documentation',
                     'summary': 'background ' * 60 + 'Roman observatory spectroscopy'}, {})
    assert 'Roman' not in row['summary']
    kept, _ = AstroSearch()._entity_gate([row], ['roman'], 8)
    assert kept == [row]


def test_malformed_and_long_html_metadata():
    from astro_search.metadata import extract_metadata
    md = extract_metadata('<script type="application/ld+json">{broken</script>'
                          '<article><p>' + 'long ' * 500 + '</p><p>Roman was not launched.</p></article>')
    assert md['passages'] == ['Roman was not launched.']
    assert md['passages_omitted']


def test_website_schema_not_used_as_article_date():
    from astro_search.metadata import extract_metadata
    md = extract_metadata('<script type="application/ld+json">'
                          '{"@type":"WebSite","datePublished":"1990-01-01"}</script>')
    assert 'date_published' not in md
