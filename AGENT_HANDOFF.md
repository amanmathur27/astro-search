# AstroSearch v2 — Complete Agent Handoff
> Everything the building agent needs. Read this fully before writing any code.

---

## 1. What You Are Building

**AstroSearch** is a domain-specific astronomy search engine packaged as a Python library.

It is NOT a web app, NOT a standalone server, NOT a general-purpose search engine.

It is a **Python package** that:
- Accepts a natural language query
- Routes it to the right astronomy data sources (NASA, USNO, JPL, NOAA, RSS feeds, arXiv)
- Returns clean, structured results
- Exposes itself as Gemini/OpenAI-compatible tool declarations

It works exactly like a "Brave Search API" or "Tavily API" — but purpose-built for astronomy, 100% free, no paid API keys required for core functionality.

---

## 2. Context: Where This Fits

**Owner:** Aman — runs Stellar Illusion (stellarillusion.com), an astronomy education platform.

**Existing system:**
- Stack: GitHub Actions (scheduler), Gemini 3.7 Flash via Google AI Studio (free tier), Python scripts
- 14+ AI subagents doing: research, writing, editing, content analysis, stale content detection, competitor gap analysis, SEO strategy, analytics blending
- All agents run as Python scripts in GitHub Actions workflows
- LLM: `gemini-3.7-flash` (Google AI Studio, free tier — NO grounding feature available)
- AstroSearch replaces the missing grounding feature for astronomy queries specifically

**Why a separate repo:**
- AstroSearch is infrastructure/tooling, not an agent
- Multiple agent repos will consume it (current agents repo + future projects)
- Install via `pip install git+https://github.com/USER/astro-search.git@main`
- Independent versioning, testing, and feed health monitoring

**How agents consume it:**
```python
from astro_search import TOOL_DECLARATIONS, tool_handler
# That's the entire integration surface
```

**Which agents get which tools:**

| Agent Type | Tools Exposed |
|------------|---------------|
| Research agent | `astro_search`, `astro_fetch`, `astro_papers` |
| Topic scout | `astro_search`, `astro_events` |
| Stale content detector | `astro_search` |
| Content refresher | `astro_search`, `astro_fetch` |
| Gap analysis agent | `astro_search` |
| Writer / Editor | None (no search needed) |

---

## 3. Repository Structure to Build

```
astro-search/
│
├── astro_search/                   # Main package
│   ├── __init__.py                 # Public API exports
│   ├── core.py                     # AstroSearch class — orchestrates everything
│   ├── intent.py                   # Query intent classifier
│   ├── ranker.py                   # Result scoring and ranking
│   ├── deduplicator.py             # Title similarity + URL dedup
│   ├── cache.py                    # 15-min TTL in-memory cache
│   ├── normalizer.py               # Enforces output schema contract
│   ├── tools.py                    # TOOL_DECLARATIONS + tool_handler for Gemini
│   └── sources/
│       ├── __init__.py
│       ├── base.py                 # BaseSource abstract class
│       ├── rss.py                  # All RSS feed fetching
│       ├── nasa.py                 # api.nasa.gov endpoints
│       ├── usno.py                 # USNO moon/eclipse APIs
│       ├── noaa.py                 # NOAA SWPC space weather
│       ├── jpl.py                  # JPL asteroid/ephemeris APIs
│       ├── arxiv.py                # arXiv astrophysics papers
│       ├── ads.py                  # NASA ADS (needs API key)
│       └── fetch.py                # astro_fetch — full article text retrieval
│
├── tools/
│   └── verify_feeds.py             # RSS health check script (already written)
│
├── tests/
│   ├── test_intent.py
│   ├── test_ranker.py
│   ├── test_deduplicator.py
│   └── test_normalizer.py
│
├── .github/
│   └── workflows/
│       ├── weekly_feed_check.yml   # Runs verify_feeds.py every Monday
│       └── test.yml                # Runs tests on push
│
├── requirements.txt
├── setup.py
└── README.md
```

---

## 4. The Output Contract (Most Important Thing)

Every single result — regardless of source — MUST return this exact schema. This is non-negotiable. It is what makes the tool agent-friendly.

```python
{
    # Required — always present
    "title":        str,           # Article/event title, plain text
    "summary":      str,           # Max 400 chars, plain text, no HTML
    "url":          str,           # Direct link to source
    "source":       str,           # Human name: "NASA", "EarthSky", "arXiv"
    "source_type":  str,           # "rss" | "api" | "computed" | "local"
    "authority":    int,           # 1=community, 2=established, 3=institutional
    "category":     str,           # "news"|"events"|"papers"|"space_weather"|"discoveries"
    "published":    str,           # ISO-8601 datetime string, or "" if unknown
    "freshness_h":  int | None,    # Hours since published. None if unknown.

    # Optional — present when available
    "entities":     list[str],     # Detected entities: ["lunar eclipse", "India", "2027"]
    "location":     str | None,    # If result is location-specific
    "event_type":   str | None,    # "solar_eclipse"|"meteor_shower"|"moon_phase" etc.
    "event_date":   str | None,    # ISO-8601 date for future events
    "authors":      list[str],     # For papers only
    "extra":        dict,          # Source-specific structured data (raw)
}
```

