"""Full-article fetch (astro_fetch). Stdlib-ish + requests."""
from __future__ import annotations
import html
import re
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
TAG_RE = re.compile(r"<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", re.S | re.I)
TAG2_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def fetch_article(url: str) -> dict:
    if not url:
        return {"url": url, "title": "", "text": "", "word_count": 0, "fetch_ok": False, "error": "empty url"}
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        ctype = r.headers.get("content-type", "")
        if "html" not in ctype and "text" not in ctype and "xml" not in ctype and "rss" not in ctype:
            return {"url": url, "title": "", "text": "", "word_count": 0, "fetch_ok": False, "error": f"non-text {ctype}"}
        body = r.text
        m = re.search(r"<article[^>]*>(.*?)</article>", body, re.S | re.I) or re.search(r"<main[^>]*>(.*?)</main>", body, re.S | re.I)
        chunk = m.group(1) if m else body
        chunk = TAG_RE.sub(" ", chunk)
        title_m = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
        title = html.unescape(TAG2_RE.sub("", title_m.group(1)).strip()) if title_m else ""
        text = html.unescape(TAG2_RE.sub(" ", chunk))
        text = WS_RE.sub(" ", text).strip()
        words = text.split()
        if len(words) > 6000:
            text = " ".join(words[:6000])
        return {"url": url, "title": title, "text": text, "word_count": min(len(words), 6000), "fetch_ok": True, "error": None}
    except Exception as e:
        return {"url": url, "title": "", "text": "", "word_count": 0, "fetch_ok": False, "error": str(e)[:300]}
