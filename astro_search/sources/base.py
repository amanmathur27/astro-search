"""BaseSource abstract class — all sources inherit from this."""
from __future__ import annotations


class BaseSource:
    name: str = "base"
    source_type: str = "api"  # "rss" | "api" | "computed" | "local"
    authority: int = 2  # 1=community, 2=established, 3=institutional
    intents: list = []
    entities: list = ["*"]
    supports_location: bool = False
    timeout: int = 12
    fallback: str | None = None

    def report_error(self, kwargs):
        """Record a caught exception without leaking URLs, tokens or payloads."""
        import sys
        error = sys.exc_info()[1]
        sink = kwargs.get("_errors")
        if sink is not None:
            diagnostic = {"source": self.name, "error": type(error).__name__ if error else "invalid_payload"}
            if diagnostic not in sink:
                sink.append(diagnostic)


    def fetch(self, query: str, **kwargs) -> list[dict]:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True
