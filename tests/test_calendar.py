"""Calendar contract and atomic publication tests."""
import json
from datetime import datetime, timedelta, timezone
import pytest
from astro_search.calendar import partition_events, validate_calendar_payload
from astro_search.normalizer import normalize
from tools.build_calendar import write_calendar


def valid_payload():
    rows = []
    for kind, count in (("moon_phase", 50), ("season", 4), ("solar_eclipse", 2), ("meteor_shower", 12)):
        for i in range(count):
            stamp = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i * 7)).isoformat().replace("+00:00", "Z")
            extra = {}
            if kind == "moon_phase":
                extra["phase"] = ("New Moon", "First Quarter", "Full Moon", "Last Quarter")[i % 4]
            if kind == "season":
                stamp = f"2026-{(i + 1) * 3:02d}-20T12:00:00Z"
                extra["phenom"] = "Equinox" if i % 2 == 0 else "Solstice"
            rows.append({"title": f"{kind} {i}", "event_type": kind, "event_date_utc": stamp, "extra": extra})
    rows.sort(key=lambda r: r["event_date_utc"])
    return {"results": rows, "count": len(rows)}


def test_valid_publication(tmp_path):
    payload = valid_payload()
    assert validate_calendar_payload(payload, 2026, 12) == []
    path = tmp_path / "calendar.json"
    write_calendar(path, payload, 2026)
    assert json.loads(path.read_text()) == payload
    assert not list(tmp_path.glob("*.tmp"))


def test_invalid_publication_preserves_existing(tmp_path):
    path = tmp_path / "calendar.json"
    path.write_text("original")
    with pytest.raises(ValueError):
        write_calendar(path, {"results": [], "count": 0}, 2026)
    assert path.read_text() == "original"


def test_date_only_not_midnight():
    row = normalize({"event_type": "solar_eclipse", "event_date": "2026-08-12",
                     "date_only": True, "precision": "day"}, {})
    assert row["event_date"] == "2026-08-12" and row["event_date_utc"] is None


def test_partition_excludes_snapshots_and_wrong_year():
    rows = [
        {"event_type": "moon_phase", "event_date_utc": "2026-02-01T00:00:00Z"},
        {"event_type": "moon_phase", "event_date_utc": "2027-01-01T00:00:00Z"},
        {"event_type": "aurora", "published": "2026-02-01T00:00:00Z"},
        {"event_type": "lunar_eclipse", "url": "https://eclipse.gsfc.nasa.gov/"},
        {"event_type": "moon_phase", "event_date_utc": "2026-01-01T00:00:00Z", "extra": {"computed": True}},
        {"event_type": "solar_eclipse", "event_date": "2026-01-15", "date_only": True},
    ]
    annual, snapshots, references = partition_events(rows, 2026)
    assert len(annual) == 2 and len(snapshots) == 2 and len(references) == 1
    assert annual[0]["event_date"] == "2026-01-15"


def test_wrong_year_and_unsorted_rejected():
    payload = valid_payload()
    payload["results"][0]["event_date_utc"] = "2027-01-01T00:00:00Z"
    errors = validate_calendar_payload(payload, 2026, 12)
    assert "out-of-year event" in errors and "events not chronological" in errors