**The full search() return value:**
```python
{
    "query":    str,           # Original query string
    "intent":   str,           # Detected intent (see Layer 1)
    "category": str,           # Effective category searched
    "count":    int,           # Number of results returned
    "results":  list[dict],    # List of result dicts above
    "markdown": str,           # Pre-formatted markdown for agent consumption
    "cached":   bool,          # True if served from cache
}
```

---

## 5. Layer 1: Intent Classifier (`intent.py`)

This is the most important component. Without it, every query hits every source — slow, noisy, wrong.

**The 9 intents:**

```python
INTENTS = {
    "celestial_event_lookup":  "User wants dates/times of a specific event",
    "celestial_event_detail":  "User wants visibility/location info for an event",
    "current_phenomenon":      "User wants real-time data (aurora NOW, solar flare TODAY)",
    "recent_news":             "User wants latest news/discoveries",
    "concept_explanation":     "User wants to understand something (what is a pulsar)",
    "research_lookup":         "User wants academic papers",
    "object_lookup":           "User wants data about a specific object (star, galaxy)",
    "mission_status":          "User wants spacecraft/mission status",
    "periodic_event":          "User wants a recurring event calendar (all meteor showers)",
}
```

**Classifier rules (keyword + pattern matching, no ML):**

```python
INTENT_RULES = [
    # Order matters — first match wins
    ("current_phenomenon",      ["tonight", "right now", "current kp", "aurora now",
                                  "live", "forecast", "is there aurora", "solar wind"]),
    ("celestial_event_detail",  ["visible from", "can i see", "visibility", 
                                  "what time", "where to watch", "best place"]),
    ("celestial_event_lookup",  ["next", "upcoming", "when is", "when will",
                                  "date of", "eclipse", "meteor shower", "full moon",
                                  "new moon", "conjunction", "opposition", "transit",
                                  "solstice", "equinox", "supermoon", "alignment"]),
    ("research_lookup",         ["paper", "study", "research", "arxiv", "published",
                                  "journal", "findings", "peer reviewed", "abstract"]),
    ("object_lookup",           ["what is", "how far", "distance to", "size of",
                                  "mass of", "type of star", "magnitude"]),
    ("mission_status",          ["mission", "spacecraft", "probe", "rover", "satellite",
                                  "where is voyager", "iss position", "launch"]),
    ("periodic_event",          ["calendar", "all meteor showers", "this year events",
                                  "2025 celestial", "2026 celestial", "schedule"]),
    ("recent_news",             ["latest", "recent", "new discovery", "just announced",
                                  "breaking", "discovered", "found", "detected"]),
    ("concept_explanation",     ["what is", "explain", "how does", "why does",
                                  "difference between", "define", "meaning of"]),
]

DEFAULT_INTENT = "recent_news"
```

**Entity extraction (simple, no NLP library needed):**

```python
KNOWN_ENTITIES = {
    # Events
    "eclipses":      ["solar eclipse", "lunar eclipse", "total eclipse", "annular eclipse", "partial eclipse"],
    "moon_phases":   ["full moon", "new moon", "first quarter", "last quarter", "supermoon", "blood moon"],
    "meteor_showers":["perseids", "leonids", "geminids", "eta aquariids", "orionids", "lyrids",
                      "ursids", "draconids", "taurids", "quadrantids", "delta aquariids"],
    "planetary":     ["conjunction", "opposition", "transit", "occultation", "retrograde",
                      "greatest elongation", "planetary alignment"],
    "solar":         ["solar flare", "cme", "coronal mass ejection", "sunspot", "solar storm",
                      "geomagnetic storm", "aurora", "northern lights", "kp index"],
    # Objects
    "planets":       ["mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"],
    "deep_sky":      ["black hole", "neutron star", "pulsar", "nebula", "galaxy", "quasar",
                      "supernova", "white dwarf", "dark matter", "exoplanet"],
    # Missions
    "missions":      ["jwst", "james webb", "hubble", "artemis", "voyager", "cassini",
                      "perseverance", "curiosity", "new horizons", "iss"],
}
```

---

## 6. Layer 2: Source Profiles + Routing (`sources/base.py`)

Each source is a class inheriting from `BaseSource`. The router picks sources by matching intent + entities.

**BaseSource interface:**

```python
class BaseSource:
    name: str               # "EarthSky RSS"
    source_type: str        # "rss" | "api" | "computed"
    authority: int          # 1-3
    intents: list[str]      # Which intents this source serves
    entities: list[str]     # Which entity types it covers. ["*"] = all.
    supports_location: bool # Can it filter by lat/lon?
    timeout: int            # Seconds before giving up
    fallback: str | None    # Name of fallback source if this fails

    def fetch(self, query: str, **kwargs) -> list[dict]:
        """Returns list of normalized result dicts."""
        raise NotImplementedError

    def is_available(self) -> bool:
        """Quick health check. Default: True."""
        return True
```

**Source routing logic in `core.py`:**

