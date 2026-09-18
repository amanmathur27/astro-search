# AstroSearch v2.1 — free astronomy search engine (Python library)

`from astro_search import TOOL_DECLARATIONS, tool_handler` — that's the integration.

## Install
```
pip install git+https://github.com/amanmathur27/astro-search.git@main
pip install -e ".[local]"  # optional offline moon appearance; cached Skyfield only
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
- `CAPABILITIES.md` — current implementation, verification limits and remaining work (wins on current-status conflicts)
- `AGENT_HANDOFF.md` — historical build spec and intended contracts
- `astro_source_registry.md` — source-discovery universe, not guaranteed adapter coverage
- `SUPPLEMENT_HANDOFF.md` — historical deployment and precision requirements
- `calendar/{year}.json` — precomputed events (`python tools/build_calendar.py`); existing files may use the legacy schema

### Calendar v2 and verification

Fresh calendar output has `schema_version: 2`: `results` contains chronological,
requested-year events; `live_snapshots` and `references` are separate. Date-only
solar eclipses carry `event_date: YYYY-MM-DD`, `date_only: true` and
`event_date_utc: null`. Inspect `completeness` and uncertainty metadata before use.
The build script validates every requested year before replacing any file. It will
fail rather than publish incomplete annual coverage. Lunar eclipses remain reference-only.

Run offline regressions with `python -m pytest tests -q`; tests block live Requests
traffic and isolate persistent caches. CI also checks built-wheel resource loading.
No hosted service or automatic ephemeris download is required.

## Yearly rituals (the only manual maintenance)
1. **Meteor showers (once a year, ~10 min).** Open the IMO shower calendar
   (https://www.imo.net/members/imo_showers/calendar/), transcribe exact peak
   datetimes + ZHR into `astro_search/data/meteor_showers_{year}.json` (copy the 2026 file's
   shape), push. Until that file exists, the engine serves templated peaks from
   `astro_search/data/meteor_showers_base.json` (accurate to ~±1 day, flagged `exact: false`).
   We deliberately ingest IMO once instead of scraping it per-query (no API, HTML/PDF only).
2. **Calendar spot-check (weekly, automatic).** `build_calendar.yml` rebuilds current +
   next year every Sunday and commits. Just glance at the bot commit occasionally.
3. **Feed health (weekly, automatic).** `weekly_feed_check.yml` reports dead RSS.
   If a feed stays dead, remove or replace its entry in `astro_search/sources/rss.py`.
