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
    from .sources.gnews import GoogleNewsSource
    srcs = [RSSSource(c) for c in RSS_FEEDS]
    srcs += [USNOSource(), NOAASource(), NASASource(), JPLSource(),
             ArxivSource(), ADSSource(), ExoplanetSource(), ISSSource(), LocalSkySource(), FallbackSkySource(),
             GoogleNewsSource()]
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

    def _select(self, intent: str, entities: list[str], category: str,
                allow_gnews: bool = False) -> list:
        from .intent import KNOWN_ENTITIES
        # map entity values -> group keys (e.g. "aurora" -> "solar")
        val_to_group: dict[str, str] = {}
        for g, vals in KNOWN_ENTITIES.items():
            for v in vals:
                val_to_group[v] = g
        qgroups = {val_to_group.get(e, e) for e in (entities or [])} | set(entities or [])
        cands = []
        for s in self.sources:
            if getattr(s, "name", "") == "Google News" and not allow_gnews:
                continue  # gated supplemental: recency / trends / empty-pool only
            if intent not in getattr(s, "intents", []):
                continue
            ents = getattr(s, "entities", ["*"])
            if ents != ["*"] and entities and not (qgroups & set(ents)):
                # allow broad RSS through; skip narrow mismatches
                if getattr(s, "source_type", "") != "rss":
                    continue
            try:
                if not s.is_available():
                    continue
            except Exception:
                pass  # availability check itself failed -> try the source anyway
            cands.append(s)
        cands.sort(key=lambda s: getattr(s, "authority", 2), reverse=True)
        selected = cands[:5]
        # gated Google News: allowed paths always carry it despite authority 1
        if allow_gnews and not any(getattr(s, "name", "") == "Google News" for s in selected):
            for cand in cands[5:]:
                if getattr(cand, "name", "") == "Google News":
                    selected.append(cand)
                    break
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
               year: int | None = None, trends: bool = False,
               edition: str | None = None) -> dict:
        try:
            max_results = int(max_results)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            max_results = 8
        max_results = max(1, min(max_results, 20))
        now_iso = now_utc or now_utc_iso()
        if not (query or "").strip():
            return self.get_celestial_events(year=year, lat=lat, lon=lon)
        intent, entities = classify(query)
        dates = resolve_dates(query)
        key = (query, category, max_results, bool(trends), edition or "")
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
        from .sources.gnews import GoogleNewsSource, has_recency
        gnews_ok = bool(trends) or has_recency(query)
        if edition is None and any(k in query.lower() for k in (
                "isro", "gslv", "pslv", "lvm3", "sslv", "gaganyaan", "chandrayaan",
                "india", "indian", "nsil", "skyroot", "agnikul")):
            edition = "IN"  # Indian outlets carry ISRO coverage western press skips
        sources = self._select(intent, entities, category, allow_gnews=gnews_ok)
        kw = {"max_results": max_results, "intent": intent, "category": category,
              "lat": lat, "lon": lon, "tz": tz, "year": year or datetime.now(timezone.utc).year,
              "date": dates.get("date_min"), "now_utc": now_iso,
              "trends": bool(trends), "edition": edition}
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
        with ThreadPoolExecutor(max_workers=min(max(len(sources), 1), 6)) as ex:
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
            if (not dates["is_historical"] and isinstance(fh, int) and not isinstance(fh, bool)
                    and fh > 90 * 24):
                continue
            filt.append(r)
        results = deduplicate(filt)
        src_intents = {s.name: s.intents for s in sources}
        results = rank(results, query, intent, src_intents)
        results, backstopped = self._entity_gate(results, entities, max_results)
        if not results and not gnews_ok and intent in ("recent_news", "current_phenomenon",
                                                       "mission_status", "object_lookup"):
            # last resort: one gated Google News call before admitting defeat
            try:
                gn = next(s for s in self.sources if getattr(s, "name", "") == "Google News")
                extra = self._safe_fetch(gn, query, **{**kw, "max_results": 5})
                if extra:
                    results = rank(deduplicate(extra), query, intent, src_intents)[:max_results]
            except Exception:
                pass
        self._apply_local_display(results, tz)
        md = self._markdown(query, intent, results, now_iso, dates)
        out = {"query": query, "intent": intent, "category": category,
               "count": len(results), "results": results, "markdown": md,
               "cached": False, "backstopped": backstopped,
               "context": {"now_utc": now_iso, "today": today_label(), "tz": str(tz),
                           "is_historical": dates["is_historical"]}}
        if entities:
            from .ranker import _tok
            covered = any(any(set(_tok(e)) <= set(_tok(f"{r.get('title', '') or ''} {r.get('summary', '') or ''}"))
                              for e in entities) for r in results)
            out["coverage"] = "full" if covered else "partial"
            if not covered and results:
                out["markdown"] = ("_Note: no direct coverage of the requested subject found; "
                                   "showing closest related items. Try `astro_fetch` on the primary "
                                   "source (e.g. isro.gov.in/Press.html) or `trends: true`._\n\n" + md)
        self.mem.set(key, out)
        if self.disk:
            try:
                self.disk.set(json.dumps(key, sort_keys=True, default=str), out)
            except Exception:
                pass
        return out

    def _entity_gate(self, results: list[dict], entities: list[str], max_results: int) -> tuple[list[dict], bool]:
        """Specific-entity queries must actually mention the entity.

        Without this, "nancy grace telescope" returns any article containing just
        "telescope" (Webb/Hubble filler) or zero-hit freshest-item fallback
        (magnetism guide). When entities were extracted, keep only results covering
        >=1 full entity phrase; backstop to top-3 by score so agents never get nothing.
        Broad queries (no entities) pass through untouched.
        Returns (results, backstopped).
        """
        if not entities or not results:
            return results[:max_results], False
        from .ranker import _tok
        # programme families: "isro" is satisfied by Chandrayaan/GSLV/etc. mentions
        EQUIV = {"isro": {"isro", "chandrayaan", "gaganyaan", "pslv", "gslv", "lvm3", "sslv",
                          "navic", "aditya", "mangalyaan", "xposat", "astrosat", "india", "indian"},
                 "spacex": {"spacex", "starship", "falcon", "starlink", "dragon"}}
        keep = []
        for r in results:
            doc = set(_tok(f"{r.get('title', '') or ''} {r.get('summary', '') or ''}"))
            ok = False
            for e in entities:
                need = EQUIV.get(e, set(_tok(e)))
                if need <= doc:
                    ok = True
                    break
            if ok:
                keep.append(r)
        if not keep:
            # backstop only when the gate empties the pool: top-3 so agents get something
            keep = results[: min(3, len(results))]
            return keep[:max_results], True
        return keep[:max_results], False

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
                if s.name in ("USNO", "Local Sky", "JPL", "NASA", "NOAA SWPC"):
                    jobs.append(ex.submit(self._safe_fetch, s,
                                          "moon phases eclipses meteor showers seasons",
                                          intent="periodic_event", year=year, lat=lat, lon=lon, max_results=10))
            for f in jobs:
                try:
                    results.extend(f.result() or [])
                except Exception:
                    continue
        # static meteor peaks (per-year IMO file, else templated base)
        try:
            from .showers import load_showers
            from .normalizer import normalize as _n
            for m in load_showers(year):
                vis = m.get("hemisphere", "") + ("" if m.get("exact", True) else " (approx peak ±1d)")
                results.append(_n({
                    "title": f"{m['name']} peak {m['peak']}", "summary": f"Peak {m['peak']} UTC. ZHR {m.get('zhr')}. Best: {m.get('hemisphere')}. Radiant {m.get('radiant')}. Moon: check USNO phase that night."[:400],
                    "url": "https://www.imo.net/members/imo_showers/calendar/",
                    "published": m["peak"], "category": "events", "event_type": "meteor_shower",
                    "event_date": m["peak"], "event_date_utc": m["peak"],
                    "visibility": vis, "extra": m,
                }, {"name": "IMO/AMS", "source_type": "local", "authority": 2, "category": "events"}))
        except Exception as e:
            logger.warning(f"meteor data: {e}")
        results = deduplicate(results)
        results = rank(results, "celestial events", "periodic_event", None)[:100]
        return {"query": f"celestial events {year}", "intent": "periodic_event",
                "category": "events", "count": len(results), "results": results,
                "markdown": self._markdown(f"celestial events {year}", "periodic_event", results, now_iso, {"is_historical": False}),
                "cached": False, "context": {"now_utc": now_iso, "today": today_label(), "tz": "UTC"},
                "generated_at": now_iso,
                "data_as_of": {"static_yearly": f"{year}-01-01 (eclipses, seasons, meteor peaks: fixed for the year)",
                               "live_snapshot": now_iso + " (moon phases yearly-static; Kp/asteroids/APOD: re-query live when fresh matters)"}}
