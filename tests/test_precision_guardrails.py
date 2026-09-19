"""Tests for Precision Guardrails, Polysemy Context Filters,
Agent Evidence Packaging, Object Comparisons, and Resiliency."""
import pytest
import json
from unittest.mock import Mock
from astro_search.relevance import check_polysemy_collision, POLYSEMY_GUARDS, ASTRO_GENERIC_STOP, tokens
from astro_search.intent import CATALOG_RE, KNOWN_ENTITIES
from astro_search.ranker import rank
from astro_search.core import AstroSearch, OBJECT_DATA
from astro_search.runtime import SourceRuntime
from astro_search.validation import search_inputs
from astro_search.tools import tool_handler, TOOL_DECLARATIONS


def test_polysemy_guards_detection():
    """Verify non-astronomy collisions are strongly penalized."""
    # Java IDE collision
    q_toks = tokens("eclipse IDE download Java plugin")
    doc_text = "Eclipse IDE 2024 for Java Developers. Download eclipse tools and maven plugins."
    mult = check_polysemy_collision(q_toks, doc_text)
    assert mult < 0.5

    # Legitimate astronomy eclipse
    q_toks_astro = tokens("total solar eclipse path totality")
    doc_text_astro = "Total Solar Eclipse of August 2026. The path of totality passes through Spain and Iceland."
    mult_astro = check_polysemy_collision(q_toks_astro, doc_text_astro)
    assert mult_astro == 1.0

    # Kubernetes cluster collision
    q_toks_k8s = tokens("kubernetes cluster node autoscaling")
    doc_text_k8s = "Deploying a 3-node cluster in AWS cloud. Configure your server cluster and container pods."
    mult_k8s = check_polysemy_collision(q_toks_k8s, doc_text_k8s)
    assert mult_k8s < 0.5

    # Globular star cluster
    q_toks_cluster = tokens("Hercules globular star cluster M13")
    doc_text_cluster = "Messier 13: The Great Globular Cluster in Hercules. M13 contains hundreds of thousands of stars."
    mult_cluster = check_polysemy_collision(q_toks_cluster, doc_text_cluster)
    assert mult_cluster == 1.0


def test_generic_astro_stopwords_and_entity_regex():
    """Check that ASTRO_GENERIC_STOP and CATALOG_RE are well-defined."""
    assert "space" in ASTRO_GENERIC_STOP
    assert "astronomy" in ASTRO_GENERIC_STOP
    assert "telescope" in ASTRO_GENERIC_STOP
    assert "universe" in ASTRO_GENERIC_STOP

    # Regex matches
    assert CATALOG_RE.search("TRAPPIST-1e exoplanet")
    assert CATALOG_RE.search("HD 209458 b transit")
    assert CATALOG_RE.search("Kepler-452b discovery")
    assert CATALOG_RE.search("GJ 1214 b atmosphere")
    assert CATALOG_RE.search("Proxima Centauri b")


def test_entity_anchor_token_normalization():
    """Verify hyphenated catalog targets match tokenized doc fields."""
    rows = [
        {"title": "TRAPPIST-1e atmosphere analysis", "summary": "Study of TRAPPIST-1e", "url": "https://example.com/1"},
        {"title": "General space news", "summary": "Latest universe observatory updates", "url": "https://example.com/2"}
    ]
    ranked = rank(rows, "TRAPPIST-1e habitability", "research_lookup")
    assert ranked[0]["title"] == "TRAPPIST-1e atmosphere analysis"
    assert ranked[0]["_score"] > ranked[1]["_score"]


def test_compare_objects_known_and_unknown():
    """Verify physical comparison matrix tool for AI agents."""
    engine = AstroSearch()
    comp = engine.compare_objects(["Europa", "Titan"])
    assert "objects" in comp
    assert "Europa" in comp["comparison"]
    assert "Titan" in comp["comparison"]
    assert comp["comparison"]["Europa"]["type"] == "Ocean Moon (Jupiter)"
    assert comp["comparison"]["Titan"]["type"] == "Icy Moon (Saturn)"
    assert "markdown_table" in comp
    assert "Ocean Moon" in comp["markdown_table"]

    # With an unknown object
    comp_mixed = engine.compare_objects(["Mars", "FictionalPlanet999"])
    assert "Mars" in comp_mixed["comparison"]
    assert "Fictionalplanet999" in comp_mixed["comparison"]
    assert comp_mixed["comparison"]["Fictionalplanet999"]["type"] == "Unknown / Uncataloged"


