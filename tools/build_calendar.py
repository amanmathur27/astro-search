"""Validate every requested calendar before atomically replacing individual files."""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from astro_search.core import AstroSearch
from astro_search.calendar import validate_calendar_payload
from astro_search.showers import load_showers


def write_calendar(path, payload, year):
    errors = validate_calendar_payload(payload, year, len(load_showers(year)))
    if errors:
        raise ValueError("; ".join(errors))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", type=int)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "calendar")
    args = parser.parse_args(argv)
    current = datetime.now(timezone.utc).year
    years = args.years or [current, current + 1]
    engine = AstroSearch()
    pending = []
    for year in years:
        if not 1900 <= year <= 2100:
            parser.error("Supported calendar years: 1900–2100")
        payload = engine.get_celestial_events(year)
        errors = validate_calendar_payload(payload, year, len(load_showers(year)))
        if errors:
            raise ValueError(f"Calendar {year} not published: {'; '.join(errors)}")
        pending.append((year, payload))
    for year, payload in pending:
        write_calendar(args.output / f"{year}.json", payload, year)
        print(f"Published {year}: {payload['count']} annual events")


if __name__ == "__main__":
    main()
