"""AstroSearch orchestrator: intent → route → safe fan-out → dedup/rank → cache → markdown."""
from __future__ import annotations
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from .intent import classify
from .timeparse import now_utc_iso, today_label, resolve_dates
from .deduplicator import deduplicate
from .ranker import rank
from .cache import TTLCache
from .cache_sqlite import SQLiteCache

logger = logging.getLogger("astro_search")

FALLBACK_CHAINS = {"USNO": "Local Sky", "NASA": "rss", "EarthSky": "rss",
                   "JPL": "nasa", "NOAA SWPC": "rss", "arXiv": "rss"}
PAYWALLED = ["New Scientist"]
ASTRONOMY_THRESHOLD = 0.1


def _build_sources():
    from .sources.rss import RSS_FEEDS, RSSSource
    from .sources.usno import USNOSource
    from .sources.noaa import NOAASource
    from .sources.nasa import NASASource
    from .sources.jpl import JPLSource
    from .sources.arxiv import ArxivSource
    from .sources.ads import ADSSource
    from .sources.tap import ExoplanetSource
    from .sources.iss import ISSSource
    from .sources.local_sky import LocalSkySource
    from .sources.sky_fallback import FallbackSkySource
    srcs = [RSSSource(c) for c in RSS_FEEDS]
    srcs += [USNOSource(), NOAASource(), NASASource(), JPLSource(),
             ArxivSource(), ADSSource(), ExoplanetSource(), ISSSource(), LocalSkySource(), FallbackSkySource()]
    return srcs