```python
def _select_sources(self, intent: str, entities: list[str], 
                    location: str | None) -> list[BaseSource]:
    candidates = []
    for source in ALL_SOURCES:
        if intent not in source.intents:
            continue
        if source.entities != ["*"] and not any(e in source.entities for e in entities):
            continue
        if location and not source.supports_location:
            # Still include, but deprioritize
            pass
        candidates.append(source)
    
    # Cap at 5 sources max per query
    # Prioritize: authority DESC, then specificity to query
    return sorted(candidates, key=lambda s: s.authority, reverse=True)[:5]
```

---

## 7. Source Implementations

### 7A. RSS Sources (`sources/rss.py`)

**Confirmed working feeds (from live verification Sept 2026):**

```python
RSS_FEEDS = [
    # TIER 1 — Institutional, highest authority
    {
        "name": "NASA News",
        "url": "https://www.nasa.gov/news-releases/feed/",
        "authority": 3,
        "intents": ["recent_news", "mission_status", "celestial_event_lookup"],
        "entities": ["*"],
        "category": "news",
    },
    {
        "name": "NASA Science",
        "url": "https://science.nasa.gov/feed/",
        "authority": 3,
        "intents": ["recent_news", "research_lookup"],
        "entities": ["*"],
        "category": "discoveries",
    },
    {
        "name": "ESA News",
        "url": "https://www.esa.int/rssfeed/Our_Activities/Space_Science",
        "authority": 3,
        "intents": ["recent_news", "mission_status"],
        "entities": ["*"],
        "category": "news",
    },
    {
        "name": "NRAO",
        "url": "https://public.nrao.edu/news/feed/",
        "authority": 3,
        "intents": ["recent_news", "research_lookup"],
        "entities": ["deep_sky"],
        "category": "discoveries",
    },
    {
        "name": "JWST",
        "url": "https://webbtelescope.org/news/webb-news/rss.xml",
        "authority": 3,
        "intents": ["recent_news", "object_lookup"],
        "entities": ["missions", "deep_sky"],
        "category": "discoveries",
    },
    {
        "name": "Hubble",
        "url": "https://hubblesite.org/api/v3/news_releases/all?format=rss",
        "authority": 3,
        "intents": ["recent_news", "object_lookup"],
        "entities": ["missions", "deep_sky"],
        "category": "discoveries",
    },
    {
        "name": "ESO",
        "url": "https://www.eso.org/public/news/feed.rss",
        "authority": 3,
        "intents": ["recent_news", "research_lookup"],
        "entities": ["deep_sky"],
        "category": "discoveries",
    },
    {
        "name": "Chandra X-ray",
        "url": "https://chandra.harvard.edu/rss/news.rss",
        "authority": 3,
        "intents": ["recent_news"],
        "entities": ["deep_sky", "solar"],
        "category": "discoveries",
    },

    # TIER 2 — Established publications
    {
        "name": "EarthSky",
        "url": "https://earthsky.org/feed/",
        "authority": 2,
        "intents": ["recent_news", "celestial_event_lookup", "celestial_event_detail",
                    "current_phenomenon", "concept_explanation"],
        "entities": ["*"],
        "category": "news",
    },
    {
        "name": "Universe Today",
        "url": "https://www.universetoday.com/feed/",
        "authority": 2,
        "intents": ["recent_news", "research_lookup", "concept_explanation"],
        "entities": ["*"],
        "category": "news",
    },
    {
        "name": "Sky & Telescope",
        "url": "https://skyandtelescope.org/astronomy-news/feed/",
        "authority": 2,
        "intents": ["recent_news", "celestial_event_lookup", "periodic_event"],
        "entities": ["*"],
        "category": "news",
    },
    {
        "name": "Astronomy Magazine",
        "url": "https://astronomy.com/feed",
        "authority": 2,
        "intents": ["recent_news", "celestial_event_lookup", "concept_explanation"],
        "entities": ["*"],
        "category": "news",
    },
    {
        "name": "AAS Nova",
        "url": "https://aasnova.org/feed/",
        "authority": 2,
        "intents": ["research_lookup", "recent_news"],
        "entities": ["*"],
        "category": "papers",
    },
    {
        "name": "Space.com",
        "url": "https://www.space.com/feeds/all",
        "authority": 2,
        "intents": ["recent_news", "mission_status"],
        "entities": ["*"],
        "category": "news",
    },
    {
        "name": "Spaceflight Now",
        "url": "https://spaceflightnow.com/feed/",
        "authority": 2,
        "intents": ["mission_status", "recent_news"],
        "entities": ["missions"],
        "category": "news",
    },
    {
        "name": "The Planetary Society",
        "url": "https://www.planetary.org/articles?rss=1",
        "authority": 2,
        "intents": ["recent_news", "mission_status"],
        "entities": ["*"],
        "category": "news",
    },
    {
        "name": "In-The-Sky.org",
        "url": "https://in-the-sky.org/rss.php?feed=dfan",
        "authority": 2,
        "intents": ["celestial_event_lookup", "periodic_event"],
        "entities": ["planetary", "moon_phases", "eclipses"],
        "category": "events",
    },
    {
        "name": "American Meteor Society",
        "url": "https://www.amsmeteors.org/feed/",
        "authority": 2,
        "intents": ["celestial_event_lookup", "periodic_event", "current_phenomenon"],
        "entities": ["meteor_showers"],
        "category": "events",
    },
    {
        "name": "Spaceweather.com",
        "url": "https://spaceweather.com/wordpress/?feed=rss2",
        "authority": 2,
        "intents": ["current_phenomenon", "celestial_event_lookup"],
        "entities": ["solar"],
        "category": "space_weather",
    },
    {
        "name": "SpaceNews",
        "url": "https://spacenews.com/feed/",
        "authority": 2,
        "intents": ["recent_news", "mission_status"],
        "entities": ["missions"],
        "category": "news",
    },
    {
        "name": "Centauri Dreams",
        "url": "https://www.centauri-dreams.org/feed/",
        "authority": 2,
        "intents": ["research_lookup", "concept_explanation"],
        "entities": ["deep_sky"],
        "category": "papers",
    },
    {
        "name": "Science News Space",
        "url": "https://www.sciencenews.org/topic/astronomy/feed",
        "authority": 2,
        "intents": ["recent_news", "research_lookup"],
        "entities": ["*"],
        "category": "news",
    },

    # TIER 3 — Community/supplemental
    {
        "name": "Keck Observatory",
        "url": "https://www.keckobservatory.org/feed/",
        "authority": 1,
        "intents": ["recent_news", "research_lookup"],
        "entities": ["deep_sky"],
        "category": "discoveries",
    },
    {
        "name": "SpaceDaily",
        "url": "https://www.spacedaily.com/spacedaily.xml",
        "authority": 1,
        "intents": ["recent_news"],
        "entities": ["*"],
        "category": "news",
    },
    {
        "name": "The Space Review",
        "url": "https://www.thespacereview.com/articles.xml",
        "authority": 1,
        "intents": ["recent_news", "mission_status"],
        "entities": ["missions"],
        "category": "news",
    },
]
```

