# AstroSearch — Complete Free Source Registry
**Last researched: September 2026**  
The master reference before writing any code. Every source here is verified free as of research date.

> Current adapter coverage and limitations are in [CAPABILITIES.md](CAPABILITIES.md).
> This is a source-discovery registry, not a list of implemented or currently healthy
> integrations. USNO lunar-eclipse API support must not be inferred from the tables
> below: current lunar-eclipse output is a NASA reference link only. Access and reuse
> terms must be checked separately.


---

## Legend
- **Key Required?** — Yes / No / Optional (No = works without any key)
- **Rate Limit** — per hour or per day unless noted
- **Data Format** — what your Python code gets back
- **Reliability** — ★★★ (institutional, stable) / ★★ (stable but not official) / ★ (community, may go offline)

---

## SECTION 1 — NEWS & CONTENT RSS FEEDS

These are the backbone. Feedparser reads them directly. No auth, no key.

| # | Source | RSS URL | Covers | Update Freq | Reliability | Notes |
|---|--------|---------|--------|-------------|-------------|-------|
| 1 | **NASA News** | `https://www.nasa.gov/news-releases/feed/` | Official NASA news, missions, discoveries | Daily | ★★★ | Most authoritative source |
| 2 | **NASA Science** | `https://science.nasa.gov/feed/` | Science mission news, APOD links | Daily | ★★★ | Broader than news-releases |
| 3 | **ESA News** | `https://www.esa.int/rssfeed/Our_Activities/Space_Science` | European Space Agency science | Daily | ★★★ | European missions (JWST partner, Hera, etc.) |
| 4 | **ESA Space Safety** | `https://www.esa.int/rssfeed/Space_Safety` | Near-Earth objects, space debris | Weekly | ★★★ | Good for asteroid/comet events |
| 5 | **Sky & Telescope** | `https://skyandtelescope.org/astronomy-news/feed/` | News + observing events | Daily | ★★★ | Premier English-language astronomy magazine |
| 6 | **EarthSky** | `https://earthsky.org/feed/` | Sky events, planets, sun/moon, aurora | Daily | ★★★ | Best for public-facing celestial event coverage |
| 7 | **Space.com** | `https://www.space.com/feeds/all` | Broad space news, missions, science | Hourly | ★★★ | High volume, very current |
| 8 | **Universe Today** | `https://www.universetoday.com/feed/` | In-depth space/astronomy news | Daily | ★★★ | Excellent depth, reliable since 1999 |
| 9 | **Astronomy Magazine** | `https://astronomy.com/feed` | News + observing + history | Daily | ★★★ | US print mag, strong event calendar |
| 10 | **Astronomy.com Sky This Week** | `https://astronomy.com/observing/sky-this-week/feed` | Weekly celestial event digest | Weekly | ★★★ | Best "what's up this week" feed |
| 11 | **Astronomy.com Full Moon Calendar** | `https://astronomy.com/observing/full-moon-calendar/feed` | Moon phases, full moon dates | Monthly | ★★★ | Direct moon event data |
| 12 | **The Planetary Society** | `https://www.planetary.org/articles?rss=1` | Planetary science, advocacy, missions | Weekly | ★★★ | Science-focused, no fluff |
| 13 | **Spaceflight Now** | `https://spaceflightnow.com/feed/` | Launch schedules, mission updates | Daily | ★★★ | Best launch coverage |
| 14 | **SpaceNews** | `https://spacenews.com/feed/` | Industry, policy, satellite business | Daily | ★★★ | Professional/industry angle |
| 15 | **SpaceDaily** | `https://www.spacedaily.com/spacedaily.xml` | Aggregated space news | Daily | ★★ | Aggregator, broad coverage |
| 16 | **NRAO (Nat. Radio Astronomy Observatory)** | `https://public.nrao.edu/news/feed/` | Radio astronomy, VLA, VLBA news | Monthly | ★★★ | Institutional, high-quality discoveries |
| 17 | **Hubble Site** | `https://hubblesite.org/api/v3/news_releases/all?format=rss` | Hubble Space Telescope news | Weekly | ★★★ | Official NASA/STScI Hubble news |
| 18 | **JWST (Webb Telescope)** | `https://webbtelescope.org/news/webb-news/rss.xml` | James Webb discoveries & images | Weekly | ★★★ | Critical for latest deep space discoveries |
| 19 | **NASA APOD** | `https://apod.nasa.gov/apod.rss` | Astronomy Picture of the Day | Daily | ★★★ | Image + explanation, great for content |
| 20 | **Astronomy Now (UK)** | `https://astronomynow.com/feed/` | UK perspective, observing news | Daily | ★★ | UK's largest astronomy magazine |
| 21 | **Bad Astronomy (Phil Plait)** | `https://www.syfy.com/syfy-wire/author/phil-plait/rss` | Accessible astronomy/science news | Weekly | ★★ | Expert communicator, good for blog content |
| 22 | **ArXiv Astro-ph (new)** | `https://arxiv.org/rss/astro-ph` | All new astrophysics preprints | Daily | ★★★ | Raw research, high volume |
| 23 | **ArXiv Astro-ph.EP** | `https://arxiv.org/rss/astro-ph.EP` | Exoplanet & planetary science papers | Daily | ★★★ | Specifically planetary |
| 24 | **ArXiv Astro-ph.SR** | `https://arxiv.org/rss/astro-ph.SR` | Solar & stellar astrophysics papers | Daily | ★★★ | Solar physics, stars |
| 25 | **AAS Nova** | `https://aasnova.org/feed/` | Highlights from AAS journals | Daily | ★★★ | Peer-reviewed, excellent summaries |
| 26 | **AAS News** | `https://aas.org/posts/news/feed` | American Astronomical Society news | Weekly | ★★★ | Professional society, high credibility |
| 27 | **Chandra X-ray Observatory** | `https://chandra.harvard.edu/rss/news.rss` | X-ray astronomy, high energy events | Monthly | ★★★ | NASA flagship mission |
| 28 | **Keck Observatory** | `https://www.keckobservatory.org/feed/` | Observatory news, discoveries | Monthly | ★★ | World's largest optical telescope |
| 29 | **ESO (European Southern Observatory)** | `https://www.eso.org/public/news/feed.rss` | European observatory discoveries | Weekly | ★★★ | VLT, ELT, ALMA news |
| 30 | **American Meteor Society** | `https://www.amsmeteors.org/feed/` | Meteor showers, fireballs, reports | Weekly | ★★★ | Best meteor data source |
| 31 | **In-The-Sky.org** | `https://in-the-sky.org/rss.php?feed=dfan` | Daily astronomy events, planet positions | Daily | ★★ | Excellent for conjunction/opposition events |
| 32 | **Spaceweather.com** | `https://spaceweather.com/wordpress/?feed=rss2` | Solar activity, aurora, geomagnetic | Daily | ★★ | Popular, timely space weather |
| 33 | **SpaceRef** | `https://www.spaceref.com/news/section.html?id=1&rss=1` | Space policy, mission news | Daily | ★★ | Older but reliable |
| 34 | **Collect Space** | `https://feeds.feedburner.com/CollectspaceSpaceHistoryNews` | Space history + current news | Weekly | ★★ | Good historical angle |
| 35 | **Astrobiology Magazine** | *(NASA Astrobiology has no standalone RSS; use NASA science feed)* | Astrobiology research | — | ★★★ | Use NASA science.nasa.gov feed instead |
| 36 | **Science News — Space** | `https://www.sciencenews.org/topic/astronomy/feed` | Peer-reviewed science journalism | Weekly | ★★★ | High editorial standard |
| 37 | **New Scientist — Space** | `https://www.newscientist.com/subject/space/feed/` | Popular science, space focus | Daily | ★★ | Some articles paywalled |
| 38 | **The Space Review** | `https://www.thespacereview.com/articles.xml` | Analysis, policy, opinion | Weekly | ★★ | Thoughtful long-form |
| 39 | **Clear Skies Blog** | `https://clearskies.eu/blog/feed/` | Astrophotography + observing reports | Weekly | ★ | Community, niche |
| 40 | **Centauri Dreams** | `https://www.centauri-dreams.org/feed/` | Interstellar research, deep space | Weekly | ★★ | Excellent for cutting-edge research |

