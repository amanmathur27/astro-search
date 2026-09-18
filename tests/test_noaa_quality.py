"""Current NOAA products must have eligible timestamps and plausible measurements."""
import pytest
from astro_search.sources import noaa
from test_noaa import _patch_noaa

NOW = "2026-09-17T12:00:00Z"


def test_unsorted_observations(monkeypatch):
    _patch_noaa(monkeypatch, {
        "/json/planetary_k_index_1m.json": [
            {"time_tag": "2026-09-17T11:59:00Z", "estimated_kp": 7},
            {"time_tag": "2026-09-17T11:00:00Z", "estimated_kp": 2},
            {"time_tag": "2026-09-18T11:00:00Z", "estimated_kp": 9}],
        "/json/solar-wind/mag-7-day.json": [
            {"time_tag": "2026-09-17T11:59:00Z", "bz_gsm": -8},
            {"time_tag": "2026-09-17T11:00:00Z", "bz_gsm": 1}],
        "/products/noaa-planetary-k-index.json": [
            ["time_tag", "Kp"], ["2026-09-17T11:00:00Z", 7],
            ["2026-09-17T09:00:00Z", 2]],
    })
    rows = noaa.NOAASource().fetch("aurora", now_utc=NOW)
    assert rows[0]["extra"]["kp"] == 7
    assert rows[0]["extra"]["bz"] == -8
    assert next(r for r in rows if "g_scale" in r["extra"])["extra"]["g_scale"] == 3


@pytest.mark.parametrize("stamp", [None, "2026-09-01T00:00:00Z", "2026-09-18T00:00:00Z", "2026-09-17"])
def test_ineligible_alerts(monkeypatch, stamp):
    _patch_noaa(monkeypatch, {"/products/alerts.json": [{"message": "Fixture alert", "issue_datetime": stamp}]})
    rows = noaa.NOAASource().fetch("alerts", now_utc=NOW)
    assert not any(r["title"] == "Fixture alert" for r in rows)


@pytest.mark.parametrize("issued", ["", ":Issued: 2026 Sep 01 0030 UTC", ":Issued: 2026 Sep 18 0030 UTC"])
def test_ineligible_forecasts(monkeypatch, issued):
    _patch_noaa(monkeypatch, text_map={"/text/3-day-forecast.txt": issued + "\nNOAA forecast text"})
    rows = noaa.NOAASource().fetch("forecast", now_utc=NOW)
    assert not any("forecast" in r["extra"] for r in rows)


def test_fresh_products(monkeypatch):
    _patch_noaa(monkeypatch, {"/products/alerts.json": [{"message": "Fixture alert", "issue_datetime": "2026-09-17T10:00:00Z"}]},
                {"/text/3-day-forecast.txt": ":Issued: 2026 Sep 17 0030 UTC\nNOAA forecast text"})
    rows = noaa.NOAASource().fetch("forecast", now_utc=NOW)
    assert any(r["title"] == "Fixture alert" for r in rows)
    forecast = next(r for r in rows if "forecast" in r["extra"])
    assert forecast["published"] == "2026-09-17T00:30:00Z"


@pytest.mark.parametrize("flux", [0, -1, 999, float("nan"), float("inf"), True])
def test_rejected_flux(monkeypatch, flux):
    _patch_noaa(monkeypatch, {"/json/goes/primary/xrays-7-day.json": [
        {"energy": "0.1-0.8nm", "flux": flux, "time_tag": "2026-09-17T11:59:00Z"}]})
    rows = noaa.NOAASource().fetch("solar", now_utc=NOW)
    assert not any("xray_flux" in r["extra"] for r in rows)
