"""Malformed calendar and completeness regressions."""
import pytest
from astro_search.calendar import validate_calendar_payload
from test_calendar import valid_payload



@pytest.mark.parametrize("payload", [None, [], {"results": None},
    {"results": [None], "count": 1}, {"results": [{"event_type": []}], "count": 1},
    {"results": [{"event_type": "moon_phase", "event_date_utc": []}], "count": 1}])
def test_malformed_calendar_is_rejected(payload):
    assert validate_calendar_payload(payload, 2026, 12)


def test_duplicates_and_phase_coverage():
    payload = valid_payload()
    payload["results"].append(dict(payload["results"][0]))
    payload["count"] += 1
    assert "duplicate event" in validate_calendar_payload(payload, 2026, 12)
    payload = valid_payload()
    for row in payload["results"]:
        if row["event_type"] == "moon_phase":
            row["extra"]["phase"] = "Full Moon"
    assert "incomplete four-phase lunar calendar" in validate_calendar_payload(payload, 2026, 12)


def test_date_only_eclipse_is_publishable():
    payload = valid_payload()
    row = next(r for r in payload["results"] if r["event_type"] == "solar_eclipse")
    row.update(date_only=True, precision="day", event_date=row.pop("event_date_utc")[:10])
    assert validate_calendar_payload(payload, 2026, 12) == []


@pytest.mark.parametrize("stamp", ["2026-01-01", "2026-01-01T99:00:00Z", "2026-01-01T12:00:00", 42])
def test_bad_event_instant(stamp):
    payload = valid_payload()
    payload["results"][0]["event_date_utc"] = stamp
    assert "missing/invalid event date" in validate_calendar_payload(payload, 2026, 12)
