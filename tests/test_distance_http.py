"""Exercise the actual demo HTTP handler, not a mocked search response."""
import json
from pathlib import Path
import runpy
from threading import Thread
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler


def test_live_http_sun_distance():
    import pytest
    pytest.importorskip("ephem")
    if not (Path(__file__).resolve().parents[1] / "local_demo" / "server.py").is_file():
        pytest.skip("Temporary local demo is not present in this checkout")
    root = Path(__file__).resolve().parents[1]
    demo = runpy.run_path(str(root / "local_demo" / "server.py"))
    server = demo["ThreadingHTTPServer"](("127.0.0.1", 0), demo["Handler"])
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        query = urlencode({"q": "how far is sun from earth", "now_utc": "2026-09-17T12:00:00Z"})
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{server.server_port}/api/search?{query}", timeout=10) as response:
            result = json.load(response)
        assert result["answer_status"] == "answered", result
        assert result["answer"]["method"] == "computed"
        assert result["answer"]["unit"] == "km"
        assert 145_000_000 < result["answer"]["value"] < 153_000_000
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