**RSS fetch implementation notes:**
- Use `feedparser` library
- Always set a real browser User-Agent header (see below)
- Timeout: 12 seconds per feed
- Never let one feed block others — use threading or asyncio
- Validate: entry count > 0 after parse
- Strip HTML from summaries: use `html.unescape` + regex `<[^>]+>` → `""`
- Truncate summaries to 400 chars at word boundary

**Correct User-Agent:**
```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}
```

### 7B. NASA APIs (`sources/nasa.py`)

**Base:** `https://api.nasa.gov/`  
**Key handling:** Check env var `ASTRO_NASA_KEY`, fall back to `DEMO_KEY`  
**DEMO_KEY limits:** 30 req/hr, 50/day (sufficient for most use)  
**Registered key limits:** 1,000 req/hr

```python
import os
NASA_KEY = os.environ.get("ASTRO_NASA_KEY", "DEMO_KEY")
```

**Endpoints to implement:**

| Method | Endpoint | Intent | Notes |
|--------|----------|--------|-------|
| `get_apod(date=None, count=None)` | `/planetary/apod` | `recent_news` | Daily astronomy image |
| `get_asteroids(days=7)` | `/neo/rest/v1/feed` | `celestial_event_lookup` | Near-Earth objects |
| `get_solar_flares(days=7)` | `/DONKI/FLR` | `current_phenomenon` | X/M/C class flares |
| `get_cme(days=7)` | `/DONKI/CME` | `current_phenomenon` | Coronal mass ejections |
| `get_geomagnetic_storms(days=7)` | `/DONKI/GST` | `current_phenomenon` | Storm events |
| `get_donki_alerts()` | `/DONKI/notifications?type=all` | `current_phenomenon` | Active alerts |
| `search_images(query)` | `https://images-api.nasa.gov/search` | `object_lookup` | No key needed |

### 7C. USNO APIs (`sources/usno.py`)

**Base:** `https://aa.usno.navy.mil/api/`  
**Key:** None required. Completely free.  
**Authority:** 3 (US government, most authoritative for moon/eclipse data)

```python
# Endpoints to implement:

def get_moon_phases(year: int) -> list[dict]:
    # GET /moon/phases/year?year=YYYY
    # Returns: all full/new/quarter moons for the year

def get_moon_phases_from_date(date: str, count: int = 4) -> list[dict]:
    # GET /moon/phases/date?date=YYYY-MM-DD&nump=N
    # Returns: next N phases from a given date

def get_solar_eclipses(year: int) -> list[dict]:
    # GET /eclipses/solar/year?year=YYYY
    # Returns: all solar eclipses for the year

def get_lunar_eclipses(year: int) -> list[dict]:
    # GET /eclipses/lunar/year?year=YYYY
    # Returns: all lunar eclipses for the year

def get_seasons(year: int) -> list[dict]:
    # GET /seasons?year=YYYY
    # Returns: equinoxes and solstices

def get_rise_set(date: str, lat: float, lon: float, tz: int = 0) -> dict:
    # GET /rstt/oneday?date=YYYY-MM-DD&coords=LAT,LON&tz=N
    # Returns: sunrise, sunset, moonrise, moonset, transit times
```

### 7D. NOAA SWPC (`sources/noaa.py`)

**Base:** `https://services.swpc.noaa.gov/`  
**Key:** None. Public domain. All endpoints return JSON.  
**Use for:** Aurora, solar flares, geomagnetic storms, space weather

