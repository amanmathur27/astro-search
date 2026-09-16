"""Gemini/OpenAI-compatible tool declarations + universal handler."""
from __future__ import annotations
import json

TOOL_DECLARATIONS = [
    {"name": "astro_search",
     "description": ("Search astronomy/astrophysics/space science: news, discoveries, eclipses, meteor showers, "
                     "moon phases, alignments, auroras, flares, missions, papers. Returns UTC dates + visibility."),
     "parameters": {"type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural query, e.g. next lunar eclipse, Perseids 2026 peak, aurora tonight, Kp now"},
                        "category": {"type": "string", "enum": ["news", "discoveries", "events", "papers", "space_weather", "all"]},
                        "max_results": {"type": "integer", "description": "Default 8, max 20"},
                        "trends": {"type": "boolean", "description": "Gap-analysis mode: include 7-day Google News topic volume. Default false."},
                        "edition": {"type": "string", "description": "News edition for breaking coverage, e.g. US, IN, UK or IN:en. Default US."},
                        "lat": {"type": "number"}, "lon": {"type": "number"},
                        "timezone": {"type": "string", "description": "IANA tz, default UTC"},
                        "now_utc": {"type": "string", "description": "ISO now UTC; omit for server time"}},
                    "required": ["query"]}},
    {"name": "astro_fetch",
     "description": "Fetch full text of a URL from astro_search results. Cleaned plain text.",
     "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
    {"name": "astro_events",
     "description": "Celestial events for a year: moon phases, eclipses, shower peaks, seasons.",
     "parameters": {"type": "object", "properties": {"year": {"type": "integer"}}, "required": []}},
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
        eng = _engine_get()
        if tool_name == "astro_search":
            out = eng.search(query=tool_args.get("query", ""), category=tool_args.get("category", "all"),
                             max_results=min(int(tool_args.get("max_results", 8)), 20),
                             lat=tool_args.get("lat"), lon=tool_args.get("lon"),
                             tz=tool_args.get("timezone", "UTC"), now_utc=tool_args.get("now_utc"),
                             trends=bool(tool_args.get("trends", False)),
                             edition=tool_args.get("edition"))
        elif tool_name == "astro_fetch":
            from .sources.fetch import fetch_article
            out = fetch_article(tool_args.get("url", ""))
            return json.dumps({"json": out, "markdown": (out.get("title", "") + "\n\n" + out.get("text", "")[:4000])}, ensure_ascii=False, indent=2)
        elif tool_name == "astro_events":
            out = eng.get_celestial_events(year=tool_args.get("year"))
        elif tool_name == "astro_papers":
            out = eng.search(query=tool_args.get("query", ""), category="papers",
                             max_results=int(tool_args.get("max_results", 5)))
            # boost papers-only: filter client-side already by intent routing; keep as-is
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        return json.dumps({"json": out, "markdown": out.get("markdown", "")}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)[:500]})
