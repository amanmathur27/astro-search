## ATel rapid-report discovery

`astro_search("latest ATel reports")` and explicit astronomical transient alert/report
queries route to the public Top ATels RSS feed, not general news or paper sources.
Use category `all` or `news`. ATel/GRB identifiers match exactly; residual topic terms
must occur in the title/description. This conservative lexical filter can miss synonyms
or details absent from the feed. Only current feed entries are searched, not the archive.
The sampled live feed contained ten reports; no complete time-window coverage or
fixed publication cadence is guaranteed. Empty results do not establish no discovery.

Reports carry `extra.report_id`, `publication_status=rapid_report_not_peer_reviewed`,
and issue-time semantics. They remain indirect, unverified evidence, never automatic
confirmed coordinates/magnitudes. Full text can be fetched separately. Missing/invalid
feeds emit diagnostics rather than being treated as a successful empty feed. Query
cache TTL is 15 minutes; ingestion is polling, not real-time push. Existing deadline,
source backoff and bounded enrichment apply; no additional dependency or credential.
The feed participates in the existing RSS health-check enumeration.

Other agent-compatibility gaps remain open: modern GCN access, MPC ingestion/element
parsing, CBAT access, stellar-property retrieval, conjunction geometry and DOI services.
ATel alone does not close the entire alert-network gap or justify retiring existing
agent retrieval. Hosted Actions and production recall/latency remain unverified.


## Metadata-aware article retrieval

Search now preserves source descriptions (up to 8,000 characters) separately from
400-character display summaries. Fetched HTML contributes distinct title, description,
Open Graph fields, Article-family JSON-LD fields, headings and bounded whole paragraphs.
Fields carry their extraction origin; all publisher metadata remains untrusted.
Publication and modification claims are separate. RSS updated-date fallback is labeled.

Field-aware lexical ranking uses the best matching field plus query coverage and a
bounded BM25 tie-breaker; identical text repeated across metadata fields is deduplicated.
Subject/property matching is a lexical diagnostic, NOT semantic relationship verification.
Freshness is preferred for news/status queries, not for timeless fact queries. Authority
and freshness cannot give a zero-relevance document a positive score.

Discovery enriches at most three RSS/news candidates (two top candidates plus one
host-diverse candidate where available), waits at most three seconds within the existing
query deadline, and reranks. A per-engine 64-entry/15-minute URL cache avoids repeat
successful downloads. Failures are labeled and prevent successful response caching;
metadata-only results remain usable as background. Network/DNS work already running
cannot be forcibly cancelled, but shared execution/admission remains bounded.

Results expose metadata, relevance diagnostics, an extractive excerpt with origin, and
enrichment status. Excerpts retain whole paragraphs <=2,000 characters; longer paragraphs
are omitted and flagged, not silently cut into evidence. The demo and Markdown show
excerpt origin. Metadata/excerpts NEVER create verified direct answers. The existing
primary-source verifier and local computational answer paths remain separate.

Limits: lexical matching is not universal semantic understanding; a matching subject and
property in one field does not prove that the measurement belongs to that subject. RSS
is not a historical web index. The shortlist can miss poorly described pages. Page dates
are publisher claims, not verified event dates; conflicts are retained rather than resolved.
No browser/ML dependency added. Tests are offline; hosted Actions and broad relevance/
p50/p95 measurements require separate runs. The local demo remains git-ignored.


## Distance capability family (supersedes the Moon-only milestone below)

A shared capability registry now drives subject interpretation and computation for
Earth-referenced distances to Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn,
Uranus, Neptune and Pluto. The structured request carries target, reference and unit.
Supported units are km, miles, meters and AU; input body ordering does not change
Earth as the declared computational reference. No additional network/model dependency.

The bounded grammar validates the whole distance phrase, rather than ignoring unknown
modifiers after matching two names. Unsupported pairs, averages, historical requests,
surface separation and extra bodies abstain with a capability explanation. This is
not universal semantic understanding. Other question families retain their existing
limitations; extending distance does not establish their coverage.

Tests sweep 10 bodies x 6 phrasings x 4 units, with additional scope/rejection tests
and a local-demo HTTP regression when that temporary frontend and PyEphem are present.
Comparisons to PyEphem verify dispatch/unit conversions, not independent model accuracy.


## Direct-answer milestone (September 2026)

Search now returns an `answer` object for supported local and evidence-backed queries.
The demo displays its text, method, timestamp, qualifiers and provenance above results.

- Earth–Moon distance: current geocentric center-to-center distance using optional
  PyEphem, in km or miles. No HTTP or ephemeris downloads. Averages, other body pairs
  and unsupported temporal constraints request clarification instead of news.
