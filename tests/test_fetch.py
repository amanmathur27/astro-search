"""Defensive fetch checks without contacting any external host."""
import socket
import pytest
from astro_search.sources import fetch


class Response:
    status_code = 200
    encoding = "utf-8"

    def __init__(self, body=b"", headers=None, status=200):
        self.body = body
        self.headers = headers or {"content-type": "text/html"}
        self.status_code = status
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield self.body


@pytest.fixture
def public_dns(monkeypatch):
    monkeypatch.setattr(fetch.socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))])


@pytest.mark.parametrize("url", ["file:///local", "ftp://example.org", "https://user:password@example.org"])
def test_invalid_url_rejected(url):
    assert not fetch.fetch_article(url)["fetch_ok"]


def test_nonpublic_dns_rejected_before_http(monkeypatch):
    monkeypatch.setattr(fetch.socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))])
    def forbidden(*a, **k):
        pytest.fail("must not contact nonpublic destination")
    monkeypatch.setattr(fetch.requests, "get", forbidden)
    assert "nonpublic" in fetch.fetch_article("https://example.org")["error"]


def test_redirect_checked_before_second_request(monkeypatch, public_dns):
    seen = []
    def validate(url):
        seen.append(url)
        if url.endswith("/blocked"):
            raise ValueError("blocked destination")
    monkeypatch.setattr(fetch, "validate_public_url", validate)
    response = Response(headers={"location": "/blocked"}, status=302)
    calls = []
    def get(url, **kw):
        calls.append(url)
        assert kw["allow_redirects"] is False
        return response
    monkeypatch.setattr(fetch.requests, "get", get)
    assert not fetch.fetch_article("https://example.org/start")["fetch_ok"]
    assert len(calls) == 1 and len(seen) == 2 and response.closed


@pytest.mark.parametrize("body,usable", [(b"<article>short</article>", False),
    (b"<article>" + b"astronomy " * 50 + b"</article>", True)])
def test_extraction_quality(monkeypatch, public_dns, body, usable):
    response = Response(body)
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: response)
    result = fetch.fetch_article("https://example.org/article")
    assert result["fetch_ok"] is usable
    assert result["content_trust"] == "untrusted_external"
    assert response.closed


def test_stream_limit_closes_response(monkeypatch, public_dns):
    monkeypatch.setattr(fetch, "MAX_BYTES", 20)
    response = Response(b"x" * 21)
    monkeypatch.setattr(fetch.requests, "get", lambda *a, **k: response)
    result = fetch.fetch_article("https://example.org/article")
    assert not result["fetch_ok"] and "size limit" in result["error"]
    assert response.closed
