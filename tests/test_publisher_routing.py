"""
Tests for publisher domain routing and 2026 feed syndication
"""
from astro_search import AstroSearch
from astro_search.sources.gnews import detected_publisher_domain, has_recency


def test_publisher_domain_detection():
    assert detected_publisher_domain("articles from space.com today") == "space.com"
    assert detected_publisher_domain("latest posts on phys.org") == "phys.org"
    assert detected_publisher_domain("sky & telescope moon news") == "skyandtelescope.org"
    assert detected_publisher_domain("planetary society updates") == "planetary.org"
    assert detected_publisher_domain("spaceflight now falcon 9") == "spaceflightnow.com"
    assert detected_publisher_domain("general astronomy news") is None


def test_publisher_recency_flag():
    assert has_recency("space.com articles") is True
    assert has_recency("content in phys.org") is True
    assert has_recency("astronomy today") is True


def test_source_selection_for_named_publisher():
    engine = AstroSearch()
    sources = engine._select(intent="recent_news", entities=[], category="all",
                             allow_gnews=True, query="astronomy content posted in space.com today")
    names = [s.name for s in sources]
    assert "Google News" in names


def test_source_selection_for_physorg():
    engine = AstroSearch()
    sources = engine._select(intent="recent_news", entities=[], category="all",
                             allow_gnews=False, query="latest discoveries on phys.org")
    names = [s.name for s in sources]
    assert "Phys.org" in names
