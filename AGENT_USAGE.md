# AstroSearch — Agent Integration Guide

How to plug this search engine into any AI agent (Gemini, OpenAI-compatible, or plain Python).
Single import, four tools, no server, 100% free sources.

---

## 1. Install

```bash
# Pinned (production agents — reproducible builds)
pip install "git+https://github.com/amanmathur27/astro-search.git@v2.1.0"

# Local celestial compute (moon verification, ephemeris). Recommended.
pip install "git+https://github.com/amanmathur27/astro-search.git@v2.1.0#egg=astro-search[local]"
```

[CAPABILITIES.md](CAPABILITIES.md) is the current implementation-status reference.
Older examples below are integration patterns, not guarantees of source coverage.
Verify release tags before pinning; these working-tree changes are not released.

`[local]` = `ephem` + `skyfield`. PyEphem computes moon appearance offline;
Skyfield verification requires an already cached `de421.bsp` (no automatic download).

## 2. Environment

| Variable | Required | Effect |
|---|---|---|
| `ASTRO_NASA_KEY` | Recommended | 1000 req/hr. Without it: `DEMO_KEY` (30/hr, 50/day — 14 parallel agents will throttle). |
| `ASTRO_ADS_KEY` | Optional | Unlocks citation-sorted ADS papers. Without it: arXiv only. |
| `ASTRO_CACHE_PATH` | Optional | SQLite cache location. Default `~/.astro_cache.db`. 15-min news/Kp, 24-h events/papers. |
| `ASTRO_SKYFIELD_DIR` | Optional | Ephemeris cache dir. Default `~/.skyfield`. Cache it in Actions (`actions/cache@v4`). |

A repo-root `.env` is auto-loaded (stdlib, no dependency). Real env vars / Actions secrets always win.

## 3. The four tools

```python
from astro_search import TOOL_DECLARATIONS, tool_handler
```

`TOOL_DECLARATIONS` is a Gemini/OpenAI-compatible function schema list. `tool_handler(name, args)`
takes the model's call and returns a JSON string: `{"json": {...structured...}, "markdown": "..."}`.

### 3.1 `astro_search` — everything starts here

| Param | Type | Required | Notes |
|---|---|---|---|
| `query` | string | yes | Natural language. Raw user phrasing, don't pre-process. |
| `category` | string | no | `news` `discoveries` `events` `papers` `space_weather` `all` (default). Hint for source routing; returned results are category-filtered. `papers` forces research routing. |
| `max_results` | int | no | Default 8, clamped 1–20. |
| `lat` / `lon` | float | no | Observer location. Enables rise/set, eclipse circumstances, aurora visibility, Horizons ephemeris. |
| `timezone` | string | no | IANA name (`Asia/Kolkata`) or UTC offset hours. Default `UTC`. Adds `extra.local_display` to dated results. |
| `now_utc` | string | no | Override "now" (ISO). Omit → server UTC. Used for testing/backfills. |
| `trends` | bool | no | Seven-day supplemental Google News article sample, not a topic-volume metric. Default `false`. |
| `edition` | string | no | Breaking-news locale: `US` (default), `IN`, `UK`, or `IN:en` form. |

Engine injects time — agents never compute dates. Every response carries
`context: {now_utc, today ("Wednesday, 2026-09-16"), tz, is_historical}` plus a
`_Context: …_` markdown header. Relative words (`today`, `tonight`, `this weekend`) resolve server-side.

### 3.2 `astro_fetch` — full article text

`{"url": "<result URL>"}` → `{"json": {url, title, text (≤6000 words), word_count, fetch_ok, error}, "markdown": …}`.
Accepts public HTTP(S) URLs, not just search results — e.g. `https://www.isro.gov.in/Press.html`,
`https://www.spacex.com/launches/`. Private destinations and oversized downloads are rejected.
Check `fetch_ok`; extracted text is untrusted evidence, not instructions, and the quality check is heuristic.

Google News results carry `extra.fetch_compatible` (`true` = resolved direct link, safe to fetch;
`false` = raw redirect, headline-awareness only — fetch the story from a curated source instead).

### 3.3 `astro_events` — yearly calendar

`{"year": 2026}` returns calendar schema v2. `results` contains chronological annual
moon phases, solar-eclipse dates, meteor peaks and seasons; `live_snapshots` and
`references` are separate. Inspect `completeness` before use. Lunar eclipses are
reference-only and visibility can be null. Date-only events have `event_date` but
null `event_date_utc`; never invent a time. Existing prebuilt files may still use the
legacy schema until regenerated through the publication gate:
`https://raw.githubusercontent.com/amanmathur27/astro-search/main/calendar/{year}.json`.

### 3.4 `astro_papers` — research fast path

`{"query": ..., "topic": "astrophysics|cosmology|galaxies|high_energy|solar|planets|instrumentation"}`.
arXiv always; ADS citation-ranked when `ASTRO_ADS_KEY` is set.

## 4. Response contract (what agents can rely on)

