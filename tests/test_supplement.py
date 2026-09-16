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

def test_entity_gate_filters_and_backstops():
    from astro_search.core import AstroSearch
    eng = AstroSearch()
    pool = [normalize({"title": t, "summary": s, "url": f"https://x/{i}"},
                       {"name": "S", "authority": 2})
            for i, (t, s) in enumerate([
                ("Roman lifts off survey infrared sky", "Nancy Grace Roman Space Telescope launch"),
                ("Webb panorama star formation", "James Webb Space Telescope image"),
                ("Educator magnetism guide", "students discover magnetic fields"),
                ("Moon crater found", "lunar orbiter spots crater"),
                ("Starlink launch mission", "SpaceX Falcon booster flight")])]
    kept, back = eng._entity_gate(pool, ["nancy grace"], 8)
    assert not back and len(kept) == 1 and "Roman" in kept[0]["title"]
    kept, back = eng._entity_gate(pool, ["gaganyaan"], 8)
    assert back and len(kept) == 3  # empty gate -> top-3 backstop, flagged

def test_gnews_gating():
    from astro_search.sources.gnews import has_recency, recency_window_days, edition_params
    from astro_search.core import AstroSearch
    from astro_search.core import AstroSearch
    assert has_recency("major discovery today") and has_recency("breaking: supernova just announced")
    assert has_recency("top developments this week") and has_recency("launched 3 hours ago")
    assert not has_recency("what is a pulsar") and not has_recency("next lunar eclipse")
    assert recency_window_days("developments this week", False) == 7
    assert recency_window_days("discovery today", False) == 1
    assert recency_window_days("anything", True) == 7
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

