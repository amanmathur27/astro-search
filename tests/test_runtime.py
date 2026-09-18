"""Offline admission, cache and backoff regressions."""
from threading import Event
import pytest
from astro_search import runtime
from astro_search.core import AstroSearch
from astro_search.sources.base import BaseSource


class Fixture(BaseSource):
    name = "fixture"
    calls = 0

    def fetch(self, query, **kwargs):
        self.calls += 1
        return [{"title": query, "extra": {"lat": kwargs.get("lat")}}]


def test_source_cache_isolated_and_copied():
    runner, source = runtime.SourceRuntime(), Fixture()
    first = runner.fetch(source, "moon", lat=1, now_utc="2026-01-01T00:00:00Z")
    first[0]["extra"]["lat"] = 99
    assert runner.fetch(source, "moon", lat=1, now_utc="2026-01-01T00:00:00Z")[0]["extra"]["lat"] == 1
    assert source.calls == 1
    runner.fetch(source, "moon", lat=2, now_utc="2026-01-01T00:00:00Z")
    runner.fetch(source, "moon", lat=2, now_utc="2026-01-02T00:00:00Z")
    assert source.calls == 3


def test_source_failure_backoff_and_recovery(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(runtime.time, "monotonic", lambda: clock[0])
    runner, source = runtime.SourceRuntime(), Fixture()
    good_fetch = source.fetch
    def broken(*args, **kwargs):
        raise ValueError("sensitive details")
    source.fetch = broken
    with pytest.raises(ValueError):
        runner.fetch(source, "moon")
    errors = []
    assert runner.fetch(source, "moon", _errors=errors) == []
    assert errors == [{"source": "fixture", "error": "source_backoff"}]
    source.fetch = good_fetch
    clock[0] += 2
    assert runner.fetch(source, "moon")
    assert source.calls == 1


def test_partial_errors_not_cached():
    class Partial(Fixture):
        def fetch(self, query, **kwargs):
            kwargs["_errors"].append({"source": self.name, "error": "invalid_payload"})
            return [{"title": "partial"}]
    runner, source = runtime.SourceRuntime(), Partial()
    errors = []
    assert runner.fetch(source, "moon", _errors=errors)
    assert errors[0]["error"] == "invalid_payload"
    assert not runner.cache._store
    assert runner.fetch(source, "moon", _errors=[]) == []


def test_executor_capacity_cancel_and_reuse():
    executor = runtime.BoundedExecutor(workers=1, capacity=2)
    entered, release = Event(), Event()
    def slow():
        entered.set()
        release.wait(3)
    try:
        running = executor.submit(slow)
        assert entered.wait(1)
        queued = executor.submit(lambda: 2)
        assert executor.submit(lambda: 3) is None
        assert queued.cancel()
        replacement = executor.submit(lambda: 4)
        assert replacement is not None
        release.set()
        running.result(timeout=1)
        assert replacement.result(timeout=1) == 4
    finally:
        release.set()
        executor.shutdown()


def test_fanout_reports_capacity(monkeypatch):
    class Full:
        def submit(self, *args, **kwargs):
            return None
    monkeypatch.setattr(runtime, "EXECUTOR", Full())
    rows, errors = AstroSearch()._fanout([Fixture()], "moon", runtime.time.monotonic() + 1)
    assert rows == [] and errors == [{"source": "fixture", "error": "capacity_exceeded"}]
