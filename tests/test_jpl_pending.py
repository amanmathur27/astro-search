"""Regressions for JPL object selection and structured observer samples."""
from astro_search.sources import jpl



def test_named_object_not_prose_and_no_unrelated_calls(monkeypatch):
    calls = []
    class Response:
        ok = True
        def json(self):
            return {"object": {"fullname": "99942 Apophis", "des": "99942"}, "orbit": {"elements": []}}
    def get(url, **kwargs):
        calls.append((url, kwargs.get("params", {})))
        return Response()
    monkeypatch.setattr(jpl.requests, "get", get)
    rows = jpl.JPLSource().fetch("What is the orbit of asteroid Apophis?", intent="object_lookup")
    assert len(calls) == 1
    assert calls[0][0].endswith("/sbdb.api")
    assert calls[0][1]["sstr"].lower() == "apophis"
    assert rows[0]["extra"]["object"]["des"] == "99942"
    calls.clear()
    assert jpl.JPLSource().fetch("mass of Jupiter", intent="object_lookup") == []
    assert calls == []


def test_sbdb_error_payload_is_not_an_object(monkeypatch):
    class Response:
        ok = True
        def json(self):
            return {"code": "200", "message": "specified object was not found"}
    monkeypatch.setattr(jpl.requests, "get", lambda *a, **kw: Response())
    assert jpl.JPLSource().fetch("asteroid Apophis", intent="object_lookup") == []


HORIZONS_CSV = '''Target body name: Jupiter (599)
 Date__(UT)__HR:MN, , , R.A._(ICRF), DEC_(ICRF), Azi_(a-app), Elev_(a-app), APmag, S-brt,
*******************************************************************************
$$SOE
 2026-Dec-31 00:00, , , 120.5, -12.25, 95.1, 22.4, -2.5, n.a.,
 2026-Dec-31 01:00, , , 120.6, -12.24, 100.2, 30.1, n.a., n.a.,
$$EOE
'''


def test_horizons_structured_samples(monkeypatch):
    calls = []
    class Response:
        ok = True
        def json(self):
            return {"result": HORIZONS_CSV}
    def get(url, **kw):
        calls.append((url, kw["params"]))
        return Response()
    monkeypatch.setattr(jpl.requests, "get", get)
    rows = jpl.JPLSource().fetch("Jupiter position", lat=28, lon=77,
                                 now_utc="2026-12-31T12:00:00Z")
    assert len(calls) == 1
    assert calls[0][1]["CSV_FORMAT"] == "YES"
    samples = rows[0]["extra"]["samples"]
    assert samples[0] == {"time_utc": "2026-12-31T00:00:00Z", "ra_deg": 120.5,
                           "dec_deg": -12.25, "azimuth_deg": 95.1,
                           "elevation_deg": 22.4, "apparent_magnitude": -2.5}
    assert samples[1]["apparent_magnitude"] is None
    assert rows[0]["extra"]["sample_interval"] == "1h"
    assert "rise" not in rows[0]["extra"]


def test_horizons_rejects_errors_and_invalid_samples():
    import pytest
    for payload in ({"error": "bad request"}, {"result": "no ephemeris"},
                    {"result": HORIZONS_CSV.replace("120.5", "nan").replace("120.6", "inf")}):
        with pytest.raises(ValueError):
            jpl.parse_horizons(payload)
