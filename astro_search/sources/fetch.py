"""Full-article fetch (astro_fetch). Stdlib-ish + requests."""
from __future__ import annotations
import html
import re
import ipaddress
import socket
from urllib.parse import urlsplit, urljoin
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
TAG_RE = re.compile(r"<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", re.S | re.I)
TAG2_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


MAX_BYTES = 2 * 1024 * 1024


def validate_public_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username or parts.password:
        raise ValueError("public HTTP(S) URL required")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    addresses = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("nonpublic destination blocked")
    return url


def resolve_google_news_url(url: str, timeout: float = 5.0) -> str:
    """Resolve a Google News RSS redirect URL to the destination publisher URL."""
    if "news.google.com" not in url:
        return url
    try:
        import json
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        m = re.search(r'data-p="([^"]+)"', resp.text)
        if not m:
            return url
        data_p = m.group(1).replace("&quot;", '"')
        obj = json.loads(data_p.replace('%.@.', '["garturlreq",'))
        payload = {
            'f.req': json.dumps([[
                ['Fbv4je', json.dumps(obj[:-6] + obj[-2:]), 'null', 'generic']
            ]])
        }
        h2 = {
            'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'user-agent': HEADERS["User-Agent"]
        }
        r2 = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", headers=h2, data=payload, timeout=timeout)
        array_string = json.loads(r2.text.replace(")]}'", ""))[0][2]
        real_url = json.loads(array_string)[1]
        return real_url or url
    except Exception:
        return url


def _download(url, deadline=None):
    current = url
    if "news.google.com" in current:
        resolved = resolve_google_news_url(current, timeout=5 if deadline is None else max(0.01, min(5, deadline - time.monotonic())))
        if resolved and resolved != current:
            current = resolved
    # Disable automatic redirects: inspect each target before contacting it.
    for _ in range(6):
        import time
        if deadline is not None and time.monotonic() >= deadline:
            raise TimeoutError("article deadline exceeded")
        validate_public_url(current)
        timeout = 15 if deadline is None else max(0.01, min(15, deadline - time.monotonic()))
        with requests.get(current, headers=HEADERS, timeout=timeout, stream=True, allow_redirects=False) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                target = response.headers.get("location")
                if not target:
                    raise ValueError("redirect has no destination")
                current = urljoin(current, target)
                continue
            response.raise_for_status()
            ctype = response.headers.get("content-type", "").lower()
            if not any(kind in ctype for kind in ("text/", "html", "xml")):
                raise ValueError("non-text response")
            length = response.headers.get("content-length")
            if length and int(length) > MAX_BYTES:
                raise ValueError("response exceeds size limit")
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=16384):
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError("article deadline exceeded")
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("response exceeds size limit")
                chunks.append(chunk)
            return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace"), current
    raise ValueError("too many redirects")


def fetch_article(url: str, *, deadline=None) -> dict:
    if not url:
        return {"url": url, "title": "", "text": "", "word_count": 0, "fetch_ok": False, "error": "empty url"}
    try:
        body, final_url = _download(url) if deadline is None else _download(url, deadline=deadline)
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
        usable = len(words) >= 40
        from ..metadata import extract_metadata
        metadata = extract_metadata(body)
        from datetime import datetime, timezone
        return {"url": url, "final_url": final_url, "title": title, "text": text,
                "metadata": metadata, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "word_count": min(len(words), 6000), "fetch_ok": usable,
                "error": None if usable else "insufficient extracted text",
                "truncated": len(words) > 6000, "content_trust": "untrusted_external"}
    except Exception as e:
        return {"url": url, "title": "", "text": "", "word_count": 0, "fetch_ok": False, "error": str(e)[:300]}