def test_compare_objects_deduplication():
    """Verify duplicate names in comparison array are safely deduplicated."""
    engine = AstroSearch()
    comp = engine.compare_objects(["Mars", "Mars", "Europa", "mars"])
    assert len(comp["objects"]) == 2
    assert "Mars" in comp["comparison"]
    assert "Europa" in comp["comparison"]


def test_compare_objects_tool_handler():
    """Verify tool_handler executes astro_compare successfully."""
    raw = tool_handler("astro_compare", {"objects": ["Mars", "Jupiter"]})
    data = json.loads(raw)
    assert "json" in data
    assert "markdown" in data
    assert "Mars" in data["json"]["comparison"]
    assert "Jupiter" in data["json"]["comparison"]


def test_search_evidence_package_structure():
    """Verify search_as_evidence_package returns structured grounding payload."""
    engine = AstroSearch()
    res = engine.search_as_evidence_package("James Webb Space Telescope exoplanet atmosphere")
    assert "query" in res
    assert "claims" in res
    assert "primary_citations" in res
    assert "direct_quotes" in res
    assert "source_authority" in res
    assert "evidence_lock_status" in res
    assert isinstance(res["primary_citations"], list)
    assert isinstance(res["claims"], list)


def test_search_deltas_with_since_date():
    """Verify search_deltas passes since_date filter and updates out dictionary."""
    engine = AstroSearch()
    # Mock source to verify date filtering
    mock_source = Mock()
    mock_source.name = "MockNews"
    mock_source.intents = ["recent_news"]
    mock_source.entities = ["*"]
    mock_source.authority = 2
    mock_source.is_available = Mock(return_value=True)
    mock_source.fetch = Mock(return_value=[
        {"title": "Old news", "summary": "Old story", "url": "https://example.com/old", "published": "2026-01-01T00:00:00Z", "source": "MockNews", "category": "news"},
        {"title": "New news", "summary": "New story", "url": "https://example.com/new", "published": "2026-03-15T00:00:00Z", "source": "MockNews", "category": "news"}
    ])
    engine._sources = [mock_source]
    res = engine.search(query="astronomy news", since_date="2026-03-01", now_utc="2026-03-20T00:00:00Z")
    assert res["count"] == 1
    assert len(res["results"]) == 1
    assert res["results"][0]["title"] == "New news"
    assert "Old news" not in res["markdown"]


def test_search_deltas_empty_since_date():
    """Verify search_deltas with default empty since_date works cleanly."""
    engine = AstroSearch()
    res = engine.search_deltas("solar flare", since_date="")
    assert "results" in res
    assert "count" in res


def test_validation_of_new_parameters():
    """Verify validation allows mode and valid since_date, rejects invalid values."""
    # Valid (does not raise)
    search_inputs(query="lunar eclipse", category="all", trends=False, edition=None, topic=None, mode="evidence", since_date="2026-03-01")
    search_inputs(query="lunar eclipse", category="all", trends=False, edition=None, topic=None, mode="standard", since_date="")
    search_inputs(query="lunar eclipse", category="all", trends=False, edition=None, topic=None, mode="standard", since_date=None)

    # Invalid mode
    with pytest.raises(ValueError, match="mode must be 'standard' or 'evidence'"):
        search_inputs(query="lunar eclipse", category="all", trends=False, edition=None, topic=None, mode="unsupported_mode")

    # Invalid since_date
    with pytest.raises(ValueError, match="since_date must be in YYYY-MM-DD format"):
        search_inputs(query="lunar eclipse", category="all", trends=False, edition=None, topic=None, since_date="01-03-2026")


def test_source_runtime_circuit_breaker_status():
    """Test circuit breaker health monitoring and reset with both string and object sources."""
    runtime = SourceRuntime()
    mock_src = Mock()
    mock_src.name = "NASA_API"

    status_clean = runtime.circuit_status(mock_src)
    assert status_clean["failures"] == 0
    assert status_clean["is_open"] is False

    # Simulate failures using object
    for _ in range(5):
        runtime._failed(mock_src, runtime._failures.get("NASA_API", (0, 0))[0])

    # Query via string name
    status_str = runtime.circuit_status("NASA_API")
    assert status_str["failures"] >= 5
    assert status_str["is_open"] is True

    # Query via object
    status_obj = runtime.circuit_status(mock_src)
    assert status_obj["failures"] >= 5
    assert status_obj["is_open"] is True

    # Reset via string name
    runtime.reset_circuit("NASA_API")
    status_reset = runtime.circuit_status(mock_src)
    assert status_reset["failures"] == 0
    assert status_reset["is_open"] is False
