"""AstroSearch orchestrator: intent → route → safe fan-out → dedup/rank → cache → markdown."""
from __future__ import annotations
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from .intent import classify
from .timeparse import now_utc_iso, today_label, resolve_dates, reference_time, timezone_for
from .deduplicator import deduplicate
from .ranker import rank
from .cache import TTLCache
from .cache_sqlite import SQLiteCache

logger = logging.getLogger("astro_search")

FALLBACK_CHAINS = {"NOAA SWPC": "Spaceweather.com", "USNO": "Local Sky",
                   "Local Sky": "Twilight Fallback", "NASA": "NASA News"}
PAYWALLED = ["New Scientist"]

# Rapid-report providers are never a complete archive and never verified evidence.
# One provider per intent keeps routing explicit: a named provider is not silently
# replaced by a different provider with a different coverage window.
RAPID_REPORT_PROVIDERS = {
    "alert_lookup": {
        "provider": "The Astronomer's Telegram",
        "scope": "current_top_feed_only",
        "note": "ATel rapid reports are preliminary, not peer-reviewed or independently verified. "
                "Only the current Top ATels feed was searched; an empty match does not mean no "
                "discovery. Timestamps are report issue times, not observation times."},
    "circular_lookup": {
        "provider": "GCN Circulars (NASA)",
        "scope": "recent_circular_list_plus_exact_id",
        "note": "GCN circulars are rapid reports, not peer-reviewed publications. Only the recent "
                "circular list and any exactly requested circular are searched; an empty match does "
                "not mean no circular exists. Timestamps are circular issue times, not observation "
                "times."},
    "mpec_lookup": {
        "provider": "Minor Planet Center (IAU)",
        "scope": "recent_100_mpecs_plus_exact_id",
        "note": "MPECs are bureau circulars, not peer-reviewed publications, and their element blocks "
                "publish no formal uncertainties. Only the 100 most recent MPECs and any exactly "
                "requested MPEC are searched; an empty match does not mean no MPEC exists."},
    "cbet_lookup": {
        "provider": "CBAT (IAU)",
        "scope": "recent_lists_only",
        "note": "CBETs and the recent-supernova list are bureau rapid reports, not peer-reviewed data, "
                "and are retrieved over unencrypted HTTP because the CBAT host completes no TLS "
                "handshake. Only the recent lists are searched; an empty match does not mean no "
                "circular exists."},
}


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
    from .sources.facts import MissionFactsSource
    from .sources.gcn import GCNSource
    from .sources.mpc import MPCSource
    from .sources.cbat import CBATSource
    from .sources.doi import DOISource
    from .sources.simbad import SimbadSource
    srcs = [RSSSource(c) for c in RSS_FEEDS]
    srcs += [USNOSource(), NOAASource(), NASASource(), JPLSource(),
             ArxivSource(), ADSSource(), ExoplanetSource(), ISSSource(), LocalSkySource(), FallbackSkySource(),
             GoogleNewsSource(), MissionFactsSource(), GCNSource(), MPCSource(), CBATSource(),
             DOISource(), SimbadSource()]
    return srcs


