# AstroSearch v2.1 — free astronomy search engine (Python library)

![Source Status](https://img.shields.io/badge/Source_Availability-Operational-brightgreen?style=flat-square)
[![Tests](https://img.shields.io/badge/Tests-568%20Passing-success?style=flat-square)](https://github.com/amanmathur27/astro-search)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-purple?style=flat-square)](LICENSE)

AstroSearch is a ultra-precise, zero-noise, lightweight domain search and grounding engine for AI agents (Gemini 3.6/3.7/3.8, Claude, OpenAI). It aggregates 100% free astronomy sources (NASA, NOAA SWPC, arXiv, JPL, ESA, EarthSky, PhysOrg, Space.com, etc.) with deterministic ephemeris and strict entity guardrails.

`from astro_search import TOOL_DECLARATIONS, tool_handler, AstroSearch` — that's the integration.

---

## Key Features

- **Zero-Noise Precision Guardrails:** Anti-polysemy context filters eliminate domain collisions (e.g. Eclipse IDE vs Solar Eclipse, Kubernetes Cluster vs Star Cluster). Strict catalog/entity anchoring (Kepler, TRAPPIST, Messier, NGC) prevents off-target ranking.
- **AI Agent Grounding Modes (`mode="evidence"`):** Returns structured claim verification packages, source authority ratings, direct quotes, and citations ready for direct LLM grounding.
- **Delta & Refresh Updates (`since_date="YYYY-MM-DD"`):** Query recent discoveries, solar flares, and transient events filtered strictly after a reference date.
- **Physical Object Comparison Matrix (`astro_compare`):** Deterministic physical parameter comparisons (radius, mass, temperature, atmosphere, gravity) across solar system planets, moons, and stars.
- **Resilient & Ultra-Lightweight:** Conditional HTTP 304 caching (`ETag`/`If-Modified-Since`) and in-memory circuit breakers with exponential backoff. Zero heavy ML/GPU dependencies (pure Python).

---

## Install

```bash
pip install git+https://github.com/amanmathur27/astro-search.git@main
pip install -e ".[local]"  # optional offline moon appearance; cached Skyfield only
```

---

## Use

### 1. Universal Function Calling / Tool Handler
Pass tool declarations directly to Gemini, OpenAI, or Anthropic tool schemas:

```python
from astro_search import TOOL_DECLARATIONS, tool_handler

# Standard astronomy search
res = tool_handler("astro_search", {"query": "next lunar eclipse", "max_results": 8})

# Evidence grounding mode for AI agents
evidence = tool_handler("astro_search", {"query": "JWST exoplanet atmosphere detection", "mode": "evidence"})

# Physical body comparison matrix
comparison = tool_handler("astro_compare", {"objects": ["Europa", "Titan"]})

# Delta search for recent space weather
deltas = tool_handler("astro_search", {"query": "solar flare CME", "since_date": "2026-03-01"})

# Precomputed celestial calendar events
calendar = tool_handler("astro_events", {"year": 2026})

# Full article clean text extraction
article = tool_handler("astro_fetch", {"url": "https://earthsky.org/..."})
```

### 2. Direct Python API
```python
from astro_search import AstroSearch

engine = AstroSearch()

# Standard search
results = engine.search("Perseids 2026 peak date")

# Grounding evidence package
pkg = engine.search_as_evidence_package("TRAPPIST-1e water vapor")

# Delta search
delta = engine.search_deltas("sunspot AR3664 flare", since_date="2026-01-01")

# Physical comparison
matrix = engine.compare_objects(["Mars", "Jupiter", "Europa"])
```

---

## Tool Declarations

The library provides 5 tool declarations via `TOOL_DECLARATIONS`:

| Tool | Purpose | Key Parameters |
| :--- | :--- | :--- |
| `astro_search` | Real-time astronomy search & grounding | `query`, `category`, `mode` (`"standard"\|"evidence"`), `since_date`, `max_results` |
| `astro_compare` | Physical characteristic comparison matrix | `objects` (e.g. `["Europa", "Titan"]`) |
| `astro_events` | Annual celestial calendar & moon phases | `year`, `lat`, `lon`, `timezone` |
| `astro_fetch` | Cleaned full-text extraction from URLs | `url` |
| `astro_papers` | Academic paper search (arXiv + ADS) | `query`, `topic`, `max_results` |

---

## Environment Variables

- `ASTRO_NASA_KEY` — NASA API Key (defaults to `DEMO_KEY`, 30 req/hr)
- `ASTRO_ADS_KEY` — NASA ADS Key (if unset, queries arXiv API)
- `ASTRO_CACHE_PATH` — SQLite cache database path (defaults to `~/.astro_cache.db`)

---

## Automated Maintenance & CI

1. **Daily Source Availability Check (`daily_feed_check.yml`):** Runs daily at 06:00 UTC to verify HTTP responses, entry counts, and freshness across all connected RSS feeds and REST APIs.
2. **Weekly Calendar Spot-Check (`build_calendar.yml`):** Rebuilds current + next year precomputed events every Sunday.
3. **Meteor Shower Annual Update:** Open the IMO shower calendar once a year and update `astro_search/data/meteor_showers_{year}.json`.

---



## Live Source Availability & Health

<!-- START_SOURCE_HEALTH_TABLE -->
**Last Automated Check:** `2026-09-21 12:02 UTC` | **Overall Health:** 🟢 **Operational** (30/31 sources healthy, `96.8%`)

| Source | Type | Status | HTTP | Details | Freshness |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **The Astronomer's Telegram** | `RSS` | 🟢 OK | `200` | 10 entries | 0h ago |
| **NASA News** | `RSS` | 🟢 OK | `200` | 10 entries | 0h ago |
| **NASA Science** | `RSS` | 🟢 OK | `200` | 10 entries | 7h ago |
| **JPL News** | `RSS` | 🟢 OK | `200` | 100 entries | 116h ago |
| **NASA Artemis** | `RSS` | 🟢 OK | `200` | 10 entries | 594h ago |
| **NASA Space Station** | `RSS` | 🟢 OK | `200` | 10 entries | 46h ago |
| **ESA News** | `RSS` | 🟢 OK | `200` | 15 entries | 76h ago |
| **ESO** | `RSS` | 🟢 OK | `200` | 10 entries | 789h ago |
| **NRAO** | `RSS` | 🟢 OK | `200` | 10 entries | 987h ago |
| **Royal Astronomical Society** | `RSS` | 🟢 OK | `200` | 10 entries | 480h ago |
| **Phys.org** | `RSS` | 🟢 OK | `200` | 30 entries | 17h ago |
| **Universe Today** | `RSS` | 🟢 OK | `200` | 20 entries | 1h ago |
| **EarthSky** | `RSS` | 🟢 OK | `200` | 10 entries | 2h ago |
| **Astronomy Magazine** | `RSS` | 🟢 OK | `200` | 10 entries | 4h ago |
| **ScienceDaily Astronomy** | `RSS` | 🟢 OK | `200` | 60 entries | 25h ago |
| **ScienceDaily Astrophysics** | `RSS` | 🟢 OK | `200` | 60 entries | 25h ago |
| **ScienceDaily Space** | `RSS` | 🟢 OK | `200` | 60 entries | 25h ago |
| **New Scientist Space** | `RSS` | 🔴 Fail | `-` | 0 entries | - |
| **AAS Nova** | `RSS` | 🟢 OK | `200` | 600 entries | 66h ago |
| **arXiv astro-ph Recent** | `RSS` | 🟢 OK | `200` | 155 entries | 8h ago |
| **SpaceNews** | `RSS` | 🟢 OK | `200` | 10 entries | 69h ago |
| **Centauri Dreams** | `RSS` | 🟢 OK | `200` | 10 entries | 115h ago |
| **Science News Space** | `RSS` | 🟢 OK | `200` | 20 entries | 87h ago |
| **Keck Observatory** | `RSS` | 🟢 OK | `200` | 10 entries | 65h ago |
| **SpaceDaily** | `RSS` | 🟢 OK | `200` | 10 entries | 1h ago |
| **The Space Review** | `RSS` | 🟢 OK | `200` | 702 entries | 168h ago |
| **NASA APOD API** | `API` | 🟢 OK | `200` | API Online | - |
| **NASA DONKI CME API** | `API` | 🟢 OK | `200` | API Online | - |
| **NOAA SWPC Kp 1-minute** | `API` | 🟢 OK | `200` | API Online | - |
| **arXiv Astronomy API** | `API` | 🟢 OK | `200` | API Online | - |
| **Open Notify ISS Position** | `API` | 🟢 OK | `200` | API Online | - |
<!-- END_SOURCE_HEALTH_TABLE -->

## License

MIT License. Free for open-source and commercial agentic search workflows.