- Lunar phases and monthly celestial events: packaged 2026–2027 reference calendars,
  structurally validated at query time. UTC instants are filtered by the requested
  civil timezone. “Next” excludes elapsed instants; an occurrence outside the requested
  month is explicitly flagged. Monthly browsing includes the entire month.
- Calendar coverage is partial: planetary events and local visibility are not computed;
  lunar eclipses remain reference-only. Lunar cross-check tolerance is 120 seconds,
  not an accuracy guarantee for showers, seasons or eclipses. Named months and several
  relative-date formulations still request clarification.
- Completed mission launch dates: narrow primary-source extraction of affirmative
  subject-bound statements with full dates. Planned/future launches, negation and
  invalid dates are not completed-launch answers. Registry and phrase coverage remain
  small; Roman's launch is not assumed to have happened. Live mission evidence is not
  certified by offline fixtures.
- Successful factual evidence also supplies a top-level answer. Conflicts and retrieval
  errors do not. Local answers deliberately bypass response caching so their reference
  instant never becomes stale; file reads/computation are small but not zero cost.
- GitHub Actions already tests base and local extras. The local job now explicitly
  imports PyEphem; the wheel job checks packaged-calendar answers outside checkout.
  These changes have not run on hosted Actions until committed/pushed by the user.
- Packaged calendar snapshots must be refreshed alongside repository calendars; this
  milestone supports only 2026–2027. Universal semantic question answering, planned-launch
  answers, a generalized property registry and volatility-specific caching are not done.


# Current capabilities and assessment follow-up

Updated 2026-09-17 for the uncommitted correctness pass, not a released version.
This document supersedes current-capability claims in historical handoffs and the
source registry. Those documents remain design/source-discovery references.
Free access does not imply unrestricted reuse: check publisher terms.

## Status matrix

Tested means deterministic regression coverage, not certification of live APIs or
independent astronomical verification of every timestamp.

| Capability | Status | Limits |
|---|---|---|
| Tool integration | Implemented; offline tests | Four handlers; no hosted service |
| Cache identity | Tested | Location, timezone, year, topic, civil dates and explicit time; v5 keys |
| Cache bounds | Tested | Entry-count caps, not bytes; SQLite age cleanup is not per-entry TTL reclamation |
| Request-time context | Implemented; tested | Aware overrides, civil-date resolution, source reference time and freshness; live feeds are not historical archives |
| Relative dates | Tested | Next week = next Monday–Sunday; weekend = this week's Saturday–Sunday; upstream date-window enforcement remains partial |
| Papers | Tested | Only arXiv/ADS; topic propagated; ADS needs key; selection does not guarantee results |
| ISS routing | Tested | Adapter reserved for ISS; provider health/pass prediction are separate concerns |
| Catalog lookup | Tested through public tool | Shared parser/router for common HD, Kepler, K2, TOI, WASP, HAT-P, TRAPPIST, GJ/Gliese and Proxima names; not general name resolution |
| NOAA | Fixture-tested | Unknown Kp/Bz preserved, finite/range Kp validation, timestamps, GOES long-channel selection; not local aurora prediction |
| Moon appearance | Tested | Eight approximate labels; not exact phase-event instants |
| Local compute | Implemented | PyEphem needs no downloads; Skyfield only uses existing de421.bsp |
| Meteor data | Packaged; tested | Future-year templates approximate; exact-year provenance still needs human verification |
| Annual calendar v2 | Fixture-tested | Year-filtered chronological results, separate snapshots/references, publication gates and atomic per-file replacement |
| Solar eclipses | Date-level support | date_only=true, precision=day, event_date is YYYY-MM-DD; event_date_utc=null without a supplied instant |
| Lunar eclipses | Reference only | No individual computed lunar-eclipse events |
| Visibility/planetary events | Partial / planned | Rise-set and link-outs exist; comprehensive visibility and conjunction/opposition prediction not implemented |
| Horizons / SBDB | Structured; fixture-tested | UTC samples, RA/Dec/Az/El degrees and nullable magnitude; malformed samples/object identities rejected. Not a rise/set or planetary-event solver |
| RSS/Google News | Partial; fixture tests | Improved fallback relevance and dates; still limited recent feed pools |
| Trends | Article sample | Seven-day retrieval, not measured topic volume |
| Article fetch | Defensive checks; tested | Public HTTP(S) prechecks, redirect checks, 2 MiB cap, minimum text; heuristic extraction, untrusted content |
| Query deadlines | Collection/admission tested | Process-wide pool: 8 workers, 24 admitted jobs; running HTTP calls cannot be forcibly cancelled |
| Source cache/backoff | Implemented; tested | Per-engine, bounded 256-entry one-minute cache; exponential failure cooldown capped at 60 seconds; exact context keys reduce live cache reuse |
| Errors | Caught-exception diagnostics tested | Sanitized source/error types; partial/outage responses are not cached. Some non-OK or malformed upstream payloads still need endpoint-specific diagnostics |
| Retrieval benchmark | Six labeled offline cases | Intent/source coverage, MRR, P@5, recall and local latency; not a representative live-web quality evaluation |
| CI | Configured | Core/local matrix, installed-wheel smoke, feed age/status checks, gated calendars; hosted runs not locally verified |
| Query interpretation | Implemented; offline tested | Scope gate + subject/property extraction for a small mission seed list (Roman, Webb, Hubble) and narrow property phrases; not general NLU |
| Factual lookup (fact_lookup) | Implemented; offline tested | Primary-source page fetch + explicit-clause evidence match (value+unit) for launch/payload/dry mass and mirror diameter; ambiguous mass/diameter asks for clarification; historical-year and multi-fact requests are refused, not guessed |
| Abstention | Implemented; tested | Out-of-domain queries return `answer_status: out_of_scope` with no retrieval; ambiguous queries `needs_clarification`; no-evidence `not_found`; entity-gate top-3 backstop removed |
| Evidence verification | Implemented; offline tested | Quote+unit+citation only from fetched primary mission pages (NASA/ESA host check); snippets, tertiary sources, negation, wrong units, and wrong subject rejected; conflicting values reported as `conflicting_evidence`. Extractive, not semantic: only explicit statement patterns are recognized |
| Semantic reranking | Planned | Optional dependency does not activate a reranker |

