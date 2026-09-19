"""Gemini/OpenAI-compatible tool declarations + universal handler."""
from __future__ import annotations
import json

TOOL_DECLARATIONS = [
    {"name": "astro_search",
     "description": ("Search astronomy/astrophysics/space science: news, discoveries, eclipses, meteor showers, "
                     "moon phases, alignments, auroras, flares, missions, papers. Explicit ATel/transient alert queries search the current Top ATels feed only (preliminary, not peer-reviewed; not a complete archive). Returns UTC dates + visibility. Includes direct answers (Earth-referenced solar-system distances, calendar dates, verified mission facts) when supported; abstains otherwise."),
     "parameters": {"type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural query, e.g. next lunar eclipse, Perseids 2026 peak, aurora tonight, Kp now"},
                        "category": {"type": "string", "enum": ["news", "discoveries", "events", "papers", "space_weather", "all"]},
                        "max_results": {"type": "integer", "description": "Default 8, max 20"},
                        "mode": {"type": "string", "enum": ["standard", "evidence"], "description": "Default standard. 'evidence' returns structured verification claims and citations for AI grounding."},
                        "since_date": {"type": "string", "description": "Filter results published on or after YYYY-MM-DD for delta updates."},
                        "trends": {"type": "boolean", "description": "Gap-analysis mode: include a 7-day Google News article sample, not measured topic volume. Default false."},
                        "edition": {"type": "string", "description": "News edition for breaking coverage, e.g. US, IN, UK or IN:en. Default US."},
                        "lat": {"type": "number"}, "lon": {"type": "number"},
                        "timezone": {"type": "string", "description": "IANA tz, default UTC"},
                        "now_utc": {"type": "string", "description": "ISO now UTC; omit for server time"}},
                    "required": ["query"]}},
    {"name": "astro_compare",
     "description": "Physical comparison matrix of astronomical bodies (planets, moons, stars) containing radius, mass, temperature, gravity, and atmosphere.",
     "parameters": {"type": "object",
                    "properties": {
                        "objects": {"type": "array", "items": {"type": "string"}, "description": "List of object names e.g. ['Europa', 'Titan']"}},
                    "required": ["objects"]}},
    {"name": "astro_fetch",
     "description": "Fetch full text of a URL from astro_search results. Cleaned plain text.",
     "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "astro_events",
     "description": "Celestial events for a year: moon phases, eclipses, shower peaks, seasons.",
     "parameters": {"type": "object", "properties": {
         "year": {"type": "integer", "minimum": 1900, "maximum": 2100},
         "lat": {"type": "number", "minimum": -90, "maximum": 90},
         "lon": {"type": "number", "minimum": -180, "maximum": 180},
         "timezone": {"type": "string", "description": "IANA timezone; coordinates must be supplied together"},
         "now_utc": {"type": "string", "description": "Timezone-aware reference instant"}}, "required": []}},
    {"name": "astro_papers",
     "description": "Astrophysics papers via arXiv + ADS.",
     "parameters": {"type": "object",
                    "properties": {"query": {"type": "string"},
                                   "topic": {"type": "string", "enum": ["astrophysics", "cosmology", "galaxies", "high_energy", "solar", "planets", "instrumentation"]},
                                   "max_results": {"type": "integer"}},
                    "required": ["query"]}},
]

_engine = None

def _engine_get():
    global _engine
    if _engine is None:
        from .core import AstroSearch
        _engine = AstroSearch()
    return _engine


def tool_handler(tool_name: str, tool_args: dict) -> str:
    try:
        if not isinstance(tool_args, dict):
            raise ValueError("tool_args must be an object")
        eng = _engine_get()
        if tool_name == "astro_search":
            search_kwargs = {
                "query": tool_args.get("query", ""),
                "category": tool_args.get("category", "all"),
                "max_results": tool_args.get("max_results", 8),
                "lat": tool_args.get("lat"),
                "lon": tool_args.get("lon"),
                "tz": tool_args.get("timezone", "UTC"),
                "now_utc": tool_args.get("now_utc"),
                "trends": tool_args.get("trends", False),
                "edition": tool_args.get("edition"),
            }
            if "mode" in tool_args:
                search_kwargs["mode"] = tool_args["mode"]
            if "since_date" in tool_args:
                search_kwargs["since_date"] = tool_args["since_date"]
            out = eng.search(**search_kwargs)
        elif tool_name == "astro_compare":
            out = eng.compare_objects(tool_args.get("objects", []))
            return json.dumps({"json": out, "markdown": out.get("markdown_table", "")}, ensure_ascii=False, indent=2)
        elif tool_name == "astro_fetch":
            from .sources.fetch import fetch_article
            out = fetch_article(tool_args.get("url", ""))
            return json.dumps({"json": out, "markdown": (out.get("title", "") + "\n\n" + out.get("text", "")[:4000])}, ensure_ascii=False, indent=2)
        elif tool_name == "astro_events":
            out = eng.get_celestial_events(year=tool_args.get("year"),
                                          lat=tool_args.get("lat"), lon=tool_args.get("lon"),
                                          tz=tool_args.get("timezone", "UTC"), now_utc=tool_args.get("now_utc"))
        elif tool_name == "astro_papers":
            out = eng.search_papers(query=tool_args.get("query", ""),
                                    topic=tool_args.get("topic", "astrophysics"),
                                    max_results=tool_args.get("max_results", 5))
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        return json.dumps({"json": out, "markdown": out.get("markdown", "")}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)[:500]})
