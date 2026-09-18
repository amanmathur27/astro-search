"""Offline metadata and relevance regressions."""
from astro_search.normalizer import normalize
from astro_search.ranker import rank


def test_description_preserved_beyond_display_limit():
    text = 'background ' * 60 + 'Roman observatory launch mass specifications'
    row = normalize({'title': 'Specifications', 'summary': text}, {'name': 'fixture'})
    assert len(row['summary']) <= 400
    assert 'launch mass' in row['metadata']['feed_description']


def test_html_metadata_and_passages():
    from astro_search.metadata import extract_metadata
    out = extract_metadata('''<html><head><title>Mission &amp; facts</title>
      <meta content="Roman mission specifications" name="description">
      <meta property="og:title" content="Roman observatory">
      <script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-01-01","dateModified":"2026-02-01"}</script>
      </head><body><nav><p>newsletter navigation</p></nav><article>
      <h1>Roman facts</h1><p>The observatory has not launched.</p>
      <p>Launch mass is not the rocket capacity.</p></article></body></html>''')
    assert out['meta_description'] == 'Roman mission specifications'
    assert out['date_published'] == '2026-01-01'
    assert out['date_modified'] == '2026-02-01'
    assert out['passages'] == ['The observatory has not launched.', 'Launch mass is not the rocket capacity.']
    assert out['field_sources']['date_published'] == 'json_ld'


def test_metadata_duplicates_do_not_inflate_score():
    a = {'title': 'Roman launch mass', 'summary': 'Roman launch mass'}
    b = {**a, 'metadata': {'og_title': a['title'], 'meta_description': a['summary']}}
    out = rank([a, b], 'Roman launch mass', 'fact_lookup')
    assert out[0]['_score'] == out[1]['_score']


def test_relevance_before_authority_and_freshness():
    rows = [ {'title': 'Mars weather', 'summary': 'Daily atmospheric report', 'authority': 3, 'freshness_h': 0},
             {'title': 'Roman mass specifications', 'summary': 'Observatory launch mass', 'authority': 1, 'freshness_h': 99999} ]
    assert rank(rows, 'Roman launch mass', 'fact_lookup')[0]['title'] == 'Roman mass specifications'


def test_query_excerpt_is_verbatim_and_not_evidence():
    from astro_search.relevance import annotate
    row = {'title': 'Roman facts', 'summary': 'Welcome', 'metadata': {
        'passages': ['General mission background.', 'Roman was not launched on January 1, 2026.']}}
    annotate(row, 'Roman launched January', 'mission_status')
    assert row['excerpt']['text'] == 'Roman was not launched on January 1, 2026.'
    assert row['excerpt']['source'] == 'article_passage'
    assert row['relevance']['evidence_status'] == 'unverified'
    assert 'evidence' not in row


def test_search_enriches_reranks_and_preserves_indirect_status(monkeypatch):
    from astro_search.core import AstroSearch
    from astro_search import enrichment
    engine = AstroSearch()
    engine._sources = []
    rows = [normalize({'title': 'Roman discoveries', 'summary': 'Roman galaxies',
                       'url': 'https://example.org/galaxies'}, {'name': 'fixture', 'source_type': 'rss'}),
            normalize({'title': 'Roman mission update', 'summary': 'Roman mission background',
                       'url': 'https://example.org/instruments'}, {'name': 'fixture', 'source_type': 'rss'})]
    monkeypatch.setattr(engine, '_fanout', lambda *args, **kwargs: (rows, []))
    calls = []
    quote = 'Roman spectroscopy instruments reveal details of exoplanet atmospheres.'
    def fetch(url, **kwargs):
        calls.append(url)
        assert kwargs['deadline'] > 0
        passage = quote if url.endswith('instruments') else 'Roman galaxies are distant.'
        return {'fetch_ok': True, 'metadata': {'passages': [passage]}, 'final_url': url,
                'retrieved_at': '2026-09-17T12:00:00Z'}
    monkeypatch.setattr(enrichment, 'fetch_article', fetch)
    out = engine.search('Roman telescope spectroscopy instruments', now_utc='2026-09-17T12:00:00Z')
    assert len(calls) == 2
    assert out['results'][0]['url'].endswith('instruments')
    assert out['results'][0]['excerpt']['text'] == quote
    assert out['results'][0]['excerpt']['source'] == 'article_passage'
    assert out['answer_status'] == 'indirect'
    assert not out.get('answer')
    assert out['enrichment']['completed'] == 2