class AstroSearch:
    def __init__(self):
        from .runtime import SourceRuntime
        from .enrichment import Enricher
        self._enricher = Enricher()
        self._runtime = SourceRuntime()
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
                allow_gnews: bool = False, query: str = "") -> list:
        from .intent import KNOWN_ENTITIES
        from .sources.gnews import detected_publisher_domain
        q = (query or "").lower()
        # map entity values -> group keys (e.g. "aurora" -> "solar")
        val_to_group: dict[str, str] = {}
        for g, vals in KNOWN_ENTITIES.items():
            for v in vals:
                val_to_group[v] = g
        qgroups = {val_to_group.get(e, e) for e in (entities or [])} | set(entities or [])
        papers_only = category == "papers" or intent == "research_lookup"
        if papers_only:
            intent = "research_lookup"
        required = {"arXiv", "NASA ADS"} if papers_only else set()
        if intent == "object_lookup":
            from .intent import CATALOG_RE
            if any(CATALOG_RE.fullmatch(e) for e in entities):
                required.add("Exoplanet Archive")
        if "iss" in qgroups or "space station" in qgroups:
            required.add("Open Notify ISS")
        if qgroups & {"eclipses", "moon_phases"}:
            required.add("USNO")

        # Explicit publisher / source mentions in query
        if detected_publisher_domain(q):
            required.add("Google News")
            allow_gnews = True
        for s in self.sources:
            s_name = getattr(s, "name", "").lower()
            if s_name and (s_name in q or (s_name == "eso" and "eso" in q.split())):
                required.add(s.name)

        cands = []
        for s in self.sources:
            if papers_only and s.name not in {"arXiv", "NASA ADS"}:
                continue
            if getattr(s, "name", "") == "Google News" and not allow_gnews:
                continue  # gated supplemental: recency / trends / empty-pool only
            if intent not in getattr(s, "intents", []):
                continue
            ents = getattr(s, "entities", ["*"])
            if s.name not in required and ents != ["*"] and entities and not (qgroups & set(ents)):
                # allow broad RSS through; skip narrow mismatches
                if getattr(s, "source_type", "") != "rss":
                    continue
            try:
                if not s.is_available():
                    continue
            except Exception:
                pass  # availability check itself failed -> try the source anyway
            cands.append(s)

        cands.sort(key=lambda s: (s.name in required, getattr(s, "authority", 2)), reverse=True)
        if papers_only:
            return cands[:5]

        # For news/discoveries: balanced selection across institutions (auth 3) and publications (auth 2)
        if intent in ("recent_news", "mission_status", "discoveries"):
            req_cands = [s for s in cands if s.name in required]
            auth3 = [s for s in cands if s.name not in required and getattr(s, "authority", 2) >= 3]
            auth2 = [s for s in cands if s.name not in required and getattr(s, "authority", 2) == 2]
            other = [s for s in cands if s.name not in required and getattr(s, "authority", 2) < 2]
            selected = req_cands + auth3[:3] + auth2[:3] + other[:1]
            selected = selected[:8]
        else:
            selected = cands[:5]

        # gated Google News: allowed paths always carry it despite authority 1
        if allow_gnews and not any(getattr(s, "name", "") == "Google News" for s in selected):
            for cand in cands:
                if getattr(cand, "name", "") == "Google News":
                    selected.append(cand)
                    break
        # fallback guarantee: if a selected source has a named fallback not yet selected, append it
        names = {getattr(s, "name", "") for s in selected}
        for s in list(selected):
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
            from .normalizer import freshness_hours, freshness_display
            res = self._runtime.fetch(source, query, **kw)
            for row in res or []:
                row["freshness_h"] = freshness_hours(row.get("published", ""), kw.get("now_utc"))
                row["freshness_display"] = freshness_display(row["freshness_h"])
            return res or []
        except Exception as e:
            logger.warning("%s: %s", getattr(source, 'name', '?'), type(e).__name__)
            if kw.get("_errors") is not None:
                kw["_errors"].append({"source": getattr(source, "name", "?"),
                                      "error": type(e).__name__})
            return []

    query_timeout = 25.0

    def _fanout(self, sources, query, deadline, **kw):
        """Bound collection and process-wide admission; no hard HTTP cancellation."""
        from concurrent.futures import wait
        from .runtime import EXECUTOR
        results, errors, jobs = [], [], []
        for source in sources:
            if time.monotonic() >= deadline:
                errors.append({"source": source.name, "error": "deadline_exceeded"})
                continue
            source_errors = []
            future = EXECUTOR.submit(self._safe_fetch, source, query,
                                     **{**kw, "_errors": source_errors, "_deadline": deadline})
            if future is None:
                errors.append({"source": source.name, "error": "capacity_exceeded"})
                continue
            jobs.append((source, future, source_errors))
        done, _ = wait([f for _, f, _ in jobs], timeout=max(0, deadline - time.monotonic()))
        for source, future, source_errors in jobs:
            if future not in done:
                future.cancel()
                errors.append({"source": source.name, "error": "deadline_exceeded"})
            else:
                results.extend(future.result())
                errors.extend(source_errors)
        return results, errors

    def search(self, query: str = "", category: str = "all", max_results: int = 8,
               lat: float | None = None, lon: float | None = None,
               tz: str | int = "UTC", now_utc: str | None = None,
               year: int | None = None, trends: bool = False,
               edition: str | None = None, topic: str | None = None) -> dict:
        from .validation import observer, calendar_year, search_inputs
        search_inputs(query, category, trends, edition, topic)
        lat, lon = observer(lat, lon, tz)
        try:
            max_results = int(max_results)  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            max_results = 8
        max_results = max(1, min(max_results, 20))
        now = reference_time(now_utc or now_utc_iso())
        now_iso = now.isoformat().replace("+00:00", "Z")
        zone = timezone_for(tz)
        dates = resolve_dates(query, now=now, tz=tz)
        year = calendar_year(year, dates["year"] or now.astimezone(zone).year)
        if not (query or "").strip():
            return self.get_celestial_events(year=year, lat=lat, lon=lon, now_utc=now_iso, tz=tz)
        intent, entities = classify(query)
        from .interpretation import interpret
        spec = interpret(query)
        if spec.scope != "in_scope":
            status = "out_of_scope" if spec.scope == "out_of_scope" else "needs_clarification"
            return self._precision_response(query, spec, status, now_iso, tz, dates, category=category)
        if spec.property in {"distance", "event_dates", "moon_phase_date", "conjunction"} and category != "papers":
            from .answers import body_distance, calendar_answer, conjunction_answer, AnswerUnavailable
            try:
                if spec.clarification:
                    raise AnswerUnavailable(spec.clarification)
                if spec.property == "distance":
                    answer, rows = body_distance(spec.distance, now), []
                elif spec.property == "conjunction":
                    answer, rows = conjunction_answer(spec, now, lat=lat, lon=lon)
                else:
                    answer, rows = calendar_answer(query, spec, now, dates, tz)
            except AnswerUnavailable as exc:
                spec.clarification = str(exc)
                return self._precision_response(query, spec, getattr(exc, "status", "needs_clarification"),
                                                now_iso, tz, dates)
            out = self._precision_response(query, spec, "answered", now_iso, tz, dates)
            out.update(answer=answer, results=rows[:max_results], count=len(rows[:max_results]),
                       markdown=answer["text"] + "\n\n" + "\n".join(answer.get("qualifiers", [])))
            if rows:
                out["markdown"] += "\n\n" + self._markdown(query, spec.task, rows[:max_results], now_iso, dates, tz)
            if spec.property == "event_dates":
                out["coverage"] = "partial"  # a bounded calendar is not all celestial phenomena
            return out
        if spec.property == "doi_metadata":
            # An explicit DOI is resolved through its registration metadata whatever
            # category was requested; it is never answered from article prose.
            return self._search_fact(query, spec, max_results, now_iso, tz, dates)
        if spec.task == "fact_lookup" and category != "papers":
            return self._search_fact(query, spec, max_results, now_iso, tz, dates)
        if category == "papers":
            intent = "research_lookup"
        if intent == "research_lookup":
            category = "papers"
        # Include resolved civil dates so live caches cannot cross local midnight.
        key = ("v9-2026-feeds", query, category, max_results, bool(trends), edition or "", topic,
               lat, lon, str(tz), year, dates["date_min"], dates["date_max"],
               now.astimezone(zone).date().isoformat())
        if now_utc:
            key += (now_iso,)
        cached = self.mem.get(key)
        if cached:
            cached = dict(cached)
            cached["cached"] = True
            return cached
        if self.disk:
            ttl = 900 if intent in ("current_phenomenon", "recent_news", *RAPID_REPORT_PROVIDERS) else 86400
            d = self.disk.get(json.dumps(key, sort_keys=True, default=str), ttl)
            if d:
                d["cached"] = True
                self.mem.set(key, d)
                return d
        from .sources.gnews import GoogleNewsSource, has_recency
        gnews_ok = intent not in RAPID_REPORT_PROVIDERS and (bool(trends) or has_recency(query))
        if edition is None and any(k in query.lower() for k in (
                "isro", "gslv", "pslv", "lvm3", "sslv", "gaganyaan", "chandrayaan",
                "india", "indian", "nsil", "skyroot", "agnikul")):
            edition = "IN"  # Indian outlets carry ISRO coverage western press skips
        sources = self._select(intent, entities, category, allow_gnews=gnews_ok, query=query)
        kw = {"max_results": max_results, "intent": intent, "category": category,
              "lat": lat, "lon": lon, "tz": tz, "year": year,
              "date": dates.get("date_min"), "date_max": dates.get("date_max"), "now_utc": now_iso,
              "trends": bool(trends), "edition": edition, "topic": topic or "astrophysics",
              "entities": entities}
        # location-aware: guarantee Twilight Fallback when lat/lon supplied
        if category != "papers" and lat is not None and lon is not None and not any(getattr(s, "name", "") == "Twilight Fallback" for s in sources):
            for cand in self.sources:
                if getattr(cand, "name", "") == "Twilight Fallback":
                    sources.append(cand)
                    break
        # moon-aware: guarantee USNO or Local Sky when query mentions moon
        if category != "papers" and "moon" in query.lower() and not any(getattr(s, "name", "") in ("USNO", "Local Sky") for s in sources):
            for want in ("USNO", "Local Sky"):
                for cand in self.sources:
                    if getattr(cand, "name", "") == want and intent in getattr(cand, "intents", []):
                        sources.append(cand)
                        break
                if any(getattr(s, "name", "") in ("USNO", "Local Sky") for s in sources):
                    break
        deadline = time.monotonic() + self.query_timeout
        results, errors = self._fanout(sources, query, deadline, **kw)
        # quality filters: paywall flag, stale pinned (>90d unless historical)
        filt = []
        for r in results:
            if r.get("source") in PAYWALLED:
                r.setdefault("extra", {})["paywalled"] = True
            fh = r.get("freshness_h")
            if category != "all" and r.get("category") != category:
                continue
            if (intent in ("recent_news", "mission_status", "current_phenomenon")
                    and not dates["is_historical"] and isinstance(fh, int) and not isinstance(fh, bool)
                    and fh > 90 * 24):
                continue
            filt.append(r)
        results = deduplicate(filt)
        src_intents = {s.name: s.intents for s in sources}
        results = rank(results, query, intent, src_intents)
        results, backstopped = self._entity_gate(results, entities, max(12, max_results))
        if not results and not gnews_ok and intent in ("recent_news", "current_phenomenon",
                                                       "mission_status", "object_lookup"):
            # last resort: one gated Google News call before admitting defeat
            try:
                gn = next(s for s in self.sources if getattr(s, "name", "") == "Google News")
                extra, fallback_errors = self._fanout([gn], query, deadline, **{**kw, "max_results": 5})
                errors.extend(fallback_errors)
                extra = [r for r in extra if category == "all" or r.get("category") == category]
                if extra:
                    extra = [r for r in extra if not (
                        intent in ("recent_news", "mission_status", "current_phenomenon")
                        and not dates["is_historical"] and isinstance(r.get("freshness_h"), int)
                        and r["freshness_h"] > 90 * 24)]
                    results, _ = self._entity_gate(
                        rank(deduplicate(extra), query, intent, src_intents), entities, max_results)
            except Exception:
                pass
        enrichment = self._enricher.enrich(results, deadline)
        errors.extend(enrichment.pop("errors"))
        results = rank(results, query, intent, src_intents)[:max_results]
        self._apply_local_display(results, tz)
        md = self._markdown(query, intent, results, now_iso, dates, tz)
        out = {"query": query, "intent": intent, "category": category,
               "count": len(results), "results": results, "markdown": md,
               "cached": False, "backstopped": backstopped,
               "context": {"now_utc": now_iso, "today": today_label(now, tz), "tz": str(tz),
                           "is_historical": dates["is_historical"]}}
        if intent in RAPID_REPORT_PROVIDERS:
            meta = RAPID_REPORT_PROVIDERS[intent]
            out["alert_coverage"] = {"provider": meta["provider"], "complete_archive": False,
                                     "scope": meta["scope"]}
            out["markdown"] = f"_{meta['note']}_\n\n" + out["markdown"]
        out["enrichment"] = enrichment
        out["errors"] = errors
        out["interpretation"] = spec.to_dict()
        out["answer_status"] = "indirect" if results else ("retrieval_failed" if errors else "not_found")
        out["coverage"] = "partial" if results else "none"
        if entities:
            from .ranker import _tok
            from .relevance import fields
            covered = any(any(set(_tok(e)) <= set(_tok(' '.join(text for _, text, _ in fields(r))))
                              for e in entities) for r in results)
            out["entity_coverage"] = "matched" if covered else "none"
            if not covered and results:
                out["markdown"] = ("_Note: no direct coverage of the requested subject found; "
                                   "showing closest related items. Try `astro_fetch` on the primary "
                                   "source (e.g. isro.gov.in/Press.html) or `trends: true`._\n\n" + md)
        if not errors:
            self.mem.set(key, out)
        if self.disk and not errors:
            try:
                self.disk.set(json.dumps(key, sort_keys=True, default=str), out)
            except Exception:
                pass
        return out

    def _entity_gate(self, results: list[dict], entities: list[str], max_results: int) -> tuple[list[dict], bool]:
        """Keep explicit entity mentions, with no unrelated top-three backstop.

        Broad discovery queries without extracted entities retain ranked results.
        This is an entity filter, not evidence verification; factual requests use
        the separate subject/property verifier. The legacy flag stays false.
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
            from .relevance import fields
            doc = set(_tok(' '.join(text for _, text, _ in fields(r))))
            ok = False
            for e in entities:
                if (bool(EQUIV[e] & doc) if e in EQUIV else set(_tok(e)) <= doc):
                    ok = True
                    break
            if ok:
                keep.append(r)
        return keep[:max_results], False

    def _precision_response(self, query, spec, status, now_iso, tz, dates,
                            results=None, errors=None, category="all"):
        results, errors = results or [], errors or []
        messages = {
            "out_of_scope": "No results: this request is outside the supported astronomy scope.",
            "needs_clarification": spec.clarification or "Please clarify the astronomical subject or property.",
            "not_found": "No supporting evidence found for the requested subject and property.",
            "retrieval_failed": "Supporting evidence could not be retrieved. No answer is inferred.",
            "conflicting_evidence": "Sources contain conflicting measurements. Do not select a value without resolving the discrepancy.",
            "answered": "Explicit primary-source evidence found; this is not independent scientific certification.",
        }
        md = messages[status]
        if spec.clarification and status != "needs_clarification":
            # A negative computed answer still carries what was actually found.
            md += "\n\n" + spec.clarification
        for row in results:
            ev = row["evidence"]
            md += "\n\n> " + row["summary"] + "\n\nSource: " + ev["citation_url"]
        if spec.assumptions:
            md += "\n\nThe query's launch-status premise has not been verified."
        answer = None
        if status == "answered" and results:
            ev = results[0]["evidence"]
            measurement = ev["measurements"][0]
            answer = {"subject": spec.subject, "property": spec.property,
                      "value": measurement["value"], "unit": measurement["unit"],
                      "method": measurement.get("method", "primary_source"),
                      "text": measurement["quote"], "citation": ev["citation_url"],
                      "reference": measurement.get("reference"),
                      "uncertainty": measurement.get("uncertainty"),
                      "retrieved_at": ev.get("retrieved_at"),
                      "qualifiers": [ev["verification"]]}
            if measurement.get("alternate_determinations"):
                answer["alternate_determinations"] = measurement["alternate_determinations"]
            if ev.get("uncertainty_note"):
                answer["qualifiers"].append(ev["uncertainty_note"])
        return {"query": query, "intent": spec.task, "category": category,
                "answer": answer,
                "count": len(results), "results": results, "markdown": md,
                "answer_status": status, "coverage": "full" if status == "answered" else ("partial" if results else "none"),
                "interpretation": spec.to_dict(), "cached": False, "backstopped": False,
                "errors": errors, "context": {"now_utc": now_iso, "today": today_label(reference_time(now_iso), tz),
                                               "tz": str(tz), "is_historical": dates["is_historical"]}}

    def _search_fact(self, query, spec, max_results, now_iso, tz, dates):
        from .evidence import filter_evidence
        if spec.clarification:
            return self._precision_response(query, spec, "needs_clarification", now_iso, tz, dates)
        sources = self._select("fact_lookup", spec.aliases, "all")
        # Rewrites retain the exact property definition, not a bag of mass synonyms.
        rewritten = f"{spec.subject or ''} {(spec.property or '').replace('_', ' ')}".strip()
        rows, errors = self._fanout(sources, rewritten, time.monotonic() + self.query_timeout,
                                   max_results=max_results, intent="fact_lookup", category="all",
                                   now_utc=now_iso, interpretation=spec.to_dict())
        # Inspect the complete retrieved pool before truncation/deduplication so a
        # conflicting value cannot disappear just because it ranked lower.
        results, status = filter_evidence(rows, spec)
        if errors and not results:
            status = "retrieval_failed"
        if errors and status == "answered":
            # A failed source may contain contradictory evidence: do not claim full coverage.
            status = "retrieval_failed"
        return self._precision_response(query, spec, status, now_iso, tz, dates,
                                        results[:max_results], errors)

    def search_papers(self, query, topic="astrophysics", max_results=5):
        from .sources.arxiv import CATS
        if topic not in CATS:
            raise ValueError(f"Unknown paper topic: {topic}")
        return self.search(query, category="papers", topic=topic, max_results=max_results)

    def _apply_local_display(self, results: list[dict], tz) -> None:
        """Add extra.local_display converted from event_date_utc. UTC default, never guessed."""
        if not tz or str(tz).upper() == "UTC" or tz == 0:
            return
        try:
            from dateutil import parser as _p, tz as _tz
            zone = timezone_for(tz)
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

    def _markdown(self, query, intent, results, now_iso, dates, tz="UTC") -> str:
        label = today_label(now_iso, tz)
        if not results:
            return (f"_Context: {label} {now_iso}._\n\n"
                    f"No results found for '{query}'. Try: 'latest astronomy news' or 'upcoming celestial events'.")
        lines = [f"_Context: {label} {now_iso} (intent: {intent})._\n"]
        for r in results:
            pub = r.get("published") or r.get("event_date_utc") or ""
            excerpt = r.get("excerpt") or {}
            display = excerpt.get("text") or r.get("summary", "")
            label = f" ({excerpt['source']}; unverified excerpt)" if excerpt.get("source") else ""
            date_label = "updated" if r.get("published_kind") == "updated_fallback" else "published"
            lines.append(f"- **[{r.get('title')}]({r.get('url')})** — {r.get('source')}{', ' + date_label + ' ' + pub[:10] if pub else ''}\n  {display}{label}")
            if r.get("event_date_utc"):
                vis = f" | Visible: {r.get('visibility')}" if r.get("visibility") else ""
                lines.append(f"  Event (UTC): {r.get('event_date_utc')}{vis}")
            elif r.get("date_only") and r.get("event_date"):
                lines.append(f"  Event date: {r['event_date']} (time not supplied)")
        return "\n".join(lines)

    def get_celestial_events(self, year: int | None = None, lat=None, lon=None,
                             now_utc=None, tz="UTC") -> dict:
        from .validation import observer, calendar_year
        lat, lon = observer(lat, lon, tz)
        now = reference_time(now_utc or now_utc_iso())
        year = calendar_year(year, now.astimezone(timezone_for(tz)).year)
        now_iso = now.isoformat().replace("+00:00", "Z")
        sources = [s for s in self.sources if s.name in ("USNO", "Local Sky", "JPL", "NASA", "NOAA SWPC")]
        results, errors = self._fanout(sources, "moon phases eclipses meteor showers seasons",
                                      time.monotonic() + self.query_timeout,
                                      intent="periodic_event", year=year, lat=lat, lon=lon,
                                      now_utc=now_iso, tz=tz, max_results=10)
        meteor_count = 0
        # static meteor peaks (per-year IMO file, else templated base)
        try:
            from .showers import load_showers
            from .normalizer import normalize as _n
            meteors = load_showers(year)
            meteor_count = len(meteors)
            for m in meteors:
                vis = m.get("hemisphere", "") + ("" if m.get("exact", True) else " (approx peak ±1d)")
                results.append(_n({
                    "title": f"{m['name']} peak {m['peak']}", "summary": f"Peak {m['peak']} UTC. ZHR {m.get('zhr')}. Best: {m.get('hemisphere')}. Radiant {m.get('radiant')}. Moon: check USNO phase that night."[:400],
                    "url": "https://www.imo.net/members/imo_showers/calendar/",
                    "published": m["peak"], "category": "events", "event_type": "meteor_shower",
                    "event_date": m["peak"], "event_date_utc": m["peak"],
                    "visibility": vis, "extra": m,
                }, {"name": "IMO/AMS", "source_type": "local", "authority": 2, "category": "events"}))
        except Exception as e:
            errors.append({"source": "IMO/AMS", "error": type(e).__name__})
        from .calendar import partition_events, validate_calendar_payload
        results, snapshots, references = partition_events(deduplicate(results), year)
        for snapshot in snapshots:
            snapshot.setdefault("extra", {})["retrieved_at"] = now_iso
        validation = validate_calendar_payload({"results": results, "count": len(results)}, year, meteor_count)
        if not meteor_count:
            validation.append("meteor dataset unavailable")
        return {"query": f"celestial events {year}", "intent": "periodic_event",
                "schema_version": 2, "year": year, "live_snapshots": snapshots, "errors": errors,
                "references": references,
                "completeness": {"publishable": not validation, "errors": validation,
                                 "lunar_eclipses": "reference_only", "planetary_events": "not_implemented"},
                "category": "events", "count": len(results), "results": results,
                "markdown": self._markdown(f"celestial events {year}", "periodic_event", results, now_iso, {"is_historical": False}, tz),
                "cached": False, "context": {"now_utc": now_iso, "today": today_label(now, tz), "tz": str(tz)},
                "generated_at": now_iso,
                "data_as_of": {"static_yearly": f"{year}-01-01 (eclipses, seasons, meteor peaks: fixed for the year)",
                               "live_snapshot": now_iso + " (moon phases yearly-static; Kp/asteroids/APOD: re-query live when fresh matters)"}}