---

## SECTION 2 — STRUCTURED APIs (JSON/XML, Programmatic)

These return clean data you parse in Python.

### 2A — NASA APIs (api.nasa.gov)
**Base:** `https://api.nasa.gov/`  
**Key:** Free. Register at api.nasa.gov — takes 30 seconds. DEMO_KEY works (30 req/hr, 50/day). Registered key: 1,000 req/hr.

| Endpoint | URL Pattern | Returns | Use For |
|----------|-------------|---------|---------|
| **APOD** | `/planetary/apod?api_key=KEY&date=YYYY-MM-DD` | Image URL, title, explanation | Daily astronomy image + explanation |
| **APOD (batch)** | `/planetary/apod?api_key=KEY&count=N` | N random APODs | Content generation |
| **NeoWs Feed** | `/neo/rest/v1/feed?start_date=YYYY-MM-DD&api_key=KEY` | Asteroid close-approach data | Near-Earth asteroids this week |
| **NeoWs Lookup** | `/neo/rest/v1/neo/{asteroid_id}?api_key=KEY` | Single asteroid details | Specific asteroid data |
| **DONKI — CME** | `/DONKI/CME?startDate=YYYY-MM-DD&api_key=KEY` | Coronal mass ejection events | Solar storm data |
| **DONKI — Solar Flares** | `/DONKI/FLR?startDate=YYYY-MM-DD&api_key=KEY` | Solar flare classifications | X/M/C class flares |
| **DONKI — Geomagnetic Storms** | `/DONKI/GST?startDate=YYYY-MM-DD&api_key=KEY` | Kp index storm data | Aurora events |
| **DONKI — Notifications** | `/DONKI/notifications?type=all&api_key=KEY` | Official space weather alerts | Real-time alerts |
| **EONET** | `/EONET/v3/events?category=severeStorms&status=open` | Natural event tracker | Space weather events |
| **NASA Image Library** | `https://images-api.nasa.gov/search?q=QUERY&media_type=image` | Photo library search | Image search, no key needed |
| **Exoplanet Archive** | `https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=...` | Confirmed exoplanet data | Exoplanet searches |
| **Mars Rover Photos** | `/mars-photos/api/v1/rovers/curiosity/photos?sol=1000&api_key=KEY` | Rover images by sol | Mars content |