class AstroSearch:
    def __init__(self):
        self.mem = TTLCache(15)
        try:
            self.disk = SQLiteCache()
        except Exception:
            self.disk = None
        self._sources = None

    @property
    def sources(self):
        if self._sources is None:
            self._sources = _build_sources()
        return self._sources

    def _select(self, intent: str, entities: list[str], category: str) -> list:
        from .intent import KNOWN_ENTITIES
        # map entity values -> group keys (e.g. "aurora" -> "solar")
        val_to_group: dict[str, str] = {}
        for g, vals in KNOWN_ENTITIES.items():
            for v in vals:
                val_to_group[v] = g
        qgroups = {val_to_group.get(e, e) for e in (entities or [])} | set(entities or [])
        cands = []
        for s in self.sources:
            if intent not in getattr(s, "intents", []):
                continue
            ents = getattr(s, "entities", ["*"])
            if ents != ["*"] and entities and not (qgroups & set(ents)):
                # allow broad RSS through; skip narrow mismatches
                if getattr(s, "source_type", "") != "rss":
                    continue
            if category not in ("all", None):
                pass  # category filters at rank stage via summary; keep routing by intent
            if isinstance(s, type) or (hasattr(s, "is_available") and not s.is_available()):
                try:
                    if not s.is_available():
                        continue
                except Exception:
                    pass
            cands.append(s)
        cands.sort(key=lambda s: getattr(s, "authority", 2), reverse=True)
        selected = cands[:5]
        # fallback guarantee: if a selected source has a named fallback not yet selected, append it
        names = {getattr(s, "name", "") for s in selected}
        for s in selected:
            fb = FALLBACK_CHAINS.get(getattr(s, "name", ""))
            if fb and fb not in names:
                for cand in self.sources:
                    if getattr(cand, "name", "") == fb:
                        selected.append(cand)
                        names.add(fb)
                        break
        return selected

    def _safe_fetch(self, source, query: str, **kw) -> list[dict]:
        try:
            res = source.fetch(query, **kw)
            return res or []
        except Exception as e:
            logger.warning(f"{getattr(source, 'name', '?')}: {e}")
            return []

    def search(self, query: str = "", category: str = "all", max_results: int = 8,
               lat: float | None = None, lon: float | None = None,
               tz: str | int = "UTC", now_utc: str | None = None,
               year: int | None = None) -> dict:
        now_iso = now_utc or now_utc_iso()
        if not (query or "").strip():
            return self.get_celestial_events(year=year, lat=lat, lon=lon)
        intent, entities = classify(query)
        dates = resolve_dates(query)
        key = (query, category, max_results)
        cached = self.mem.get(key)
        if cached:
            cached = dict(cached)
            cached["cached"] = True
            return cached
        if self.disk:
            ttl = 900 if intent in ("current_phenomenon", "recent_news") else 86400
            d = self.disk.get(json.dumps(key, sort_keys=True, default=str), ttl)
            if d:
                d["cached"] = True
                self.mem.set(key, d)
                return d
        sources = self._select(intent, entities, category)
        kw = {"max_results": max_results, "intent": intent, "category": category,
              "lat": lat, "lon": lon, "tz": tz, "year": year or datetime.now(timezone.utc).year,
              "date": dates.get("date_min"), "now_utc": now_iso}
        # location-aware: guarantee Twilight Fallback when lat/lon supplied
        if lat is not None and lon is not None and not any(getattr(s, "name", "") == "Twilight Fallback" for s in sources):
            for cand in self.sources:
                if getattr(cand, "name", "") == "Twilight Fallback":
                    sources.append(cand)
                    break
        # moon-aware: guarantee USNO or Local Sky when query mentions moon
        if "moon" in query.lower() and not any(getattr(s, "name", "") in ("USNO", "Local Sky") for s in sources):
            for want in ("USNO", "Local Sky"):
                for cand in self.sources:
                    if getattr(cand, "name", "") == want and intent in getattr(cand, "intents", []):
                        sources.append(cand)
                        break
                if any(getattr(s, "name", "") in ("USNO", "Local Sky") for s in sources):
                    break
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=5) as ex:
            futs = [ex.submit(self._safe_fetch, s, query, **kw) for s in sources]
            for f in futs:
                try:
                    results.extend(f.result() or [])
                except Exception:
                    continue
        # quality filters: paywall flag, stale pinned (>90d unless historical)
        filt = []
        for r in results:
            if r.get("source") in PAYWALLED:
                r.setdefault("extra", {})["paywalled"] = True
            fh = r.get("freshness_h")
            if not dates["is_historical"] and isinstance(fh, int) and fh > 90 * 24:
                continue
            filt.append(r)
        results = deduplicate(filt)
        src_intents = {s.name: s.intents for s in sources}
        results = rank(results, query, intent, src_intents)
        results = results[: min(max_results, 20)]
        self._apply_local_display(results, tz)
        md = self._markdown(query, intent, results, now_iso, dates)
        out = {"query": query, "intent": intent, "category": category,
               "count": len(results), "results": results, "markdown": md,
               "cached": False,
               "context": {"now_utc": now_iso, "today": today_label(), "tz": str(tz),
                           "is_historical": dates["is_historical"]}}
        self.mem.set(key, out)
        if self.disk:
            try:
                self.disk.set(json.dumps(key, sort_keys=True, default=str), out)
            except Exception:
                pass
        return out

    def _apply_local_display(self, results: list[dict], tz) -> None:
        """Add extra.local_display converted from event_date_utc. UTC default, never guessed."""
        if not tz or str(tz).upper() == "UTC" or tz == 0:
            return
        try:
            from dateutil import parser as _p, tz as _tz
            zone = _tz.gettz(str(tz)) if isinstance(tz, str) else _tz.tzoffset(None, int(tz) * 3600)
            if zone is None:
                return
            for r in results:
                iso = r.get("event_date_utc")
                if not iso:
                    continue
                try:
                    dt = _p.parse(iso)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    r.setdefault("extra", {})["local_display"] = dt.astimezone(zone).isoformat()
                    r["extra"]["local_tz"] = str(tz)
                except Exception:
                    continue
        except Exception:
            pass

    def _markdown(self, query, intent, results, now_iso, dates) -> str:
        if not results:
            return (f"_Context: {today_label()} {now_iso}._\n\n"
                    f"No results found for '{query}'. Try: 'latest astronomy news' or 'upcoming celestial events'.")
        lines = [f"_Context: {today_label()} {now_iso} (intent: {intent})._\n"]
        for r in results:
            pub = r.get("published") or r.get("event_date_utc") or ""
            lines.append(f"- **[{r.get('title')}]({r.get('url')})** — {r.get('source')}{', ' + pub[:10] if pub else ''}\n  {r.get('summary','')[:300]}")
            if r.get("event_date_utc"):
                vis = f" | Visible: {r.get('visibility')}" if r.get("visibility") else ""
                lines.append(f"  Event (UTC): {r.get('event_date_utc')}{vis}")
        return "\n".join(lines)

    def get_celestial_events(self, year: int | None = None, lat=None, lon=None) -> dict:
        from datetime import timezone
        year = year or datetime.now(timezone.utc).year
        now_iso = now_utc_iso()
        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            jobs = []
            for s in self.sources:
                if s.name in ("USNO", "JPL", "NASA", "NOAA SWPC"):
                    jobs.append(ex.submit(self._safe_fetch, s,
                                          "moon phases eclipses meteor showers seasons",
                                          intent="periodic_event", year=year, lat=lat, lon=lon, max_results=10))
            for f in jobs:
                try:
                    results.extend(f.result() or [])
                except Exception:
                    continue
        # static meteor peaks
        try:
            import json as _j
            from pathlib import Path
            p = Path(__file__).resolve().parent.parent / "data" / "meteor_showers.json"
            if p.exists():
                for m in _j.loads(p.read_text()):
                    if str(year) in str(m.get("peak", "")) or True:
                        from .normalizer import normalize as _n
                        results.append(_n({
                            "title": f"{m['name']} peak {m['peak']}", "summary": f"Peak {m['peak']} UTC. ZHR {m.get('zhr')}. Best: {m.get('hemisphere')}. Radiant {m.get('radiant')}. Moon: check USNO phase that night."[:400],
                            "url": "https://www.amsmeteors.org/meteor-showers/meteor-shower-calendar/",
                            "published": m["peak"], "category": "events", "event_type": "meteor_shower",
                            "event_date": m["peak"], "event_date_utc": m["peak"],
                            "visibility": m.get("hemisphere"), "extra": m,
                        }, {"name": "IMO/AMS", "source_type": "local", "authority": 2, "category": "events"}))
        except Exception as e:
            logger.warning(f"meteor json: {e}")
        results = deduplicate(results)
        results = rank(results, "celestial events", "periodic_event", None)[:100]
        return {"query": f"celestial events {year}", "intent": "periodic_event",
                "category": "events", "count": len(results), "results": results,
                "markdown": self._markdown(f"celestial events {year}", "periodic_event", results, now_iso, {"is_historical": False}),
                "cached": False, "context": {"now_utc": now_iso, "today": today_label(), "tz": "UTC"},
                "generated_at": now_iso,
                "data_as_of": {"static_yearly": f"{year}-01-01 (eclipses, seasons, meteor peaks: fixed for the year)",
                               "live_snapshot": now_iso + " (moon phases yearly-static; Kp/asteroids/APOD: re-query live when fresh matters)"}}
