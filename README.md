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
- `calendar/{year}.json` — precomputed events, plain HTTPS (`python tools/build_calendar.py`)

## Yearly rituals (the only manual maintenance)
1. **Meteor showers (once a year, ~10 min).** Open the IMO shower calendar
   (https://www.imo.net/members/imo_showers/calendar/), transcribe exact peak
   datetimes + ZHR into `data/meteor_showers_{year}.json` (copy the 2026 file's
   shape), push. Until that file exists, the engine serves templated peaks from
   `data/meteor_showers_base.json` (accurate to ~±1 day, flagged `exact: false`).
   We deliberately ingest IMO once instead of scraping it per-query (no API, HTML/PDF only).
2. **Calendar spot-check (weekly, automatic).** `build_calendar.yml` rebuilds current +
   next year every Sunday and commits. Just glance at the bot commit occasionally.
3. **Feed health (weekly, automatic).** `weekly_feed_check.yml` reports dead RSS.
   If a feed stays dead, remove or replace its entry in `astro_search/sources/rss.py`.