### 2B — JPL (Jet Propulsion Laboratory) APIs
**Base:** `https://ssd-api.jpl.nasa.gov/` — **No API key required, completely free**

| Endpoint | URL Pattern | Returns | Use For |
|----------|-------------|---------|---------|
| **CAD (Close Approach Data)** | `/cad.api?dist-max=0.05&date-min=YYYY-MM-DD` | Asteroid/comet close approaches | Upcoming flybys |
| **SBDB (Small Body DB)** | `/sbdb.api?sstr=Apophis` | Asteroid/comet orbital data | Named object lookup |
| **Sentry (Impact Risk)** | `/sentry.api` | Potential Earth-impacting objects | Impact risk monitoring |
| **Fireball** | `/fireball.api?limit=10` | Reported bolide/fireball events | Fireball news |
| **Scout** | `/scout.api` | Newly discovered NEO candidates | Very fresh discoveries |
| **Horizons (ephemeris)** | `https://ssd.jpl.nasa.gov/api/horizons.api?...` | Precise planetary positions, rise/set | Ephemeris data for any date/location |
| **Horizons (OBSERVER table)** | `format=json&COMMAND='499'&OBJ_DATA='NO'&MAKE_EPHEM='YES'&EPHEM_TYPE='OBSERVER'` | RA/Dec, Az/El, distance for planets | Planet rise/set/transit times |

### 2C — USNO (US Naval Observatory) APIs
**Base:** `https://aa.usno.navy.mil/api/` — **No API key required**

