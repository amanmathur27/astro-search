"""Tests never use live HTTP, persistent user caches, or downloaded ephemerides."""
import pytest
import requests
from astro_search import core


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    def blocked(*args, **kwargs):
        raise RuntimeError("HTTP disabled in unit tests; provide a fixture")
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    monkeypatch.setattr(core, "SQLiteCache", lambda: None)
    monkeypatch.setenv("ASTRO_SKYFIELD_DIR", str(tmp_path / "skyfield"))
