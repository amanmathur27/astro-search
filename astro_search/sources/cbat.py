"""CBAT source over plaintext HTTP (the host completes no TLS handshake).

Every row records the transport and TLS status so an agent can weigh integrity.
CBETs and the recent-supernova list are rapid reports, never verified evidence.
The CBAT RSS feeds answer 401 (subscription-only) and are not used.
"""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize
from ..timeparse import now_utc_iso

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html, text/plain;q=0.9, */*;q=0.8",
}
MAX_HYDRATE = 2


class CBATSource(BaseSource):
    name = "CBAT (IAU)"
    source_type = "api"
    authority = 3
    intents = ["cbet_lookup"]
    entities = ["*"]
    timeout = 20

    def _text(self, url: str) -> str:
        response = requests.get(url, headers=HEADERS, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def fetch(self, query: str, **kwargs) -> list[dict]:
        try:
            max_results = min(max(int(kwargs.get("max_results", 8)), 1), 20)
        except (TypeError, ValueError):
            max_results = 8
        try:
            rows = self._collect(query, max_results)
        except Exception:
            self.report_error(kwargs)
            return []
        return rows

    def _collect(self, query, max_results) -> list[dict]:
        import re
        from ..cbat import (CBET_LIST, SUPERNOVA_LIST, cbet_number, list_matches,
                            parse_cbet_list, parse_supernova_list)
        if re.search(r"\b(?:supernova|sn\s?(?:19|20)\d{2})\w*\b", query or "", re.I):
            entries = parse_supernova_list(self._text(SUPERNOVA_LIST))
            if not entries:
                raise ValueError("no supernovae parsed from the recent list")
            supern = re.findall(r"(?:sn\s?)?((?:19|20)\d{2}[a-z]{1,3})", query or "", re.I)
            wanted = {s.lower() for s in supern}
            from ..relevance import tokens as _tokens
            generic = not (_tokens(re.sub(r"\b(?:cbat|supernovae?|sns?|latest|recent|new|"
                                          r"lists?|reports?|about|show|find)\b", "", query or "", flags=re.I))
                        - {"sn", "supernova", "supernovae"})
            selected = [e for e in entries
                        if (wanted and e["supernova"].lower() in wanted)
                        or list_matches(query, e["supernova"])
                        or list_matches(query, e.get("host_galaxy") or "")
                        or generic]
            return [self._supernova_row(e) for e in selected[:max_results]]
        entries = parse_cbet_list(self._text(CBET_LIST))
        if not entries:
            raise ValueError("no CBETs parsed from the recent list")
        wanted = cbet_number(query)
        selected = [e for e in entries if list_matches(query, e["title"]) or (wanted and e["cbet_number"] == wanted)]
        rows = []
        for entry in selected[:max_results]:
            body = ""
            if len(rows) < MAX_HYDRATE:
                try:
                    body = self._text(entry["url"])
                except Exception:
                    body = ""  # the list record remains usable without the full text
            rows.append(self._cbet_row(entry, body))
        return rows

    def _extra(self, **values) -> dict:
        from ..cbat import TLS_STATUS, TRANSPORT
        extra = {"provider": "CBAT (IAU Central Bureau for Astronomical Telegrams)",
                 "publication_status": "bureau_circular_not_peer_reviewed",
                 "complete_archive": False, "transport": TRANSPORT, "tls_status": TLS_STATUS,
                 "transport_note": "The CBAT host completes no TLS handshake; content is "
                                   "retrieved over unencrypted HTTP and is not integrity-protected.",
                 "retrieved_at": now_utc_iso(), "content_trust": "untrusted_external"}
        extra.update(values)
        return extra

    def _cbet_row(self, entry, body) -> dict:
        summary = body or entry["title"]
        return normalize({"title": f"CBET {entry['cbet_number']}: {entry['title']}",
                          "summary": summary, "url": entry["url"],
                          "published": entry["issued"], "published_kind": "issued",
                          "category": "news",
                          "extra": self._extra(cbet_number=entry["cbet_number"],
                                               full_text_retrieved=bool(body),
                                               timestamp_semantics="cbet_issue_date_not_observation_time")},
                         {"name": self.name, "authority": self.authority,
                          "source_type": "api", "category": "news"})

    def _supernova_row(self, entry) -> dict:
        summary = (f"Recent supernova {entry['supernova']} reported by CBAT"
                   + (f" in {entry['host_galaxy']}" if entry.get("host_galaxy") else "")
                   + (f", discovery date {entry['discovery_date']}" if entry.get("discovery_date") else "")
                   + (f", magnitude {entry['magnitude']}" if entry.get("magnitude") is not None else "")
                   + (f", type {entry['type']}" if entry.get("type") else "") + ".")
        return normalize({"title": f"Supernova {entry['supernova']}", "summary": summary,
                          "url": entry["url"], "published": entry.get("discovery_date") or "",
                          "published_kind": "observed" if entry.get("discovery_date") else "unknown",
                          "category": "news",
                          "extra": self._extra(supernova=entry["supernova"],
                                               host_galaxy=entry.get("host_galaxy"),
                                               supernova_type=entry.get("type"),
                                               discovery_magnitude=entry.get("magnitude"),
                                               parsed_fields_note="Only fields matched by strict "
                                                                  "patterns are reported; the "
                                                                  "fixed-width list is not fully parsed.")},
                         {"name": self.name, "authority": self.authority,
                          "source_type": "api", "category": "news"})