| Endpoint | URL Pattern | Returns | Use For |
|----------|-------------|---------|---------|
| **Moon Phases (year)** | `/moon/phases/year?year=2026` | All moon phases for a year | Full/new/quarter moon dates |
| **Moon Phase (date)** | `/moon/phases/date?date=YYYY-MM-DD&nump=4` | Next N phases from a date | Upcoming moon events |
| **Solar Eclipses (year)** | `/eclipses/solar/year?year=2026` | Solar eclipse list | Eclipse dates, type, region |
| **Lunar Eclipses (year)** | `/eclipses/lunar/year?year=2026` | Lunar eclipse list | Eclipse dates, type |
| **Rise/Set/Transit** | `/rstt/oneday?date=YYYY-MM-DD&coords=LAT,LON&tz=N` | Sun/Moon rise, set, transit | Sunrise/sunset for any location |
| **Seasons (equinox/solstice)** | `/seasons?year=2026` | Equinox and solstice dates/times | Season change events |
| **Earth's Seasons** | `/seasons?year=2026` | Vernal equinox, summer solstice, etc. | Calendar events |
| **Sun/Moon Positions** | `/siderealtime?date=YYYY-MM-DD&coords=LAT,LON` | Sidereal time | Astronomical timing |

### 2D — NOAA Space Weather Prediction Center (SWPC)
**Base:** `https://services.swpc.noaa.gov/` — **No API key required, all public domain**

| Endpoint | URL | Returns | Use For |
|----------|-----|---------|---------|
| **3-Day Forecast** | `/text/3-day-forecast.txt` | Plain text forecast | Space weather 3-day outlook |
| **27-Day Outlook** | `/text/27-day-outlook.txt` | 27-day solar activity prediction | Long-range solar forecast |
| **Current Kp Index** | `/json/planetary_k_index_1m.json` | Kp index (1-min) | Real-time geomagnetic activity |
| **Kp Forecast** | `/json/kp_index.json` | Forecast Kp values | Aurora prediction |
| **Solar Wind Speed** | `/json/solar-wind/plasma-7-day.json` | Solar wind plasma data | CME impact detection |
| **Solar Wind IMF** | `/json/solar-wind/mag-7-day.json` | IMF Bz, Bt values | Aurora trigger data |
| **Active Alerts** | `/products/alerts.json` | All active space weather alerts | Instant alert monitoring |
| **GOES X-ray Flux** | `/json/goes/secondary/xrays-7-day.json` | X-ray flux (solar flares) | Real-time flare detection |
| **Aurora Oval (North)** | `/json/ovation_aurora_latest.json` | Aurora probability map | Where aurora is visible now |
| **Geomagnetic Storms** | `/products/noaa-planetary-k-index.json` | G-scale storm data | Storm level (G1-G5) |

### 2E — Open Astronomy / Virtual Observatory APIs
**No API key required for any of these**

| Source | Base URL | What it provides | Python package |
|--------|----------|-----------------|----------------|
| **SIMBAD** | `https://simbad.u-strasbg.fr/simbad/sim-tap/sync?REQUEST=doQuery&LANG=ADQL&QUERY=...` | 15M+ astronomical object database, coordinates, classifications | `astroquery.simbad` or raw HTTP |
| **VizieR** | `https://vizier.cds.unistra.fr/viz-bin/votable?...` | 20,000+ astronomical catalogs | `astroquery.vizier` or raw HTTP |
| **NED (NASA/IPAC Extragalactic DB)** | `https://ned.ipac.caltech.edu/tap/sync?QUERY=...` | Extragalactic objects, redshifts, galaxy data | `astroquery.ned` or raw HTTP |
| **Gaia Archive** | `https://gea.esac.esa.int/tap-server/tap/sync?REQUEST=doQuery&LANG=ADQL&QUERY=...` | 1.8 billion stars with parallax | `astroquery.gaia` or raw HTTP |
| **arXiv API** | `https://export.arxiv.org/api/query?search_query=cat:astro-ph&max_results=10` | Astrophysics preprints | Pure HTTP (XML Atom feed) |
| **ADS (Astrophysics Data System)** | `https://api.adsabs.harvard.edu/v1/search/query?q=...` | Published papers, citations | **Free key required** (generous limit) |
| **TNS (Transient Name Server)** | `https://www.wis-tns.org/api/get/object` | Supernovae, transient events | Requires free account |

