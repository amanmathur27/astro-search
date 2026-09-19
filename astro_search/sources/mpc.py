"""MPC source: recent MPECs, MPEC element blocks, and bounded MPC-80 astrometry.

Only explicitly requested designations are sent to the astrometry API; the
recent-MPEC list is a bounded 100-entry view, not the full archive.
"""
from __future__ import annotations
import json
import requests
from .base import BaseSource
from ..normalizer import normalize
from ..timeparse import now_utc_iso

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html, application/json;q=0.9, */*;q=0.8",
}


class MPCSource(BaseSource):
    name = "Minor Planet Center"
    source_type = "api"
    authority = 3
    intents = ["mpec_lookup"]
    entities = ["*"]
    timeout = 20

    def _get(self, url: str, **kw) -> requests.Response:
        merged = {**HEADERS, **kw.pop("headers", {})}
        response = requests.get(url, headers=merged, timeout=self.timeout, **kw)
        response.raise_for_status()
        return response

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
        from ..mpec import (LIST_URL, OBS_API, list_matches, mpec_request,
                            parse_elements, parse_mpec_list, parse_observations)
        request = mpec_request(query)
        if request["url"]:
            page = self._get(request["url"]).text
            elements = parse_elements(page)
            return [self._mpec_row(request["identifier"], request["url"], elements)]
        if request["designation"] and request["wants_observations"]:
            payload = self._get(OBS_API, headers={**HEADERS, "Content-Type": "application/json"},
                                data=json.dumps({"desigs": [request["designation"]],
                                                 "output_format": ["OBS80"]})).json()
            # The API returns [<data>, <status_code>]; only the first element carries records.
            if (not isinstance(payload, list) or not payload
                    or not isinstance(payload[0], dict)):
                raise ValueError("unexpected astrometry payload shape")
            if isinstance(payload[0], dict) and "OBS80" not in payload[0]:
                raise ValueError("astrometry payload missing OBS80 records")
            parsed = parse_observations(payload[0].get("OBS80") or "")
            if not parsed["parsed"]:
                raise ValueError("no conforming MPC-80 observations parsed")
            return [self._observation_row(request["designation"], parsed)]
        entries = parse_mpec_list(self._get(LIST_URL).text)
        if not entries:
            raise ValueError("no MPECs parsed from the recent list")
        selected = [e for e in entries if list_matches(query, e["identifier"], e["designations"])]
        return [self._mpec_row(e["identifier"], e["url"], None, e) for e in selected[:max_results]]

    def _mpec_row(self, identifier, url, elements, entry=None) -> dict:
        entry = entry or {}
        designations = entry.get("designations") or (
            [elements["designation"]] if elements and elements.get("designation") else [])
        subject = ", ".join(designations) or identifier
        summary = f"MPEC {identifier} covers {subject}."
        if elements:
            summary += " Orbital elements parsed: " + ", ".join(sorted(elements["fields"])) + "."
        extra = {"mpec_identifier": identifier, "provider": "Minor Planet Center (IAU)",
                 "publication_status": "bureau_circular_not_peer_reviewed",
                 "complete_archive": False, "designations": designations,
                 "elements": elements, "uncertainty": None,
                 "timestamp_semantics": "mpec_issue_date_not_observation_time",
                 "retrieved_at": now_utc_iso(), "content_trust": "untrusted_external",
                 "transport": "https"}
        return normalize({"title": f"MPEC {identifier}: {subject}", "summary": summary,
                          "url": url, "published": entry.get("issued") or "",
                          "published_kind": "issued" if entry.get("issued") else "unknown",
                          "category": "news", "extra": extra},
                         {"name": self.name, "authority": self.authority,
                          "source_type": "api", "category": "news"})

    def _observation_row(self, designation, parsed) -> dict:
        first = parsed["observations"][0]
        summary = (f"{parsed['parsed']} MPC-80 astrometric observations parsed for {designation}; "
                   f"first at {first['date_utc']} ({first['ra_hms']} {first['dec_dms']}). "
                   f"{parsed['skipped']} non-conforming line(s) skipped.")
        extra = {"designation": designation, "provider": "Minor Planet Center (IAU)",
                 "archive_record": {"catalog": "MPC astrometry (MPC-80)", "record_id": designation,
                                    "fields": {"observations": parsed["parsed"],
                                               "skipped": parsed["skipped"],
                                               "format": parsed["format"]},
                                    "uncertainty": None,
                                    "uncertainty_note": parsed["uncertainty_note"],
                                    "reference": "Minor Planet Center astrometry database"},
                 "observations": parsed["observations"], "parsed": parsed["parsed"],
                 "skipped": parsed["skipped"], "truncated": parsed["truncated"],
                 "uncertainty_note": parsed["uncertainty_note"], "time_note": parsed["time_note"],
                 "publication_status": "archive_record_not_independently_verified",
                 "retrieved_at": now_utc_iso(), "content_trust": "untrusted_external",
                 "transport": "https"}
        return normalize({"title": f"MPC astrometry for {designation}", "summary": summary,
                          "url": "https://www.minorplanetcenter.net/iau/ECS/MPCAT/MPCAT.html",
                          "published": first["date_utc"], "published_kind": "observed",
                          "category": "news", "extra": extra},
                         {"name": self.name, "authority": self.authority,
                          "source_type": "api", "category": "news"})