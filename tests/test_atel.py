"""ATel integration uses offline RDF fixtures and the public search pipeline."""
import pytest
import requests
from astro_search.core import AstroSearch
from astro_search.intent import classify
from astro_search.interpretation import interpret
from astro_search.sources.rss import RSS_FEEDS, RSSSource

XML = '''<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel rdf:about="https://www.astronomerstelegram.org/?rss"><title>Top ATels</title></channel>
<item rdf:about="https://www.astronomerstelegram.org/?read=18053">
<title>ATel 18053: Optical monitoring of Nova Sge 2026</title>
<link>https://www.astronomerstelegram.org/?read=18053</link>
<description>Preliminary spectroscopic observations of the nova.</description>
<dc:date>2026-09-17T14:29:25-00:00</dc:date><author>Fixture Observer</author>
<identifier>ATel18053</identifier></item>
<item rdf:about="https://www.astronomerstelegram.org/?read=18052">
<title>ATel 18052: GRB 260917A optical follow-up</title>
<link>https://www.astronomerstelegram.org/?read=18052</link>
<description>A candidate counterpart; not yet confirmed.</description>
<dc:date>2026-09-17T12:00:00Z</dc:date><identifier>ATel18052</identifier></item>
</rdf:RDF>'''


def config():
    return next(c for c in RSS_FEEDS if c['name'] == "The Astronomer's Telegram")


def mock_feed(monkeypatch, payload=XML):
    class Response:
        content = payload.encode()
        def raise_for_status(self):
            pass
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: Response())


@pytest.mark.parametrize('query', ['latest ATel reports', 'latest astronomical transient alerts',
                                  'GRB 260917A follow-up reports', 'ATel 18053'])
def test_alert_routing(query):
    intent, entities = classify(query)
    assert intent == 'alert_lookup'
    assert interpret(query).scope == 'in_scope'
    selected = AstroSearch()._select(intent, entities, 'all')
    assert [s.name for s in selected] == ["The Astronomer's Telegram"]


def test_no_alerts_for_unrelated_queries():
    engine = AstroSearch()
    for query in ['latest iPhone alerts', 'latest telescope news', 'papers on supernovae', 'explain gamma ray bursts']:
        intent, entities = classify(query)
        assert intent != 'alert_lookup'
        assert "The Astronomer's Telegram" not in [s.name for s in engine._select(intent, entities, 'all')]


def test_rdf_provenance_and_exact_id(monkeypatch):
    mock_feed(monkeypatch)
    rows = RSSSource(config()).fetch('ATel 18053', intent='alert_lookup')
    assert len(rows) == 1
    row = rows[0]
    assert row['published'] == '2026-09-17T14:29:25Z'
    assert row['published_kind'] == 'issued'
    assert row['extra']['report_id'] == 'ATel18053'
    assert row['extra']['publication_status'] == 'rapid_report_not_peer_reviewed'
    assert row['authors'] == ['Fixture Observer']
    assert row['event_date'] is None
    assert RSSSource(config()).fetch('ATel 1805', intent='alert_lookup') == []
    assert RSSSource(config()).fetch('ATel nova UnknownObject', intent='alert_lookup') == []


def test_public_search_preliminary_not_answer(monkeypatch):
    mock_feed(monkeypatch)
    engine = AstroSearch()
    monkeypatch.setattr(engine._enricher, 'enrich', lambda *a: {'errors': [], 'completed': 0})
    out = engine.search('GRB 260917A follow-up reports', now_utc='2026-09-17T16:00:00Z')
    assert out['intent'] == 'alert_lookup'
    assert out['answer_status'] == 'indirect'
    assert not out.get('answer')
    assert out['count'] == 1
    assert out['results'][0]['extra']['report_id'] == 'ATel18052'
    assert out['results'][0]['relevance']['evidence_status'] == 'unverified'
    assert out['alert_coverage']['complete_archive'] is False
    assert 'not peer-reviewed' in out['markdown']


@pytest.mark.parametrize('payload', ['<html>service unavailable</html>', '<rdf:RDF broken'])
def test_invalid_feed_diagnostic(monkeypatch, payload):
    mock_feed(monkeypatch, payload)
    errors = []
    assert RSSSource(config()).fetch('latest ATel reports', _errors=errors) == []
    assert errors and errors[0]['source'] == "The Astronomer's Telegram"


def test_failed_feed_is_not_no_discoveries(monkeypatch):
    def fail(*a, **kw):
        raise requests.Timeout('private transport detail')
    monkeypatch.setattr(requests, 'get', fail)
    out = AstroSearch().search('latest ATel reports', now_utc='2026-09-17T16:00:00Z')
    assert out['answer_status'] == 'retrieval_failed'
    assert out['errors']
    assert 'private transport detail' not in str(out)
