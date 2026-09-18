"""Crossref registration metadata as an archive record for an explicit DOI."""
from __future__ import annotations
import os
import requests
from .base import BaseSource
from ..doi import CROSSREF, extract_doi, record_to_archive
from ..normalizer import normalize
from ..timeparse import now_utc_iso

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; astro-search/2.1; +https://github.com/amanmathur27/astro-search)",
    "Accept": "application/json",
}


class DOISource(BaseSource):
    name = "Crossref"
    source_type = "api"
    authority = 3
    intents = ["fact_lookup"]
    entities = ["*"]
    timeout = 15

    def fetch(self, query: str, **kwargs) -> list[dict]:
        doi = extract_doi(query)
        if not doi:
            return []
        text, error = self._record(doi)
        if error:
            # Diagnostics only for transport/parse failures; an unregistered DOI is
            # a genuine not-found and must not be reported as a failed retrieval.
            if error != "not_registered":
                self.report_error(kwargs)
            return []
        archive = record_to_archive(text, doi)
        if not archive:
            self.report_error(kwargs)
            return []
        return [normalize({"title": archive["quote"], "summary": archive["quote"],
                           "url": f"https://doi.org/{archive['record_id']}",
                           "published": archive.get("issued") or "", "category": "papers",
                           "extra": {"archive_record": archive, "doi": archive["record_id"],
                                     "transport": "https", "content_trust": "untrusted_external",
                                     "retrieved_at": now_utc_iso()}},
                          {"name": self.name, "authority": self.authority,
                           "source_type": "api", "category": "papers"})]

    def _record(self, doi: str) -> tuple[dict | None, str | None]:
        """Return (message, error); 'not_registered' is not a transport failure."""
        params = {}
        mailto = os.environ.get("ASTRO_CROSSREF_MAILTO", "").strip()
        if mailto:
            params["mailto"] = mailto
        try:
            response = requests.get(CROSSREF.format(doi=requests.utils.quote(doi, safe="")),
                                    headers=HEADERS, timeout=self.timeout, params=params or None)
            if response.status_code == 404:
                return None, "not_registered"
            if response.status_code != 200:
                return None, "http_error"
            payload = response.json()
        except Exception:
            return None, "transport_error"
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return None, "malformed_payload"
        message = payload.get("message")
        return (message, None) if isinstance(message, dict) else (None, "malformed_payload")