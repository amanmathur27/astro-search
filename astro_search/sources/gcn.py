"""GCN Circulars via the modern machine-readable endpoints (verified 2026-09-18).

The legacy GCN archive is frozen and its RSS path 404s; ``/circulars`` and the
per-circular ``.json`` export are the supported surfaces. Circulars remain rapid
reports: this source never promotes them to verified evidence.
"""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize
from ..timeparse import now_utc_iso

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}
MAX_HYDRATE = 3


class GCNSource(BaseSource):
    name = "GCN Circulars"
    source_type = "api"
    authority = 3
    intents = ["circular_lookup"]
    entities = ["*"]
    list_url = "https://gcn.nasa.gov/circulars"
    circular_url = "https://gcn.nasa.gov/circulars/{ident}.json"
    timeout = 15

    def _body(self, url: str) -> bytes:
        response = requests.get(url, headers=HEADERS, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def _json(self, url: str):
        import json
        return json.loads(self._body(url).decode("utf-8", errors="replace"))

    def fetch(self, query: str, **kwargs) -> list[dict]:
        try:
            max_results = min(max(int(kwargs.get("max_results", 8)), 1), 20)
        except (TypeError, ValueError):
            max_results = 8
        try:
            records = self._collect(query, max_results)
        except Exception:
            self.report_error(kwargs)
            return []
        return [self._row(record) for record in records]

    def _collect(self, query, max_results) -> list[dict]:
        from ..gcn import circular_id, parse_circular, parse_list, report_matches
        ident = circular_id(query)
        if ident:
            record = parse_circular(self._json(self.circular_url.format(ident=ident)))
            if not record or record["circular_id"] != ident:
                raise ValueError("circular payload missing or mismatched")
            return [record]
        entries = parse_list(self._body(self.list_url).decode("utf-8", errors="replace"))
        if not entries:
            raise ValueError("no circulars parsed from the list page")
        selected = [e for e in entries if report_matches(query, e["subject"])]
        records = []
        for entry in selected[:min(MAX_HYDRATE, max_results)]:
            record = None
            try:
                record = parse_circular(self._json(self.circular_url.format(ident=entry["circular_id"])))
            except Exception:
                # Optional body/date hydration only; the list record stays usable.
                record = None
            records.append(record or {"circular_id": entry["circular_id"], "subject": entry["subject"],
                                      "body": "", "published": "", "bibcode": None,
                                      "event_id": None, "submitter": None, "url": entry["url"]})
        return records

    def _row(self, record: dict) -> dict:
        summary = record.get("body") or record["subject"]
        return normalize({
            "title": record["subject"], "summary": summary, "url": record["url"],
            "published": record.get("published", ""),
            "published_kind": "issued" if record.get("published") else "unknown",
            "category": "news",
            "authors": [record["submitter"]] if record.get("submitter") else [],
            "extra": {"circular_id": record["circular_id"], "bibcode": record.get("bibcode"),
                      "event_id": record.get("event_id"), "provider": "GCN (NASA)",
                      "publication_status": "circular_not_peer_reviewed",
                      "complete_archive": False, "machine_readable": True,
                      "timestamp_semantics": "circular_issued_not_event_time",
                      "retrieved_at": now_utc_iso(), "content_trust": "untrusted_external",
                      "transport": "https"},
        }, {"name": self.name, "authority": self.authority, "source_type": "api", "category": "news"})