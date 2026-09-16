"""Snapshot astro_events(year) to calendar/{year}.json for Cloudflare/Pages hosting."""
import json, sys
from pathlib import Path
sys.path.insert(0, ".")
from astro_search import tool_handler

year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
payload = json.loads(tool_handler("astro_events", {"year": year}))["json"]
Path("calendar").mkdir(exist_ok=True)
Path(f"calendar/{year}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
print(f"wrote calendar/{year}.json count={payload.get('count')}")
