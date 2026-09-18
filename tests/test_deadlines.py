"""Deadline collection must not wait for a blocked adapter to finish."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from astro_search.core import AstroSearch
from astro_search.sources.base import BaseSource


def test_deadline_returns_without_joining_running_source():
    started, release = Event(), Event()

    class Slow(BaseSource):
        name = "Slow fixture"
        def fetch(self, query, **kwargs):
            started.set()
            release.wait(5)
            return []

    engine = AstroSearch()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(engine._fanout, [Slow()], "test", time.monotonic() + 0.15)
            assert started.wait(1)
            try:
                rows, errors = future.result(timeout=1)
                assert rows == []
                assert errors == [{"source": "Slow fixture", "error": "deadline_exceeded"}]
            finally:
                release.set()
    finally:
        release.set()


def test_exhausted_deadline_never_starts_source():
    class Source(BaseSource):
        name = "Unstarted"
        def fetch(self, query, **kwargs):
            raise AssertionError("must not run")
    rows, errors = AstroSearch()._fanout([Source()], "test", time.monotonic() - 1)
    assert not rows and errors[0]["error"] == "deadline_exceeded"


def test_source_failure_is_distinct_from_empty_results():
    class Broken(BaseSource):
        name = "Broken"
        def fetch(self, query, **kwargs):
            raise ValueError("sensitive request detail")
    rows, errors = AstroSearch()._fanout([Broken()], "test", time.monotonic() + 1)
    assert not rows and errors == [{"source": "Broken", "error": "ValueError"}]
