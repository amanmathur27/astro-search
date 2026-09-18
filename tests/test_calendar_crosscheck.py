"""Cross-check published USNO lunar events against optional PyEphem computation."""
from datetime import timedelta, timezone
import json
from pathlib import Path
import pytest
from dateutil.parser import isoparse
from astro_search.calendar import validate_calendar_payload
from astro_search.showers import load_showers

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('year,count', [(2026, 70), (2027, 69)])
def test_regenerated_calendar_contract(year, count):
    payload = json.loads((ROOT / 'calendar' / f'{year}.json').read_text(encoding='utf-8'))
    assert payload['schema_version'] == 2
    assert payload['count'] == count
    assert validate_calendar_payload(payload, year, len(load_showers(year))) == []


@pytest.mark.parametrize('year', [2026, 2027])
def test_lunar_dates_against_independent_computation(year):
    ephem = pytest.importorskip('ephem')
    functions = {'New Moon': ephem.next_new_moon,
                 'First Quarter': ephem.next_first_quarter_moon,
                 'Full Moon': ephem.next_full_moon,
                 'Last Quarter': ephem.next_last_quarter_moon}
    payload = json.loads((ROOT / 'calendar' / f'{year}.json').read_text(encoding='utf-8'))
    checked = 0
    for row in payload['results']:
        if row['event_type'] != 'moon_phase':
            continue
        observed = isoparse(row['event_date_utc'])
        # Find the same phase starting a day earlier, not the next lunation.
        start = ephem.Date((observed - timedelta(days=1)).replace(tzinfo=None))
        predicted = functions[row['extra']['phase']](start).datetime().replace(tzinfo=timezone.utc)
        # USNO dates are minute-rounded; allow model and rounding differences.
        assert abs((observed - predicted).total_seconds()) <= 120, row['title']
        checked += 1
    assert 48 <= checked <= 52
