"""Offline regression coverage for local Moon phase classification."""
from datetime import datetime, timedelta, timezone

import pytest

from astro_search.sources import local_sky


@pytest.mark.parametrize("waxing,prefix,quarter", [
    (True, "Waxing", "First Quarter"),
    (False, "Waning", "Last Quarter"),
])
@pytest.mark.parametrize("illum,kind", [
    (0, "New Moon"), (1.99, "New Moon"), (2, "Crescent"),
    (25, "Crescent"), (47.99, "Crescent"), (48, "quarter"),
    (50, "quarter"), (52, "quarter"), (52.01, "Gibbous"),
    (75, "Gibbous"), (98, "Gibbous"), (98.01, "Full Moon"),
    (100, "Full Moon"),
])
def test_phase_name_boundaries(illum, kind, waxing, prefix, quarter):
    expected = quarter if kind == "quarter" else (
        f"{prefix} {kind}" if kind in ("Crescent", "Gibbous") else kind)
    assert local_sky._phase_name(illum, waxing) == expected


@pytest.mark.parametrize("day,phase,waxing,illum", [
    (2, "Waning Gibbous", False, 75.3),
    (8, "Waning Crescent", False, 12.4),
    (16, "Waxing Crescent", True, 24.0),
    (22, "Waxing Gibbous", True, 78.3),
])
def test_september_moon_regressions(day, phase, waxing, illum):
    pytest.importorskip("ephem")
    info = local_sky._ephem_moon(datetime(2026, 9, day, tzinfo=timezone.utc))
    assert info["phase"] == phase
    assert info["waxing"] is waxing
    assert info["illumination_pct"] == pytest.approx(illum, abs=0.2)
    assert info["next_full"] and info["next_new"]


@pytest.mark.parametrize("event,name,before,after", [
    ("next_new_moon", "New Moon", False, True),
    ("next_first_quarter_moon", "First Quarter", True, True),
    ("next_full_moon", "Full Moon", True, False),
    ("next_last_quarter_moon", "Last Quarter", False, False),
])
def test_phase_events_and_direction(event, name, before, after):
    ephem = pytest.importorskip("ephem")
    # Event times provide an independent oracle, not an average half-cycle.
    instant = getattr(ephem, event)("2026/9/1").datetime().replace(tzinfo=timezone.utc)
    assert local_sky._ephem_moon(instant)["phase"] == name
    assert local_sky._ephem_moon(instant - timedelta(hours=6))["waxing"] is before
    assert local_sky._ephem_moon(instant + timedelta(hours=6))["waxing"] is after


def test_fetch_preserves_correct_phase_in_normalized_result(monkeypatch):
    pytest.importorskip("ephem")
    monkeypatch.setattr(local_sky, "_skyfield_moon", lambda date: None)
    results = local_sky.LocalSkySource().fetch("moon phase", date="2026-09-02")
    assert len(results) == 1
    result = results[0]
    assert "Waning Gibbous" in result["title"]
    assert "Waning Gibbous" in result["summary"]
    assert result["event_date_utc"] == "2026-09-02T00:00:00Z"
    assert result["extra"]["computed"] is True
    assert result["extra"]["local_verify"]["waxing"] is False