```python
NOAA_ENDPOINTS = {
    "kp_forecast":    "/json/kp_index.json",
    "kp_1min":        "/json/planetary_k_index_1m.json",
    "solar_wind":     "/json/solar-wind/plasma-7-day.json",
    "imf":            "/json/solar-wind/mag-7-day.json",
    "alerts":         "/products/alerts.json",
    "xray_flux":      "/json/goes/secondary/xrays-7-day.json",
    "aurora_north":   "/json/ovation_aurora_latest.json",
    "3day_forecast":  "/text/3-day-forecast.txt",
    "27day_outlook":  "/text/27-day-outlook.txt",
}

# Key fields to extract:
# Kp index: 0-9 scale. >5 = storm. >7 = strong storm (aurora likely at lower latitudes)
# IMF Bz: negative = aurora-favorable
# Aurora probability: percentage from OVATION model
```

**Aurora alert logic:**
```python
def get_aurora_alert(kp: float, bz: float) -> str:
    """Convert Kp + Bz into human-readable aurora alert."""
    if kp >= 7:
        return "Strong aurora likely. Visible at mid-latitudes."
    elif kp >= 5:
        return "Moderate aurora activity. Visible at high latitudes."
    elif kp >= 3 and bz < -5:
        return "Minor aurora possible at high latitudes."
    else:
        return "Quiet conditions. Aurora unlikely except at polar regions."
```

### 7E. JPL APIs (`sources/jpl.py`)

**Base:** `https://ssd-api.jpl.nasa.gov/`  
**Key:** None required.

```python
def get_close_approaches(days: int = 30, dist_max: float = 0.05) -> list[dict]:
    # GET /cad.api?dist-max=0.05&date-min=TODAY&date-max=TODAY+days
    # dist_max in AU. 0.05 AU ≈ 7.5M km (well inside Mars orbit)

def get_asteroid(name: str) -> dict:
    # GET /sbdb.api?sstr=NAME
    # Lookup by name: "Apophis", "Ceres", "2024 YR4"

def get_fireballs(limit: int = 10) -> list[dict]:
    # GET /fireball.api?limit=10
    # Recently detected bolide/fireball events

def get_planetary_position(body: str, date: str, lat: float, lon: float) -> dict:
    # GET https://ssd.jpl.nasa.gov/api/horizons.api
    # body: "499"=Mars, "599"=Jupiter, "10"=Sun, "301"=Moon
    # Returns RA, Dec, Az, El, distance, rise/set times
```

### 7F. arXiv (`sources/arxiv.py`)

**Base:** `https://export.arxiv.org/api/query`  
**Key:** None. Free. Returns Atom XML.  
**Rate limit:** Be polite — add 3-second delay between requests.

```python
ARXIV_CATS = {
    "all_astrophysics": "astro-ph",
    "cosmology":        "astro-ph.CO",
    "galaxies":         "astro-ph.GA",
    "high_energy":      "astro-ph.HE",
    "instrumentation":  "astro-ph.IM",
    "solar_stellar":    "astro-ph.SR",
    "planets":          "astro-ph.EP",
}

def search_papers(query: str, category: str = "astro-ph",
                  max_results: int = 5, days_back: int = 30) -> list[dict]:
    # Returns: title, authors (max 3), abstract (truncated 400 chars),
    #          arxiv_url, published_date, categories
```

### 7G. NASA ADS (`sources/ads.py`)

**Base:** `https://api.adsabs.harvard.edu/v1/`  
**Key:** Required. Free. Sign up at ui.adsabs.harvard.edu.  
**Env var:** `ASTRO_ADS_KEY`  
**Limits:** 5,000 requests/day (very generous)

```python
def search_papers(query: str, year_range: tuple = None,
                  max_results: int = 5) -> list[dict]:
    # Returns: title, authors, abstract, journal, year,
    #          citation_count, doi, ads_url
    # Much more comprehensive than arXiv — includes published papers,
    # not just preprints. Citation counts are a quality signal.
    # Only activate if ASTRO_ADS_KEY env var is set.
```

### 7H. Full Article Fetch (`sources/fetch.py`)

**This is the `astro_fetch` tool.** Agents call this after `astro_search` when they need the full article text.

```python
def fetch_article(url: str) -> dict:
    """
    Fetch full article text from a URL.
    
    Returns:
    {
        "url": str,
        "title": str,
        "text": str,          # Cleaned plain text, no HTML
        "word_count": int,
        "fetch_ok": bool,
        "error": str | None,
    }
    """
    # Implementation:
    # 1. requests.get(url, headers=HEADERS, timeout=15)
    # 2. If content-type is not text/html → return error
    # 3. Strip nav, header, footer, ads using basic heuristics
    # 4. Extract main content: look for <article>, <main>, 
    #    largest <div> by text volume
    # 5. html.unescape + strip tags
    # 6. Collapse whitespace
    # 7. Truncate to 6000 words (agent context limit)
```

---

## 8. Layer 3: Result Assembly

### Cache (`cache.py`)

