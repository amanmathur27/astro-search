"""Open Notify: ISS position + crew. No key."""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize


class ISSSource(BaseSource):
    name = "Open Notify ISS"
    source_type = "api"
    authority = 2
    intents = ["mission_status"]
    entities = ["missions"]
    timeout = 10

    def fetch(self, query: str, **kwargs) -> list[dict]:
        out: list[dict] = []
        q = (query or "").lower()
        try:
            r = requests.get("http://api.open-notify.org/iss-now.json", timeout=self.timeout)
            if r.ok:
                d = r.json()
                pos = d.get("iss_position", {})
                out.append(normalize({
                    "title": f"ISS now: {pos.get('latitude')}, {pos.get('longitude')}",
                    "summary": f"ISS at lat {pos.get('latitude')}, lon {pos.get('longitude')}."[:400],
                    "url": "http://open-notify.org/Open-Notify-API/ISS-Location-Now/",
                    "published": "", "category": "news",
                    "extra": {"position": pos, "timestamp": d.get("timestamp")},
                }, {"name": "Open Notify ISS", "source_type": "api", "authority": 2, "category": "news"}))
            if "crew" in q or "who" in q or "space" in q:
                r2 = requests.get("http://api.open-notify.org/astros.json", timeout=self.timeout)
                if r2.ok:
                    d2 = r2.json()
                    out.append(normalize({
                        "title": f"{d2.get('number', '?')} humans in space now",
                        "summary": ", ".join(p.get("name", "") for p in d2.get("people", []))[:400],
                        "url": "http://open-notify.org/", "published": "",
                        "category": "news", "extra": {"people": d2.get("people", [])},
                    }, {"name": "Open Notify ISS", "source_type": "api", "authority": 2, "category": "news"}))
        except Exception:
            pass
        return out
