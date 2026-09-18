"""Meteor shower data: per-year exact overrides, else templated base.

- astro_search/data/meteor_showers_{year}.json — exact peak datetimes + ZHR transcribed
  once a year from the IMO shower calendar (https://www.imo.net/members/imo_showers/calendar/).
  This is the deliberate choice over live-scraping IMO: their calendar is HTML/PDF
  with no API; parsing it per-query is fragile and slow. One human-verified ingest
  per year (~10 min) beats a parser that breaks silently on redesign.
- astro_search/data/meteor_showers_base.json — recurring month/day/time + typical ZHR
  used when no exact file exists for the requested year (peak accurate to ~±1 day).

Both files ship inside the package (setup.py package_data) so pip-installed copies
work without the repo checkout.
"""
from __future__ import annotations
import json
from pathlib import Path

# Package-relative: works for editable installs AND pip-installed wheels.
_HERE = Path(__file__).resolve().parent / "data"


def load_showers(year: int) -> list[dict]:
    exact = _HERE / f"meteor_showers_{year}.json"
    if exact.is_file():
        showers = json.loads(exact.read_text())
        for m in showers:
            m.setdefault("exact", True)
        return showers
    base = json.loads((_HERE / "meteor_showers_base.json").read_text())
    out = []
    for m in base:
        out.append({
            "name": m["name"],
            "peak": f"{year}-{m['month']:02d}-{m['day']:02d}T{m['time']}:00Z",
            "zhr": m.get("zhr"), "hemisphere": m.get("hemisphere"),
            "radiant": m.get("radiant"), "parent": m.get("parent"),
            "exact": False,
        })
    return out
