# AstroSearch — Supplement Handoff v2.1
> Companion to `AGENT_HANDOFF.md` (how) + `astro_source_registry.md` (what).
> Purpose: close the registry-vs-handoff drift, lock deployment for GitHub Actions + Cloudflare, fix time/timezone handling, define BM25 on Actions, and nail celestial-event precision (date/time + where visible).
> Last updated: 2026-09-16. All live checks re-verified this date: USNO v4.0.1 OK, NOAA Kp 1-min OK, JPL CAD v1.5 OK, arXiv OK (105k astro-ph), ADS 401-gated OK, Open Notify ISS OK.

> Implementation update (2026-09-17): [CAPABILITIES.md](CAPABILITIES.md) is the current
> status reference. The live-check date above is historical, not a new verification.
> USNO lunar-eclipse year retrieval is not implemented; annual output now separates
> snapshots and references and does not invent UTC instants for date-only events.


---

## 1. Deployment Decision for Immediate Need

### 1.1 Current reality
- Agents = Python scripts in GitHub Actions + Gemini free tier + Cloudflare Worker (for caching/proxy/site ops).
- AstroSearch v2 = Python library (`pip install git+https://...@main`), no server.

### 1.2 Recommendation: stay library-mode for v2, add precomputed artifacts on Cloudflare
Do NOT host a Python server yet. Reasons:
- GitHub Actions `ubuntu-latest` already runs `feedparser + requests + python-dateutil + skyfield + ephem` with zero config. No cold start, no egress fee, no extra service to keep awake.
- Cloudflare Workers free (100k req/day) is JS/WASM-first. Python on Workers (beta, Pyodide) cannot comfortably run `skyfield` ephemeris files (~15 MB), `feedparser` fan-out to 30 feeds with 12s timeouts, or `numpy/pandas`. CPU 10 ms free limit kills fan-out.
- A server adds auth, rate-limit, uptime burden you explicitly marked non-goal.

**Target architecture v2:**

```
GitHub Actions job (agent script)
  └─ pip install astro-search@main
  └─ from astro_search import TOOL_DECLARATIONS, tool_handler
  └─ tool_handler("astro_search", {...})  # in-process, ~2-6s with ThreadPoolExecutor(5)
  └─ optional: read https://<your-worker>/astro-calendar/2026.json (precomputed)
```

**Cloudflare role in v2 (thin, high-value):**
1. Host `astro-calendar/{year}.json` on Workers Sites / R2 / GitHub Pages behind Worker cache. Rebuilt weekly by Actions cron. Agents fetch it in <200 ms instead of calling USNO+IMO live every time.
2. Optional KV cache: `GET /cache?q=hash` for cross-run dedup. Only if you hit NASA DEMO_KEY limits (30/hr, 50/day). Otherwise skip — Actions cache + SQLite file is enough.
3. Keep existing Worker for Stellar Illusion site; don't couple agent runtime to it.

### 1.3 Free alternatives evaluated (for v3 server if ever needed)
| Option | Free tier | Python fit | Verdict |
|---|---|---|---|
| GitHub Actions + library (current) | 2000 min/mo, 500 MB cache | perfect | **use for v2** |
| Cloudflare R2 + Pages (static JSON) | 10 GB, unlimited egress via Workers | perfect for calendar | **use for calendar artifact** |
| Hugging Face Spaces (CPU) | free, sleeps | good for demo API | v3 demo only |
| Render free web service | 750h/mo, sleeps 15m | good | v3 if you need REST |
| Fly.io free allowance | ~3 shared VMs | good | v3 alternative |
| Supabase / Upstash Redis | 500 MB / 10k cmd/day | good for shared cache | only if cross-run cache needed |
| Vercel serverless Python | 100 GB-h | timeout 10-60s, no skyfield data persistence | avoid for fan-out |

**Action:** No new infra for v2. Add one Actions workflow `build_calendar.yml` → writes `calendar/2026.json` → publishes to Cloudflare/Pages. Workers stay static.

---

## 2. Closing Registry-vs-Handoff Drift: Full Source Expansion

Handoff implements a subset for doc-size reasons. This section maps EVERY registry section to code status.

### 2.1 RSS (registry §1, 40 feeds) → `sources/rss.py`
**v2 core (implement now, 8 feeds cover 90%):** NASA News, NASA Science, ESA News, EarthSky, Universe Today, Sky & Telescope, JWST, AAS Nova.