```python
class TTLCache:
    """
    Simple in-process cache. 15-min TTL. 
    Key = (query, category, max_results). Value = search result dict.
    Not persistent across runs — that's fine for GitHub Actions.
    """
    def __init__(self, ttl_minutes: int = 15):
        self._store: dict = {}  # key → (timestamp, value)
        self.ttl = ttl_minutes * 60

    def get(self, key: tuple) -> dict | None: ...
    def set(self, key: tuple, value: dict) -> None: ...
    def clear(self) -> None: ...
```

### Deduplicator (`deduplicator.py`)

```python
def deduplicate(results: list[dict]) -> list[dict]:
    """
    Three-pass dedup:
    Pass 1: Exact URL match → keep first occurrence
    Pass 2: Title token overlap > 0.7 → keep higher-authority result
    Pass 3: Same event/date from multiple sources → keep best, 
            add "also covered by" to extra field
    """
```

**Title similarity (no external libraries):**
```python
def title_similarity(a: str, b: str) -> float:
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    # Remove stopwords
    stopwords = {"a","an","the","in","on","at","of","to","and","or","is","are","was"}
    tokens_a -= stopwords
    tokens_b -= stopwords
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / max(len(tokens_a), len(tokens_b))
    # Threshold for dedup: > 0.65
```

### Ranker (`ranker.py`)

```python
def rank(results: list[dict], query_tokens: list[str], intent: str) -> list[dict]:
    """
    Score formula:
    
    score = (
        intent_source_match  * 0.35  +  # was this source designed for this intent?
        entity_overlap       * 0.30  +  # query tokens in title+summary
        authority            * 0.20  +  # 1/2/3 normalized to 0-1
        freshness            * 0.15     # exponential decay: 1.0 at 0h, 0.5 at 24h, 0.1 at 7d
    )
    
    freshness_score = max(0, 1 - (hours_old / 168))  # 168h = 7 days
    entity_score = hits / len(query_tokens) if query_tokens else 0
    authority_score = (authority - 1) / 2  # normalize 1-3 to 0-1
    intent_match_score = 1.0 if intent in source.intents else 0.3
    """
```

### Normalizer (`normalizer.py`)

```python
def normalize(raw: dict, source_meta: dict) -> dict:
    """
    Takes raw data from any source.
    Returns a result dict matching the output contract exactly.
    Strips HTML from summary.
    Truncates summary to 400 chars at word boundary.
    Converts any date format to ISO-8601.
    Calculates freshness_h.
    Always returns all required fields (never KeyError on the agent side).
    """
```

---

## 9. Edge Case Handling

Implement these explicitly. Do not leave them to chance.

### Query edge cases

```python
# Empty/whitespace query → default to today's events
if not query.strip():
    return self.get_celestial_events()

# Past year in query → label results as historical
import re
past_years = re.findall(r'\b(20[0-2][0-9])\b', query)
if past_years and all(int(y) < datetime.now().year for y in past_years):
    # Search but label results: is_historical = True

# Multi-intent query → split and merge
# "eclipses and meteor showers" → two sub-queries, merged + deduplicated

# Misspelled entities → fuzzy match
# "persieds" → "perseids" (simple edit distance check against KNOWN_ENTITIES)

# No results → graceful empty (never raise, never crash)
if not results:
    return {
        "query": query, "intent": intent, "count": 0,
        "results": [], 
        "markdown": f"No results found for '{query}'. Try: 'latest astronomy news' or 'upcoming celestial events'.",
        "cached": False,
    }
```

### Source failure edge cases

```python
# Every source fetch MUST be wrapped:
def _safe_fetch(self, source: BaseSource, query: str, **kwargs) -> list[dict]:
    try:
        results = source.fetch(query, **kwargs)
        if not results:
            return self._try_fallback(source, query, **kwargs)
        return results
    except requests.Timeout:
        logger.warning(f"{source.name}: timeout after {source.timeout}s")
        return self._try_fallback(source, query, **kwargs)
    except Exception as e:
        logger.warning(f"{source.name}: {e}")
        return self._try_fallback(source, query, **kwargs)

# Fallback chains:
FALLBACK_CHAINS = {
    "USNO": "ephem_local",         # USNO down → compute locally with ephem
    "NASA APOD": "nasa_science_rss",
    "EarthSky": "universe_today",
    "JPL CAD": "nasa_neows",
    "NOAA SWPC": "spaceweather_rss",
    "arXiv": "aas_nova_rss",
}
```

### Content quality filters

```python
# Filter stale pinned posts (> 90 days old, unless historical query)
def _is_fresh_enough(result: dict, query_is_historical: bool) -> bool:
    if query_is_historical:
        return True
    if not result.get("freshness_h"):
        return True  # unknown age → keep
    return result["freshness_h"] < 90 * 24  # 90 days

# Strip boilerplate summary patterns
BOILERPLATE_PATTERNS = [
    r"subscribe to.*newsletter",
    r"sign up for.*free",
    r"click here to read more",
    r"this article first appeared",
    r"©\s*\d{4}",
    r"all rights reserved",
]

# Mark paywalled sources
PAYWALLED_SOURCES = ["New Scientist"]  # partial paywall — flag, don't remove

# Strip non-astronomy content slipping through broad feeds
ASTRONOMY_RELEVANCE_THRESHOLD = 0.1  # minimum entity overlap to include result
```

---

## 10. The Tools Interface (`tools.py`)

