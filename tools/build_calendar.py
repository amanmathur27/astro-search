"""Snapshot astro_events(years) to calendar/{year}.json for plain-HTTPS agent reads."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, ".")
from astro_search import tool_handler

now_year = datetime.now(timezone.utc).year
args = [a for a in sys.argv[1:] if a.strip().isdigit()]
years = [int(a) for a in args] or [now_year, now_year + 1]
Path("calendar").mkdir(exist_ok=True)
for year in years:
    payload = json.loads(tool_handler("astro_events", {"year": year}))["json"]
    Path(f"calendar/{year}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote calendar/{year}.json count={payload.get('count')}")