### 2F — Celestial Event Specific APIs

| Source | URL | What it provides | Key Required? |
|--------|-----|-----------------|---------------|
| **In-The-Sky.org API** | `https://in-the-sky.org/whatsup.php?lat=LAT&lng=LON&alt=0&date=YYYY-MM-DD` | What's up tonight for a location | No |
| **AstroAPI.com** | `https://api.astronomyapi.com/api/v2/bodies/positions?...` | Planet positions, moon phase, star charts | Yes (free tier: limited) |
| **Sunrise-Sunset.org** | `https://api.sunrise-sunset.org/json?lat=LAT&lng=LNG&date=YYYY-MM-DD` | Sunrise, sunset, solar noon, golden hour | No |
| **IPGeolocation Astronomy** | `https://api.ipgeolocation.io/astronomy?apiKey=KEY&lat=LAT&long=LON` | Rise/set, moon phase, twilight | Yes (free: 1,000/day) |
| **Open Notify — ISS** | `http://api.open-notify.org/iss-now.json` | ISS real-time position | No |
| **Open Notify — Astronauts** | `http://api.open-notify.org/astros.json` | Who's in space right now | No |
| **NASA Exoplanet Archive TAP** | `https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+*+from+pscomppars+where+...&format=json` | 5,800+ confirmed exoplanets | No |
| **ephemeris.fyi** | `https://ephemeris.fyi/ephemeris/get_single_body_position?body=moon&latitude=LAT&longitude=LON&datetime=ISO` | Precise body positions, current sky | No (free REST API) |
| **USNO Astronomical Almanac** | `https://aa.usno.navy.mil/` | Gold standard ephemeris | No |

---

## SECTION 3 — SPECIALIZED DATA SOURCES

### 3A — Space Weather (detailed)

| Source | URL | Data | Key |
|--------|-----|------|-----|
| **NOAA SWPC (all products)** | `https://www.swpc.noaa.gov/products-and-data` | Everything — storms, flares, aurora | No |
| **SpaceWeatherLive API** | `https://www.spaceweatherlive.com/en/archive` | Historical Kp, aurora reports | No (scrape-friendly) |
| **Helioviewer** | `https://api.helioviewer.org/v2/getJP2Image/?...` | Solar images (SDO, SOHO, LASCO) | No |
| **SOHO/LASCO** | `https://soho.nascom.nasa.gov/data/synoptic/` | Coronagraph images, CME data | No |
| **GOES X-ray (NOAA)** | `https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json` | Real-time solar flare flux | No |

### 3B — Meteor & Fireball Data

| Source | URL | Data | Key |
|--------|-----|------|-----|
| **AMS Fireball Reports** | `https://fireball.amsmeteors.org/members/imo_view/` | Eyewitness fireball reports | No |
| **AMS Meteor Shower Calendar** | `https://www.amsmeteors.org/meteor-showers/meteor-shower-calendar/` | Annual shower calendar | No (HTML parse) |
| **IMO (Intl Meteor Org)** | `https://www.imo.net/members/imo_showers/calendar?year=2026` | International shower calendar | No |
| **IMO Working Shower List** | `https://www.imo.net/files/meteor-shower/cal2026.pdf` | Official annual calendar PDF | No |
| **NASA Meteor Watch** | `https://fireballs.ndc.nasa.gov/` | NASA's fireball sensor network | No |

### 3C — Eclipse Data