**v2 extended (add with same class, just config entries):**
- NRAO, Hubble, ESO, Chandra, Space.com, Spaceflight Now, SpaceNews, Planetary Society, In-The-Sky (`rss.php?feed=dfan`), AMS (`amsmeteors.org/feed`), Spaceweather.com, Science News Space, Centauri Dreams, Astronomy Magazine.
- Deferred but config-ready: ESA Space Safety, Astronomy.com Sky-This-Week, Full-Moon-Calendar, APOD RSS, Astronomy Now (UK, 403-prone — wrap in safe_fetch), Bad Astronomy SyFy, SpaceDaily, SpaceRef, Collect Space, Space Review, Clear Skies Blog, AAS News, Keck.
- arXiv RSS (`arxiv.org/rss/astro-ph*`) — do NOT poll via RSS; use `sources/arxiv.py` API instead (cleaner dedup). Keep RSS entry disabled with comment.

Implementation note: single `RSSSource` class parameterized by `RSS_FEEDS` list from handoff §7A. Adding a feed = 7-line dict, no new code. Health-gated by `tools/verify_feeds.py` weekly.

### 2.2 NASA api.nasa.gov (registry §2A) → `sources/nasa.py`
Implement all 7 from handoff + 3 extra from registry:
- Done: APOD, NeoWs Feed/Lookup, DONKI CME/FLR/GST/notifications, Image Library search.
- Add: EONET `/EONET/v3/events?category=severeStorms`, Exoplanet Archive TAP passthrough (`pscomppars` select), Mars Rover Photos (trivial, 10 lines, high content value for Stellar Illusion).
- Key: `ASTRO_NASA_KEY` else `DEMO_KEY`. Log warning on DEMO_KEY + cap to 3 NASA calls/query.

### 2.3 JPL (registry §2B) → `sources/jpl.py`
Handoff has CAD + SBDB + Fireball + Horizons OBSERVER. Add:
- Sentry (`/sentry.api` — impact risk, same parser as CAD), Scout (`/scout.api` — fresh NEO candidates). Both return same `fields/data` array shape; reuse CAD normalizer.
- Horizons: keep one method `get_observer_table(command, date, lat, lon)` returning RA/Dec/Az/El/range. Bodies map: 10 Sun, 301 Moon, 499 Mars, 599 Jupiter, etc.

### 2.4 USNO (registry §2C) → `sources/usno.py`
Handoff covers year/date moon, solar/lunar eclipses, seasons, rstt/oneday. Add:
- `siderealtime?date=&coords=` (1 method, same pattern).
- Note apiversion `4.0.1` observed live — response shape `{"phasedata":[{"phase","day","month","year","time"}]}` with no timezone (assume UTC, label explicitly).

### 2.5 NOAA SWPC (registry §2D+§3A) → `sources/noaa.py`
Handoff lists 9 endpoints. Implement all + GOES primary X-ray (`/json/goes/primary/xrays-7-day.json`) + `noaa-planetary-k-index.json` for G-scale. Add parsers:
- `kp_now()` from `planetary_k_index_1m.json` (last non-zero entry; 2026-09-16 live Kp 2-3 observed).
- `ovation_aurora_latest.json` → probability grid link + `aurora_alert(kp,bz)` already spec'd.
- `3-day-forecast.txt` / `27-day-outlook.txt` → plain-text chunked to 800 chars in `extra`.

### 2.6 VO / TAP (registry §2E+§3E) → NEW `sources/tap.py` (v2.1, not v2 blocker)
SIMBAD, VizieR, NED, Gaia DR3, Exoplanet TAP all speak TAP+ADQL `.../tap/sync?REQUEST=doQuery&LANG=ADQL&QUERY=...`.
- v2: do NOT implement full TAP. Add only `Exoplanet Archive pscomppars` via simple TAP GET (no `astroquery` dep) for `object_lookup` exoplanets.
- v2.1: add `sources/tap.py` with `query_tap(base_url, adql)` helper; SIMBAD for star/galaxy coords, Gaia for parallax. Depend on `requests` only; `astroquery` optional extra.
- ADS (`sources/ads.py`): gated on `ASTRO_ADS_KEY`, `search_papers` with citation_count sort. TNS: v2.1 (needs free account + POST).

### 2.7 Event-specific (registry §2F+§3B/3C/3D) → wire into `core.get_celestial_events()`
- In-The-Sky `whatsup.php?lat=&lng=&date=` — HTML, parse `<li>` events; fallback to RSS if blocked.
- Sunrise-Sunset `api.sunrise-sunset.org/json` — no key, use for `rstt` fallback when USNO down.
- `ephemeris.fyi/get_single_body_position` — no key, use as second fallback for positions.
- Open Notify `iss-now.json` + `astros.json` — implement `get_iss()` (verified live). 15 lines.
- AMS shower calendar + IMO `calendar?year=` / `cal2026.pdf` — do NOT scrape per-query. Ingest once/year into `data/meteor_showers.json` (name, peak UTC, ZHR, parent comet, hemisphere). Commit to repo.
- NASA Eclipse site (`eclipse.gsfc.nasa.gov`) — static; link out in `extra.nasa_eclipse_url`, don't scrape.