## Calendar migration

Check schema_version == 2 and completeness. results/count now describe annual events
only; live_snapshots and references are separate. Visibility may be null. A civil
date is not a midnight UTC event. Approximate meteor peaks retain uncertainty metadata.
The gate checks malformed records, duplicates, per-phase coverage, seasonal months,
dates, year, chronology and count consistency, not full scientific accuracy. All years
are validated before writing; individual files are atomic, not a multi-file transaction.
The working-tree 2026/2027 JSONs were regenerated as v2 (70/69 annual events).
All 99 lunar phase instants were cross-checked against PyEphem: maximum differences
36.25 seconds (2026) and 34.37 seconds (2027). The optional-local CI test allows two
minutes for model/rounding differences. Meteor peaks, seasons, and eclipse circumstances
have not all been independently certified. Cached live snapshots must not be used as
current conditions.

## Follow-up implementation completed

- Structured Horizons parser and small-body designation extraction, with identity and
  malformed-response regressions; unrelated close-approach calls reduced.
- Bounded shared source execution, per-engine source caches/cooldowns, and sanitized
  caught-exception diagnostics. Failed/partial searches are not response-cached.
- Public coordinate/year/timezone/input validation; NASA date-window chunking and DONKI
  start/end propagation; DONKI event-time fields. Not every provider supports archives.
- Stronger calendar gates and regenerated 2026/2027 artifacts, with independent lunar checks.
- NOAA timestamp ordering, future/stale sample rejection, Bz/flux sanity bounds, long-band
  GOES selection and forecast/alert issue-age checks. Alert expiry parsing is not complete.
- Argument-forwarding tests for all four public handlers, plus source diagnostics tests.
- Six-case offline routing/ranking benchmark in `benchmarks/retrieval.json`, executed by
  `tools/benchmark_retrieval.py` and pytest. Its deliberately small fixture pools do not
  establish live search quality or historical recall.

## Still-open work / release gates

1. Hosted CI requires publishing this working tree to a remote branch; it has not run
   on these changes. No push/deploy was performed. Local tests are not hosted validation.
2. Meteor data provenance requires authoritative external review; lunar checks do not
   validate showers, seasons or eclipse visibility. General planetary-event computation
   and individual lunar-eclipse events remain unimplemented.
3. Exhaustive happy/malformed fixtures for every upstream endpoint are not complete.
   Some HTTP status/malformed-payload paths remain silent; backoff is not a full
   Retry-After-aware retry state machine. Date-window support remains provider-dependent.
4. Fetch checks are defense in depth: DNS is not pinned and ambient proxies affect
   routing. Use restricted egress for untrusted callers. Word-count checks cannot
   reliably identify consent/paywall screens; retrieved text is untrusted evidence.
5. Expand the benchmark to an independently labeled corpus and live-source evaluation;
   report citation usability, missing-answer rates and historical coverage separately.

## Deferred product work

General SIMBAD/Gaia/VizieR resolution, exact planetary events, semantic reranking,
measured trends, historical index and shared hosting remain planned. No deployment,
tag, push or release was performed in this pass.