This is the **only file your agent repos need to import**.

```python
# Three tool declarations for Gemini function calling
TOOL_DECLARATIONS = [
    {
        "name": "astro_search",
        "description": (
            "Search for astronomy, astrophysics, and space science information. "
            "Covers: latest news, new discoveries, upcoming and historical celestial events "
            "(lunar/solar eclipses, meteor showers, full/new moon, planetary alignments, "
            "conjunctions, oppositions, transits, occultations, equinoxes, solstices, "
            "comets, auroras, geomagnetic storms, solar flares), space mission updates, "
            "and astrophysics research papers. "
            "Use this whenever you need current astronomy information."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query. Examples: 'next lunar eclipse', "
                                   "'Perseid meteor shower 2026 peak date', "
                                   "'latest James Webb discoveries', 'aurora forecast tonight', "
                                   "'Kp index right now'"
                },
                "category": {
                    "type": "string",
                    "enum": ["news", "discoveries", "events", "papers", "space_weather", "all"],
                    "description": "Category to search. Use 'events' for celestial events, "
                                   "'space_weather' for aurora/solar/geomagnetic, "
                                   "'papers' for research, 'all' to auto-detect."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return. Default: 8. Max: 20."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "astro_fetch",
        "description": (
            "Fetch the full text of an astronomy article or page from a URL. "
            "Use after astro_search when you need the complete content of a result, "
            "not just the summary. Returns cleaned plain text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch. Should come from astro_search results."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "astro_events",
        "description": (
            "Get a complete list of celestial events for a given year. "
            "Includes all moon phases, solar and lunar eclipses, meteor shower peaks, "
            "equinoxes, solstices, and major planetary events."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "Year to get events for. Defaults to current year."
                }
            },
            "required": []
        }
    },
    {
        "name": "astro_papers",
        "description": (
            "Search astrophysics research papers from arXiv and NASA ADS. "
            "Use for finding peer-reviewed research, recent preprints, "
            "or specific academic findings on an astronomy topic."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "topic": {
                    "type": "string",
                    "enum": ["astrophysics", "cosmology", "galaxies", "high_energy",
                             "solar", "planets", "instrumentation"],
                    "description": "arXiv sub-category to search within."
                },
                "max_results": {"type": "integer"}
            },
            "required": ["query"]
        }
    }
]


def tool_handler(tool_name: str, tool_args: dict) -> str:
    """
    Universal handler. Call this in your agent's tool execution loop.
    Returns JSON string with 'json' (structured) and 'markdown' (readable) keys.
    
    Usage:
        result_str = tool_handler(fc.name, dict(fc.args))
        # Pass result_str back to model as function response
    """
    engine = AstroSearch()
    
    if tool_name == "astro_search":
        output = engine.search(
            query=tool_args.get("query", ""),
            category=tool_args.get("category", "all"),
            max_results=min(tool_args.get("max_results", 8), 20),
        )
    elif tool_name == "astro_fetch":
        output = fetch_article(tool_args.get("url", ""))
    elif tool_name == "astro_events":
        output = engine.get_celestial_events(year=tool_args.get("year"))
    elif tool_name == "astro_papers":
        output = engine.search(
            query=tool_args.get("query", ""),
            category="papers",
            max_results=tool_args.get("max_results", 5),
        )
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    return json.dumps({"json": output, "markdown": output.get("markdown", "")},
                      ensure_ascii=False, indent=2)
```

---

## 11. Public API (`__init__.py`)

```python
from .core import AstroSearch
from .tools import TOOL_DECLARATIONS, tool_handler
from .sources.fetch import fetch_article

__all__ = ["AstroSearch", "TOOL_DECLARATIONS", "tool_handler", "fetch_article"]
__version__ = "2.0.0"
```

**What agents import:**
```python
from astro_search import TOOL_DECLARATIONS, tool_handler
# That's it. Nothing else needed.
```

---

## 12. `setup.py`

```python
from setuptools import setup, find_packages

setup(
    name="astro-search",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "feedparser>=6.0",
        "requests>=2.28",
        "python-dateutil>=2.8",
    ],
    extras_require={
        "local": ["ephem>=4.1", "astropy>=5.0"],  # optional local computation
    },
    python_requires=">=3.9",
)
```

---

## 13. `requirements.txt`

```
feedparser>=6.0
requests>=2.28
python-dateutil>=2.8

# Optional — for local celestial event computation (fallback)
# ephem>=4.1
# astropy>=5.0
```

---

## 14. Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ASTRO_NASA_KEY` | No | `DEMO_KEY` | NASA API (30→1000 req/hr) |
| `ASTRO_ADS_KEY` | No | None | NASA ADS papers search. Get free at ui.adsabs.harvard.edu |

**Aman has a NASA ADS API key.** Store it as `ASTRO_ADS_KEY` in GitHub Actions secrets. The `ads.py` source activates only when this is set.

---

## 15. GitHub Actions Workflows

### `.github/workflows/weekly_feed_check.yml`

```yaml
name: Weekly Feed Health Check

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday 9 AM UTC
  workflow_dispatch:

jobs:
  verify-feeds:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install feedparser requests
      - name: Run feed verification
        run: python tools/verify_feeds.py > feed_report.txt 2>&1
      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: feed-health-report
          path: feed_report.txt
          retention-days: 30
```