Scoring matrix from registry §4 stays canonical; router in `core.py` follows it.

---

## 3. BM25 + Rerank on GitHub Actions: Verdict

**Yes, safe for Actions. Constraint: pure-Python lexical only for v2.**

- `ubuntu-latest` runners have no BLAS/GPU guarantee, 7 GB RAM, ~2 cores. Pure-Python BM25 over ≤50 results/query = <20 ms, zero native deps.
- Do NOT add `rank-bm25`, `faiss`, `torch`, `sentence-transformers` to `install_requires`. They pull `numpy/scipy/torch` (~200-800 MB), blow cold install from ~15s to 3-8 min and risk Actions cache eviction.
- Recommended v2 ranker (extends handoff §ranker, keeps weights):
  ```python
  # no new deps. ~30 lines in ranker.py
  def bm25_score(query_terms, doc_terms, avgdl, N, df, k1=1.5, b=0.75): ...
  final = bm25_norm*0.35 + intent_match*0.25 + authority_norm*0.20 + freshness*0.20
  ```
  Compute IDF from current result set (N = len(results)), not global corpus. Good enough for 5-50 docs.
- Semantic rerank (MiniLM-L6-v2, 80 MB) → gate behind `extras_require={"semantic": ["sentence-transformers>=2.0"]}` + env `ASTRO_SEMANTIC=1`. Lazy-import only when set. Default OFF in Actions. Document as v2.1 experiment.
- Keep handoff's `title_similarity` Jaccard for dedup (already dependency-free). Threshold 0.65 validated.

**Actions proof:** `pip install -e .` (feedparser, requests, python-dateutil, skyfield, ephem) installs in <90s on `ubuntu-latest`, no compiler needed. Add `pytest tests/test_ranker.py` with 20 fixed docs to lock scores.

---

## 4. Temporal Context: "What Is Today?" Design (Required Fix)

Problem: agent asks `astro_search(query="phase of moon today")` with no date. Engine must resolve `today` deterministically.

### 4.1 Single source of truth: engine injects time, never trusts LLM
```python
# core.py
from datetime import datetime, timezone
now_utc = datetime.now(timezone.utc)  # e.g. 2026-09-16T09:43:00+00:00
today_str = now_utc.strftime("%A, %Y-%m-%d")  # Wednesday, 2026-09-16
```

### 4.2 Tool schema change (backward compatible)
Add optional params to all 4 declarations (LLM may omit; engine fills):
```json
{
  "now_utc": {"type":"string","description":"ISO-8601 now in UTC. Omit to use server time."},
  "timezone": {"type":"string","description":"IANA tz e.g. Asia/Kolkata or UTC offset. Default UTC."},
  "lat": {"type":"number"}, "lon": {"type":"number"}
}
```
`tool_handler` fills missing with server `now_utc`. Returns `context` in every response:
```python
{"query":..., "intent":..., "context":{"now_utc":"2026-09-16T09:43:00Z","today":"Wednesday, 2026-09-16","tz":"UTC"},"results":...,
 "markdown":"_Context: Wed 2026-09-16 09:43 UTC._\n\n..."}
```

### 4.3 Relative-date resolver (`intent.py` + new `timeparse.py`, `python-dateutil` only)
- Map: today/tonight/tomorrow/yesterday/this weekend/next week/this month → concrete `date_min/date_max` passed to USNO/JPL/NOAA.
- Past-year regex from handoff §9 stays: label `is_historical=true` in `extra`.
- Agent system prompt (in stellarillusion-agents repo) must prepend: `Today is {now_utc} (UTC). User tz: {tz}. Pass through to astro_search.` Engine echoes resolved date in markdown so editor sees grounding.

### 4.4 What to tell agents
> You don't need to compute dates. Send raw query + optional lat/lon/tz. Engine resolves "today/tonight/next" against server UTC and returns `event_date` in UTC + local display string. Always show `context.now_utc` in citations.

---

## 5. Celestial-Event Precision: Date/Time + Where Visible

Requirement: for every event return accurate UTC instant + visibility region, not just "Sep 2026".

