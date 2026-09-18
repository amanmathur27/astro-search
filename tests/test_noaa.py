"""NOAA space-weather correctness: failures must stay unknown, never become 'quiet'."""
import pytest

from astro_search.sources import noaa
from astro_search.sources.noaa import (NOAASource, aurora_alert, kp_from_1m,
                                       g_scale_from_kp, _as_kp, _last_row)


@pytest.fixture
def noaa_source():
    return NOAASource()


def _patch_noaa(monkeypatch, json_map=None, text_map=None):
    def fake_json(path):
        if json_map and path in json_map:
            return json_map[path]
        raise ValueError(f"offline: {path}")

    def fake_text(path):
        if text_map and path in text_map:
            return text_map[path]
        raise ValueError(f"offline: {path}")

    monkeypatch.setattr(noaa, "_json", fake_json)
    monkeypatch.setattr(noaa, "_text", fake_text)


def test_all_requests_fail_never_claims_quiet(monkeypatch, noaa_source):
    _patch_noaa(monkeypatch)
    results = noaa_source.fetch("aurora forecast tonight")
    assert results, "one explicit unknown-data result must still be emitted"
    first = results[0]
    assert first["extra"]["kp_available"] is False
    assert first["extra"]["kp"] is None
    assert "unavailable" in first["title"].lower()
    assert "quiet" not in first["title"].lower()
    assert "unknown" in first["summary"].lower()


def test_measured_zero_is_not_treated_as_failure(monkeypatch, noaa_source):
    kp_payload = [{"time_tag": "2026-09-17 00:00:00", "estimated_kp": 0}]
    _patch_noaa(monkeypatch, {"/json/planetary_k_index_1m.json": kp_payload})
    results = noaa_source.fetch("aurora", now_utc="2026-09-17T00:30:00Z")
    first = results[0]
    assert first["extra"]["kp_available"] is True
    assert first["extra"]["kp"] == 0.0
    assert first["extra"]["bz"] is None
    assert "Bz unavailable" in first["extra"]["alert"]


def test_kp_seven_is_not_storm_scale_g0(monkeypatch, noaa_source):
    _patch_noaa(monkeypatch, {
        "/json/planetary_k_index_1m.json": [{"time_tag": "t", "estimated_kp": 7}],
        "/products/noaa-planetary-k-index.json":
            [["time_tag", "Kp", "a_running", "station_count"],
             ["2026-09-17 00:00:00", "7", "80", "8"]],
    })
    results = noaa_source.fetch("aurora", now_utc="2026-09-17T00:30:00Z")
    g_rows = [r for r in results if r["extra"].get("g_scale") is not None]
    assert g_rows, "list-format planetary K row must parse into a G-scale result"
    assert g_rows[0]["extra"]["g_scale"] == 3 and g_rows[0]["extra"]["kp"] == 7.0
    assert "G3" in g_rows[0]["title"]


def test_columnar_fields_data_payload_parses():
    payload = {"fields": ["time_tag", "kp_index"],
               "data": [["2026-09-17", 6], ["2026-09-18", 6.3]]}
    row = _last_row(payload)
    assert row == {"time_tag": "2026-09-18", "kp_index": 6.3}
    assert _as_kp(row["kp_index"]) == 6.3


def test_last_row_handles_header_list_and_data_wrappers():
    assert _last_row([["time_tag", "Kp", "a_running"],
                      ["2026-09-17", "7", "80"]]) == {
        "time_tag": "2026-09-17", "Kp": "7", "a_running": "80"}
    assert _last_row({"data": [{"kp_index": 4}, {"kp_index": 5}]}) == {"kp_index": 5}
    assert _last_row({"kp_index": 6}) == {"kp_index": 6}
    assert _last_row([]) == {} and _last_row("junk") == {}


def test_kp_helpers_unit():
    assert _as_kp("4.33") == 4.33
    assert _as_kp(0) == 0.0          # zero is a measurement
    assert _as_kp(None) is None
    assert _as_kp("") is None
    assert _as_kp(True) is None
    assert _as_kp("n/a") is None
    assert kp_from_1m([]) == (None, {})
    assert kp_from_1m("junk") == (None, {})
    assert kp_from_1m([{"estimated_kp": None}, {"estimated_kp": 3.0}])[0] == 3.0
    assert g_scale_from_kp(None) is None
    assert g_scale_from_kp(0) == 0
    assert g_scale_from_kp(5) == 1
    assert g_scale_from_kp(9) == 5
    assert g_scale_from_kp(9.5) is None
    assert aurora_alert(None, 0.0).startswith("Kp unavailable")


def test_junk_kp_values_are_not_zero(monkeypatch, noaa_source):
    _patch_noaa(monkeypatch, {
        "/json/planetary_k_index_1m.json": [{"estimated_kp": None}, {"estimated_kp": "n/a"}],
    })
    results = noaa_source.fetch("aurora")
    assert results[0]["extra"]["kp_available"] is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 10, "NaN", True])
def test_invalid_measurement_range(value):
    assert _as_kp(value) is None
    assert g_scale_from_kp(value) is None


def test_stale_kp_and_channel_selection(monkeypatch):
    _patch_noaa(monkeypatch, {
        "/json/planetary_k_index_1m.json": [{"estimated_kp": 7, "time_tag": "2026-09-16T00:00:00Z"}],
        "/json/goes/primary/xrays-7-day.json": [
            {"energy": "0.1-0.8nm", "flux": 2e-6, "time_tag": "2026-09-17T00:00:00Z"},
            {"energy": "0.05-0.4nm", "flux": 1e-4, "time_tag": "2026-09-17T00:00:00Z"}],
    })
    rows = NOAASource().fetch("aurora", now_utc="2026-09-17T00:30:00Z")
    assert rows[0]["extra"]["stale"] is True
    assert rows[0]["extra"]["kp"] is None
    xray = next(r for r in rows if "xray_flux" in r["extra"])
    assert xray["extra"]["flare_class"] == "C"
    assert xray["extra"]["energy"] == "0.1-0.8nm"


@pytest.mark.parametrize("payload", [
    {"fields": ["Kp"], "data": [None]},
    {"fields": [["Kp"]], "data": [[7]]},
    [["Kp"]], [["Kp", "Kp"], [7, 8]],
])
def test_malformed_tables(payload):
    assert _last_row(payload) == {}