### `.github/workflows/test.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e . pytest
      - run: pytest tests/ -v
```

---

## 16. Integration in Agent Repo

**In `requirements.txt` of stellarillusion-agents:**
```
git+https://github.com/AMAN_USERNAME/astro-search.git@main
```

**In any agent script that needs search:**
```python
import json
import google.generativeai as genai
from astro_search import TOOL_DECLARATIONS, tool_handler

def build_gemini_tools():
    from google.generativeai.types import FunctionDeclaration, Tool
    declarations = [
        FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=t["parameters"],
        )
        for t in TOOL_DECLARATIONS
    ]
    return [Tool(function_declarations=declarations)]

def run_agent_with_search(user_query: str, system_prompt: str) -> str:
    model = genai.GenerativeModel(
        model_name="gemini-3.7-flash",
        tools=build_gemini_tools(),
        system_instruction=system_prompt,
    )
    chat = model.start_chat()
    response = chat.send_message(user_query)
    
    # Agentic tool-call loop
    for _ in range(10):  # max 10 tool calls per query
        tool_calls = [
            p for p in response.candidates[0].content.parts
            if hasattr(p, "function_call") and p.function_call.name
        ]
        if not tool_calls:
            break  # model gave final text response
        
        tool_responses = []
        for part in tool_calls:
            fc = part.function_call
            result = tool_handler(fc.name, dict(fc.args))
            tool_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )
        response = chat.send_message(tool_responses)
    
    return response.text
```

**For agents that DON'T need search (writer, editor):**
```python
# Just don't pass tools= parameter. Done.
model = genai.GenerativeModel(
    model_name="gemini-3.7-flash",
    system_instruction=system_prompt,
    # No tools= here
)
```

---

## 17. Build Order

Build in this exact sequence. Each step is testable before moving to the next.

```
Step 1: Repo scaffold
  - Create directory structure
  - setup.py, requirements.txt, __init__.py stubs
  - Confirm: pip install -e . works

Step 2: Output contract + Normalizer
  - normalizer.py with the schema
  - Unit tests for normalize()
  - Confirm: all edge cases (missing fields, bad dates, HTML in summary)

Step 3: Intent classifier
  - intent.py
  - Unit tests: 20+ queries → expected intent
  - Confirm: 95%+ accuracy on test cases

Step 4: BaseSource + RSS source
  - base.py abstract class
  - rss.py with first 5 feeds (EarthSky, Universe Today, NASA, ESA, JWST)
  - Integration test: fetch real results, confirm schema
  - Confirm: works with real feeds

Step 5: USNO + NOAA sources
  - usno.py: moon phases + eclipse endpoints
  - noaa.py: Kp index + aurora + alerts
  - Integration tests
  - Confirm: celestial event queries return structured data

Step 6: JPL + NASA API sources
  - jpl.py: close approaches + fireballs
  - nasa.py: APOD + NeoWs + DONKI
  - Integration tests

Step 7: arXiv + ADS sources
  - arxiv.py
  - ads.py (gated on ASTRO_ADS_KEY env var)
  - Integration tests

Step 8: Core orchestrator
  - core.py: AstroSearch class
  - Source routing logic
  - Async fetching (threading.ThreadPoolExecutor, max_workers=5)
  - Fallback chains

Step 9: Deduplicator + Ranker
  - deduplicator.py
  - ranker.py
  - Unit tests with known duplicate sets

Step 10: Cache layer
  - cache.py TTLCache
  - Integrate into core.py

Step 11: astro_fetch
  - sources/fetch.py
  - Test on 5 known astronomy article URLs

Step 12: Tools interface
  - tools.py: TOOL_DECLARATIONS + tool_handler
  - End-to-end test: simulate Gemini tool call → verify response shape

Step 13: GitHub Actions workflows
  - weekly_feed_check.yml
  - test.yml

Step 14: README
  - Installation, usage, tool declarations, env vars, examples
```

---

## 18. Non-Goals (Do NOT build these)

- No web UI
- No database or persistent storage
- No FastAPI/Flask server (not yet — that's v3)
- No crawler or web scraping of arbitrary pages
- No general-purpose search (only astronomy domain)
- No authentication layer
- No rate limiting server (let individual sources handle their own limits)
- No Docker container

---

## 19. Definition of Done

The build is complete when:

1. `pip install git+https://github.com/USER/astro-search.git@main` works
2. `from astro_search import TOOL_DECLARATIONS, tool_handler` works
3. `tool_handler("astro_search", {"query": "next lunar eclipse"})` returns valid JSON with at least 3 results
4. `tool_handler("astro_search", {"query": "aurora forecast tonight"})` returns NOAA data
5. `tool_handler("astro_events", {"year": 2026})` returns moon phases + eclipses
6. `tool_handler("astro_fetch", {"url": "https://earthsky.org/..."})` returns article text
7. All pytest tests pass
8. Weekly feed check workflow runs without error
9. A Gemini agent can call all 4 tools in a real conversation and get useful results

---

*End of handoff document. The building agent should start at Step 1 of Section 17 and work sequentially.*