### 5.1 Schema extension (additive, non-breaking to handoff §4 contract)
```python
{
  # existing: title, summary, url, source, source_type, authority, category,
  # published, freshness_h, entities, location, event_type, event_date, authors, extra
  # ADD:
  "event_date_utc": str | None,   # ISO-8601 UTC instant, e.g. "2026-09-26T16:49:00Z"
  "event_end_utc": str | None,    # for eclipses/showers windows
  "visibility": str | None,       # human regions: "Asia, Australia, Pacific; not visible Americas"
  "visibility_url": str | None,   # link to NASA/USNO visibility map when available
}
```
Keep old `event_date/location` populated for compat; new fields authoritative.

### 5.2 Per-type source of truth
| Event | Primary (UTC instant) | Visibility (where) | Fallback |
|---|---|---|---|
| Moon phases | USNO `/moon/phases/date` + skyfield verify | global (no region) | `ephem` local |
| Solar/lunar eclipse | USNO `/eclipses/{solar,lunar}/year` for date+type | NASA eclipse.gsfc map link in `visibility_url` + USNO region string parsed | timeanddate link-out |
| Meteor shower peak | `data/meteor_showers.json` (IMO/AMS ingested yearly) | hemisphere + radiant + moon interference (from USNO moon phase same night) | AMS RSS |
| Conjunction/opposition/transit | skyfield + JPL Horizons OBSERVER | lat/lon-specific rise/set/Az/El via Horizons or `ephemeris.fyi` | In-The-Sky RSS/whatsup |
| Sunrise/sunset/moonrise | USNO `rstt/oneday?coords=&tz=` | exact lat/lon + tz conversion | sunrise-sunset.org |
| Aurora | NOAA Kp 1-min + Ovation + 3-day text | Kp→G-scale→lat band (`Kp>=7 mid-lat, >=5 high-lat`) + `aurora_alert()` string | Spaceweather.com RSS |
| Solstice/equinox | USNO `/seasons?year=` | global instant, display in UTC + user tz | skyfield |

### 5.3 Timezone handling
Store canonical `event_date_utc` always in `Z`. Add `extra.local_display` only when `tz/lat/lon` supplied: `dateutil.tz.gettz(tz)` conversion. Never guess tz — default UTC and label `UTC`.

### 5.4 `get_celestial_events(year)` output
Return grouped: `{moon_phases:[...], solar_eclipses:[...], lunar_eclipses:[...], meteor_showers:[...], seasons:[...]}` each with new precision fields. This JSON is what `build_calendar.yml` snapshots to `calendar/{year}.json` for Cloudflare hosting.

---

## 6. Other Gap Fixes Accepted (from review)

1. Intent `what is` collision → route: if entity in planets/deep_sky/missions + (how far|mass|size|distance|magnitude) → `object_lookup`, elif `explain|define|difference|why|how does` → `concept_explanation`. Unit-test both.
2. `requirements.txt`/`setup.py`: keep core `feedparser, requests, python-dateutil`; move `ephem, skyfield, astropy, astral` to `extras_require["local"]` but install `skyfield+ephem` in Actions `test.yml` (they're wheels, fast). No torch.
3. SQLite persistent cache (new `cache_sqlite.py`, stdlib only): 15 min news/Kp, 24h events/papers. Path `~/.astro_cache.db` or `$ASTRO_CACHE_PATH`. Falls back to `TTLCache` in-memory if unwritable. Enables Actions `actions/cache@v4` reuse + Cloudflare KV later without code change.
4. NASA/ADS keys: `ASTRO_NASA_KEY`, `ASTRO_ADS_KEY` from Actions secrets; warn + degrade gracefully when absent (NASA→JPL CAD, ADS→arXiv).
5. Boilerplate/paywall filters from handoff §9 stay as written.

---

## 7. How to Use These Three Docs to Build to Fullest

- `astro_source_registry.md` = allowed universe. No new source without adding here + health check.
- `AGENT_HANDOFF.md` = build order Steps 1-14, contracts, tool shapes. Follow sequentially.
- This supplement = deltas: deployment (§1), source-to-file map (§2), BM25 rule (§3), time injection (§4), event precision (§5), gap patches (§6). If conflict, this doc wins on architecture, handoff wins on schema unless §5 extension noted.

**Definition of Done delta (append to handoff §19):**
10. `tool_handler("astro_search",{"query":"phase of moon today"})` returns `context.now_utc` = today UTC + USNO phase within 1 day.
11. `tool_handler("astro_events",{"year":2026})` entries all have `event_date_utc` + `visibility` or explicit null with reason.
12. `pytest` passes offline (mocked HTTP) + live smoke passes with keys absent (degraded, not crash).
13. `calendar/2026.json` builds and validates against schema.

*End supplement. Build agent: read registry → handoff → this file, then start at handoff Step 1 with §4-§5 patches applied from day one.*
