import json
from pathlib import Path
from astro_search.sources.local_sky import LocalSkySource, _ephem_moon
from astro_search.deduplicator import deduplicate
from astro_search.normalizer import normalize
from datetime import datetime, timezone

META = {"name": "T", "source_type": "computed", "authority": 2}

def test_local_sky_moon():
    info = _ephem_moon(datetime(2026, 9, 16, tzinfo=timezone.utc))
    assert 0 <= info["illumination_pct"] <= 100
    assert info["phase"]  # named phase
    r = LocalSkySource().fetch("phase of moon today")
    assert len(r) == 1 and r[0]["event_date_utc"] and r[0]["extra"]["computed"] is True

def test_meteor_calendar_complete():
    from astro_search.showers import load_showers
    data = load_showers(2026)  # exact IMO file
    names = {m["name"] for m in data}
    for need in ["Quadrantids", "Lyrids", "Eta Aquariids", "Southern Delta Aquariids", "Perseids",
                 "Draconids", "Orionids", "Southern Taurids", "Northern Taurids", "Leonids",
                 "Geminids", "Ursids"]:
        assert need in names, f"missing {need}"
    assert all(m.get("peak", "").endswith("Z") for m in data)

def test_dedup_keeps_distinct_dated_events():
    a = normalize({"title": "Full Moon — 9/26/2026", "url": "https://aa.usno.navy.mil/",
                   "event_type": "moon_phase", "event_date_utc": "2026-09-26T16:49:00Z"}, META)
    b = normalize({"title": "New Moon — 10/10/2026", "url": "https://aa.usno.navy.mil/",
                   "event_type": "moon_phase", "event_date_utc": "2026-10-10T15:50:00Z"}, META)
    c = normalize({"title": "Full Moon — 9/26/2026 repost", "url": "https://aa.usno.navy.mil/",
                   "event_type": "moon_phase", "event_date_utc": "2026-09-26T16:49:00Z"}, META)
    out = deduplicate([a, b, c])
    assert len(out) == 2  # true duplicate collapsed, distinct dates kept

def test_meteor_templated_year():
    from astro_search.showers import load_showers
    data = load_showers(2027)  # no exact file -> templated base
    assert len(data) == 12 and all(m["peak"].startswith("2027-") and m["exact"] is False for m in data)

def test_dedup_keeps_monthly_moons():
    moons = [normalize({"title": f"Full Moon — {m}/1/2026", "url": "https://aa.usno.navy.mil/",
                        "event_type": "moon_phase", "event_date_utc": f"2026-{m:02d}-01T10:00:00Z"}, META)
             for m in (1, 2, 3)]
    assert len(deduplicate(moons)) == 3

def test_gnews_gating():
    from astro_search.sources.gnews import has_recency, edition_params
    from astro_search.core import AstroSearch
    assert has_recency("major discovery today") and has_recency("breaking: supernova just announced")
    assert not has_recency("what is a pulsar") and not has_recency("next lunar eclipse")
    assert edition_params(None) == ("en-US", "US", "US:en")
    assert edition_params("IN") == ("en-IN", "IN", "IN:en")
    assert edition_params("IN:en") == ("en-IN", "IN", "IN:en")
    eng = AstroSearch()
    plain = [s.name for s in eng._select("recent_news", [], "all")]
    assert "Google News" not in plain  # default-off: no noise
    gated = [s.name for s in eng._select("recent_news", [], "all", allow_gnews=True)]
    assert "Google News" in gated
    # concept queries never admit it even when forced path differs: intent mismatch
    assert "Google News" not in [s.name for s in eng._select("concept_explanation", [], "all", allow_gnews=True)]
