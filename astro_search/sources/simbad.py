"""SIMBAD TAP source for bounded, reference-carrying object properties.

Only a whitelisted property set is queried, only a validated identifier is sent,
and a value is reported only with the reference SIMBAD publishes for it.
"""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize
from ..timeparse import now_utc_iso

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; astro-search/2.1; +https://github.com/amanmathur27/astro-search)",
    "Accept": "application/json",
}


class SimbadSource(BaseSource):
    name = "SIMBAD"
    source_type = "api"
    authority = 3
    intents = ["fact_lookup"]
    entities = ["*"]
    timeout = 20

    def fetch(self, query: str, **kwargs) -> list[dict]:
        from ..simbad import (SUPPORTED, TAP, build_query, candidate_identifier,
                              record_from_payload, requested_band, safe_identifier)
        spec = kwargs.get("interpretation") or {}
        prop = spec.get("property")
        if prop not in SUPPORTED:
            # Unsupported properties are never approximated with a nearby column.
            return []
        identifier = safe_identifier(spec.get("subject") or "") or candidate_identifier(query)
        if not identifier:
            return []
        band, _explicit = requested_band(query)
        payload, failure = self._resolve(TAP, prop, identifier, band, build_query)
        if failure:
            self.report_error(kwargs)
            return []
        record = record_from_payload(payload, prop, identifier, band)
        if not record:
            return []  # unknown, ambiguous, or unfilterable: never a guessed value
        record["retrieved_at"] = now_utc_iso()
        record["content_trust"] = "untrusted_external"
        record["query_url"] = TAP
        return [normalize({"title": record["quote"], "summary": record["quote"],
                           "url": self._record_url(record), "published": "",
                           "category": "discoveries",
                           "extra": {"archive_record": record, "transport": "https",
                                     "content_trust": "untrusted_external",
                                     "retrieved_at": now_utc_iso()}},
                          {"name": self.name, "authority": self.authority,
                           "source_type": "api", "category": "discoveries"})]

    def _resolve(self, tap, prop, identifier, band, build_query):
        """Query as supplied, then one bounded case-normalized retry.

        Returns (payload, failure). An unresolvable identifier is an empty payload,
        not a failure, so it becomes an honest not-found.
        """
        attempts = [identifier]
        stripped = identifier.strip()
        if not any(ch.isdigit() for ch in stripped) and stripped[:1].isupper():
            attempts.append(stripped.lower())
        payload = None
        for attempt in attempts:
            adql = build_query(prop, attempt, band)
            if not adql:
                return None, "invalid_query"
            payload, failure = self._tap(tap, adql)
            if failure:
                return None, failure
            if payload and payload.get("data"):
                return payload, None
        return payload, None

    def _tap(self, tap, adql):
        try:
            response = requests.get(tap, headers=HEADERS, timeout=self.timeout,
                                    params={"request": "doQuery", "lang": "adql",
                                            "format": "json", "query": adql})
        except Exception:
            return None, "transport_error"
        if response.status_code != 200:
            # A rejected ADQL query is a provider-side failure, never a no-data answer.
            return None, "http_error"
        try:
            payload = response.json()
        except ValueError:
            return None, "malformed_payload"
        if not isinstance(payload, dict) or "data" not in payload:
            return None, "malformed_payload"
        return payload, None

    def _record_url(self, record) -> str:
        from urllib.parse import quote
        return ("https://simbad.u-strasbg.fr/simbad/sim-id?Ident="
                + quote(str(record.get("record_id") or ""), safe=""))