| Source | URL | Data | Key |
|--------|-----|------|-----|
| **NASA Eclipse Website** | `https://eclipse.gsfc.nasa.gov/` | All eclipses 1000 BCE–3000 CE | No (static pages, parseable) |
| **USNO Eclipse API** | `https://aa.usno.navy.mil/api/eclipses/solar/year?year=2026` | Solar eclipses, structured JSON | No |
| **timeanddate.com Eclipse** | `https://www.timeanddate.com/eclipse/` | Eclipse visibility by location | No (scrape-friendly) |
| **Besselian Elements** | Via JPL Horizons or NASA Eclipse site | Precise eclipse path data | No |

### 3D — Planetary / Solar System Data

| Source | URL | Data | Key |
|--------|-----|------|-----|
| **JPL Horizons** | `https://ssd.jpl.nasa.gov/api/horizons.api` | Positions of any solar system body | No |
| **JPL Small Body DB** | `https://ssd-api.jpl.nasa.gov/sbdb.api` | 1.3M+ asteroids and comets | No |
| **JPL Close Approach** | `https://ssd-api.jpl.nasa.gov/cad.api` | Asteroid close approaches | No |
| **Minor Planet Center** | `https://www.minorplanetcenter.net/iau/MPCORB.html` | Orbital elements for all known minor bodies | No |
| **CNEOS Fireball/Bolide** | `https://cneos.jpl.nasa.gov/fireballs/` | Atmospheric bolide events | No |

### 3E — Deep Sky / Catalogs

| Source | Base URL | Data | Key |
|--------|----------|------|-----|
| **SIMBAD TAP** | `https://simbad.u-strasbg.fr/simbad/sim-tap/` | 15M objects (stars, galaxies, nebulae) | No |
| **VizieR TAP** | `https://vizier.cds.unistra.fr/viz-bin/votable` | 20,000+ catalogs | No |
| **NED TAP** | `https://ned.ipac.caltech.edu/tap/` | Extragalactic objects | No |
| **Gaia DR3** | `https://gea.esac.esa.int/tap-server/tap/` | 1.8B stars, precise astrometry | No |
| **Open Cluster DB** | Vizier catalog `J/A+A/618/A93` | Stellar cluster data | No |
| **Exoplanet Archive** | `https://exoplanetarchive.ipac.caltech.edu/TAP/` | All confirmed exoplanets | No |

### 3F — Python Libraries (local computation, no API calls)

These compute answers locally — zero network dependency, zero rate limits.

| Library | Install | What it computes | Notes |
|---------|---------|-----------------|-------|
| **ephem** | `pip install ephem` | Planet positions, rise/set, moon phase, eclipses | Classic, simple API |
| **astropy** | `pip install astropy` | Full astronomy toolkit, time, coordinates, cosmology | Industry standard |
| **skyfield** | `pip install skyfield` | High-precision ephemeris, planet positions, events | Uses JPL data files |
| **astral** | `pip install astral` | Sunrise/sunset/twilight for any location | Lightweight, fast |
| **pyephem** | `pip install pyephem` | Older but widely used for orbital mechanics | Deprecated, use ephem instead |

**Key insight:** skyfield + astropy together can locally compute moon phases, eclipse dates, planet rise/set times, conjunction dates, meteor shower peaks — with no API calls at all. This is the most reliable approach for celestial events.

---

## SECTION 4 — SOURCE SCORING MATRIX

For AstroSearch, prioritize by use case:

| Use Case | Primary Source(s) | Backup |
|----------|------------------|--------|
| **Latest news** | Space.com, EarthSky, Universe Today (RSS) | NASA News, ESA News |
| **Discoveries** | JWST, Hubble, ESO, AAS Nova (RSS) | arXiv astro-ph RSS |
| **Moon phases / Full moon dates** | USNO `/moon/phases/year` | Local: `ephem` or `skyfield` |
| **Solar eclipses** | USNO `/eclipses/solar/year` | NASA Eclipse site |
| **Lunar eclipses** | USNO `/eclipses/lunar/year` | NASA Eclipse site |
| **Meteor showers** | AMS calendar + RSS, IMO calendar | Local: peak dates are precomputed |
| **Aurora forecast** | NOAA SWPC (`/json/kp_index.json` + `/json/ovation_aurora_latest.json`) | SpaceWeatherLive |
| **Solar flares** | NOAA GOES X-ray + DONKI | Spaceweather.com RSS |
| **Planetary positions** | JPL Horizons API | Local: `skyfield` |
| **Planetary events (conjunctions, oppositions)** | In-The-Sky.org RSS | Local: `ephem` |
| **ISS tracking** | Open Notify | NASA ISS tracker |
| **Asteroid news** | JPL CAD API + NASA NeoWs | ESA Space Safety RSS |
| **Research papers** | arXiv API (astro-ph) | ADS (needs free key) |
| **Exoplanets** | NASA Exoplanet Archive TAP | SIMBAD |
| **Comet news** | In-The-Sky RSS + JPL SBDB | AMS + Universe Today |
| **Space weather events** | NOAA SWPC full suite | DONKI API |

