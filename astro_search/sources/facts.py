"""Bounded primary mission-document retrieval for precision factual queries.

A small seed registry, not a web index. No numeric facts are hard-coded. Failures
are diagnostics, never grounds for substituting feed articles or snippets.
"""
from .base import BaseSource
from .fetch import fetch_article
from ..normalizer import normalize
from ..timeparse import now_utc_iso

DOCUMENTS = {
    "roman": "https://roman.gsfc.nasa.gov/science/observatory.html",
    "webb": "https://science.nasa.gov/mission/webb/",
    "hubble": "https://science.nasa.gov/mission/hubble/",
}


class MissionFactsSource(BaseSource):
    name = "Mission specifications"
    authority = 3
    intents = ["fact_lookup"]
    entities = ["*"]

    def fetch(self, query, **kwargs):
        spec = kwargs.get("interpretation") or {}
        url = DOCUMENTS.get(spec.get("subject_id"))
        if not url:
            return []
        article = fetch_article(url)
        if not article.get("fetch_ok"):
            # Do not include external exception strings/URLs in diagnostics.
            self.report_error(kwargs)
            return []
        return [normalize({
            "title": article.get("title", ""), "summary": article.get("text", ""),
            "metadata": article.get("metadata", {}),
            "url": article.get("final_url", url), "category": "all",
            "extra": {"document_text": article.get("text", ""),
                      "document_url": article.get("final_url", url),
                      "document_fetch_ok": True,
                      "document_truncated": article.get("truncated", False),
                      "retrieved_at": now_utc_iso(),
                      "content_trust": "untrusted_external"},
        }, {"name": self.name, "authority": self.authority, "source_type": "api"})]