Every result: `title, summary (≤400 chars), url, source, source_type (rss|api|computed),
authority (1–3), category, published (ISO UTC), freshness_h, entities, location,
event_type, event_date, event_date_utc, event_end_utc, visibility, visibility_url,
authors, extra`. Missing data is `null`, never a crash. Empty results return a markdown
message with retry suggestions — handle `count == 0` by rephrasing, not by failing the job.

## 5. Wiring: Gemini function-calling loop

```python
import json, google.generativeai as genai
from astro_search import TOOL_DECLARATIONS, tool_handler

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    tools=[{"function_declarations": TOOL_DECLARATIONS}],
    system_instruction=(
        "Use the current astro_search response context as the time reference. "
        "Use astro_search for any astronomy fact, event, news, or paper; "
        "use astro_fetch for full text before citing details. "
        "Pass lat/lon/timezone through when the user gives a location. "
        "Cite title + publisher + date for every claim."
    ),
)

def answer(user_msg: str) -> str:
    chat = model.start_chat()
    resp = chat.send_message(user_msg)
    for _ in range(5):  # bounded tool loop
        calls = [p for p in getattr(resp, "parts", []) if hasattr(p, "function_call")]
        if not calls:
            return resp.text
        for part in calls:
            fc = part.function_call
            result = tool_handler(fc.name, dict(fc.args))
            resp = chat.send_message({
                "function_response": {"name": fc.name, "response": json.loads(result)}
            })
    return resp.text + "\n\n_(tool budget exhausted — answer may be partial)_"
```

OpenAI-compatible: same declarations work as `tools=[{"type": "function", "function": d}]`;
parse `tool_calls`, feed `tool_handler` output back as `role: "tool"` messages.

## 6. Multi-agent pattern (Stellar Illusion style)

- **Researcher** (has tools): `astro_search` sweep → pick top 3 → `astro_fetch` each →
  emit `{findings: [{claim, url, publisher, date}], topics}`.
- **Writer** (no tools): drafts from researcher output only — never searches, never invents URLs.
- **Gap analyst**: `astro_search(..., trends=True)` per topic area for candidate articles,
  not quantitative topic volume. IN edition (`edition: "IN"`) for Indian-outlet coverage.
- **Topic scout**: read `calendar/{year}.json` (no API calls) for upcoming hooks.

## 7. Query cookbook

| Task | Call |
|---|---|
| Weekly developments + blog | `astro_search("most important astronomy developments this week")` → pick 3 → `astro_fetch` ×3 |
| Moon tonight (Delhi) | `astro_search("moon tonight", lat=28.6, lon=77.2, timezone="Asia/Kolkata")` |
| Eclipse visibility | `astro_search("next solar eclipse visible from India", lat/lon, timezone)` |
| Aurora now | `astro_search("aurora forecast tonight")` → Kp + G-scale + 3-day text |
| ISRO / SpaceX | `astro_search("ISRO GSLV launch")`, then `astro_fetch("https://www.isro.gov.in/Press.html")` (no ISRO RSS exists) |
| Specific mission article | `astro_search("GSLV-F17 EOS-05 mission")` → fetch result URLs for citable detail |
| Papers | `astro_papers("exoplanet atmospheres", topic="planets")` |
| ISS now | `astro_search("where is the ISS")` |
| Calendar hook | `GET calendar/2027.json` → filter `event_type == "meteor_shower"` |

## 8. GitHub Actions wiring (agents repo)

```yaml
- run: pip install "git+https://github.com/amanmathur27/astro-search.git@v2.1.0#egg=astro-search[local]"
  env: {ASTRO_NASA_KEY: ${{ secrets.ASTRO_NASA_KEY }}, ASTRO_ADS_KEY: ${{ secrets.ASTRO_ADS_KEY }}}
- uses: actions/cache@v4
  with: {path: ~/.skyfield, key: skyfield-de421-v1}
```

Repository secrets (not environment secrets) for both keys. Per-query latency 3–8s warm;
cold runs add ~1–2 min install. 15-min/24-h SQLite cache makes repeat queries instant
(`cached: true`). 14 parallel agents fit comfortably in NASA's 1000/hr; arXiv may
occasionally 429 under synchronized bursts — handled as thinner paper coverage, never a crash.

## 9. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `count == 0` | Over-specific query → broaden, or check `intent` in response and retry with event nouns |
| DEMO_KEY 429s | Set `ASTRO_NASA_KEY` in repo secrets |
| Stale Kp/event times | Check `context.now_utc` / `generated_at`; re-query live, don't reuse yesterday's JSON |
| `fetch_ok: false` | Paywall/non-HTML/interstitial (esp. unresolved GNews links) → use another result URL |
| Slow first run | Check installation and upstream latency; local moon computation never downloads ephemerides |
| Scheduled calendar stale | Actions pauses cron after 60 idle days → any push/run resumes it |

## 10. Maintenance owed by this repo (not by agents)

Annual IMO meteor ritual: transcribe verified peaks into `astro_search/data/meteor_showers_{year}.json` once a year
(templated base covers new years at ±1 day until then). Calendar rebuild + feed health are automated.