---

## SECTION 5 — WHAT'S CONFIRMED WORKING vs. UNCERTAIN

### ✅ Confirmed free, stable, institutional
- All `api.nasa.gov` endpoints (DEMO_KEY works, registered key better)
- All `ssd-api.jpl.nasa.gov` endpoints (no key, no rate limit documented)
- All `aa.usno.navy.mil/api` endpoints (no key required)
- All `services.swpc.noaa.gov` JSON endpoints (public domain, no key)
- arXiv API (`export.arxiv.org/api`) — asks for 3s delay between requests, no key
- Open Notify (`api.open-notify.org`) — fully free, no key
- `api.sunrise-sunset.org` — free, no key
- SIMBAD/VizieR/NED TAP services — free, academic
- NASA Exoplanet Archive TAP — free, no key
- ephemeris.fyi REST API — free, no key (community-run)

### ⚠️ RSS feeds — confirmed URLs (working as of Sept 2026)
From the BruneiAstronomy page live render we confirmed these are actively publishing:
- astronomy.com/feed ✓ (publishing daily Sept 2026)
- earthsky.org/feed ✓ (publishing daily Sept 2026)  
- universetoday.com/feed ✓ (publishing daily Sept 2026)
- nasa.gov/news-releases/feed ✓ (publishing Sept 2026)
- esa.int RSS ✓ (publishing Sept 2026)
- nrao.edu/news/feed ✓ (publishing 2026)

### ⚠️ Uncertain / needs verification at build time
- Sky & Telescope RSS — had timeouts in some test environments (403 or timeout)
- Astronomy Now (UK) — reported 403 in some aggregators
- New Scientist — some articles paywalled despite RSS

### ❌ Do NOT use (confirmed problematic)
- **Brave Search API** — eliminated free tier Feb 2026, now requires prepaid credit card
- **Bing Search API** — shut down August 11, 2025
- **Google Custom Search** — being discontinued, legacy customers only
- **AstronomyAPI.com** — freemium, free tier is very limited (basic bodies only)

---

## SECTION 6 — RECOMMENDED BUILD ORDER

Based on reliability × coverage, implement in this order:

1. **NOAA SWPC JSON endpoints** — Real-time space weather, aurora, solar flares. Most structured, most stable, completely free, no key.

2. **USNO AA API** — Moon phases, eclipses, rise/set times. Authoritative US government data, no key.

3. **JPL APIs (CAD, SBDB, Horizons)** — Asteroid data, planetary ephemeris. No key, NASA institutional.

4. **NASA APOD + NeoWs + DONKI** (with free key) — Daily image, asteroids, solar events.

5. **RSS feeds (EarthSky, Universe Today, NASA, ESA, JWST, AAS Nova)** — These 6 alone cover 90% of news/discovery needs.

6. **arXiv API** — Research papers. Free, no key, massive coverage.

7. **Open Notify** — ISS position and crew. Trivial to add, nice feature.

8. **Local computation (skyfield/ephem)** — For precise celestial events without API dependency. Add as fallback.

9. **In-The-Sky.org RSS** — Daily events feed. Good for conjunction/opposition events.

10. **American Meteor Society** — For meteor shower coverage.

---

*This document should be the single source of truth before any coding decisions. Update when sources go offline or change terms.*
