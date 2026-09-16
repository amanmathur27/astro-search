# AstroSearch v2.1 — free astronomy search engine (Python library)

`from astro_search import TOOL_DECLARATIONS, tool_handler` — that's the integration.

## Install
```
pip install git+https://github.com/USER/astro-search.git@main
pip install -e ".[local]"  # skyfield+ephem for local event precision (optional)
```

## Use
```python
from astro_search import tool_handler
print(tool_handler("astro_search", {"query": "next lunar eclipse", "max_results": 8}))
print(tool_handler("astro_search", {"query": "aurora forecast tonight"}))
print(tool_handler("astro_events", {"year": 2026}))
print(tool_handler("astro_fetch", {"url": "https://earthsky.org/..."}))
```

## Env
- `ASTRO_NASA_KEY` (else DEMO_KEY, 30/hr)
- `ASTRO_ADS_KEY` (else arXiv only)
- `ASTRO_CACHE_PATH` (else ~/.astro_cache.db)

## Docs
- `AGENT_HANDOFF.md` — build spec, contracts
- `astro_source_registry.md` — source universe
- `SUPPLEMENT_HANDOFF.md` — deployment, BM25, time injection, event precision (wins on conflicts)
- `calendar/{year}.json` — precomputed events for Cloudflare/Pages (`python tools/build_calendar.py 2026`)
