"""NOAA SWPC — Kp, solar wind, alerts, aurora. No key, public domain."""
from __future__ import annotations
import requests
from .base import BaseSource
from ..normalizer import normalize

BASE = "https://services.swpc.noaa.gov"
TIMEOUT = 15


def _json(path: str):
    r = requests.get(f"{BASE}{path}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _text(path: str) -> str:
    r = requests.get(f"{BASE}{path}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def aurora_alert(kp: float, bz: float) -> str:
    if kp >= 7:
        return "Strong aurora likely. Visible at mid-latitudes."
    if kp >= 5:
        return "Moderate aurora activity. Visible at high latitudes."
    if kp >= 3 and bz < -5:
        return "Minor aurora possible at high latitudes."
    return "Quiet conditions. Aurora unlikely except at polar regions."


class NOAASource(BaseSource):
    name = "NOAA SWPC"
    source_type = "api"
    authority = 3
    intents = ["current_phenomenon", "celestial_event_lookup", "recent_news"]
    entities = ["solar"]
    timeout = 15

    def fetch(self, query: str, **kwargs) -> list[dict]:
        out: list[dict] = []
        try:
            kp_data = _json("/json/planetary_k_index_1m.json")
            last = [x for x in kp_data if isinstance(x, dict)][-10:]
            kp_now = next((x for x in reversed(last) if x.get("estimated_kp") not in (None, 0)), last[-1] if last else {})
            kp = float(kp_now.get("estimated_kp", 0) or 0)
        except Exception:
            kp, kp_now = 0.0, {}
        bz = 0.0
        try:
            mag = _json("/json/solar-wind/mag-7-day.json")
            if isinstance(mag, list) and len(mag) > 1 and isinstance(mag[-1], list) and len(mag[-1]) > 3:
                bz = float(mag[-1][3] or 0.0)
        except Exception:
            pass
        alert = aurora_alert(kp, bz)
        out.append(normalize({
            "title": f"Aurora / geomagnetic now: Kp {kp:.1f} — {alert}",
            "summary": f"Current estimated Kp {kp:.1f} (1-min SWPC). IMF Bz {bz:.1f} nT. {alert}"[:400],
            "url": "https://www.swpc.noaa.gov/products-and-data",
            "published": str((kp_now or {}).get("time_tag", "")),
            "category": "space_weather", "event_type": "aurora",
            "extra": {"kp": kp, "bz": bz, "alert": alert, "kp_sample": kp_now},
        }, {"name": "NOAA SWPC", "source_type": "api", "authority": 3, "category": "space_weather"}))
        try:
            alerts = _json("/products/alerts.json")
            items = alerts if isinstance(alerts, list) else alerts.get("alerts", [])
            for a in items[:5]:
                if isinstance(a, dict):
                    out.append(normalize({
                        "title": a.get("message", a.get("title", "SWPC alert")),
                        "summary": str(a.get("message", a))[:400],
                        "url": "https://www.swpc.noaa.gov/products/alerts",
                        "published": str(a.get("issue_datetime", a.get("time_tag", ""))),
                        "category": "space_weather", "extra": {"raw": a},
                    }, {"name": "NOAA SWPC", "source_type": "api", "authority": 3, "category": "space_weather"}))
        except Exception:
            pass
        try:
            txt = _text("/text/3-day-forecast.txt")[:800]
            out.append(normalize({
                "title": "NOAA 3-day space weather forecast",
                "summary": txt[:400], "url": "https://www.swpc.noaa.gov/",
                "published": "", "category": "space_weather", "extra": {"forecast": txt},
            }, {"name": "NOAA SWPC", "source_type": "api", "authority": 3, "category": "space_weather"}))
        except Exception:
            pass
        # GOES primary X-ray flux -> flare class (A/B/C/M/X)
        try:
            xray = _json("/json/goes/primary/xrays-7-day.json")
            last = [p for p in xray if isinstance(p, dict) and p.get("flux")] or []
            if not last and isinstance(xray, list) and xray and isinstance(xray[-1], list):
                pass  # unexpected shape; skip
            if last:
                flux = float(last[-1].get("flux", 0) or 0)
                cls = "A" if flux < 1e-7 else ("B" if flux < 1e-6 else ("C" if flux < 1e-5 else ("M" if flux < 1e-4 else "X")))
                out.append(normalize({
                    "title": f"Solar X-ray flux now: {flux:.1e} W/m² (class {cls})",
                    "summary": f"GOES primary X-ray {flux:.1e} W/m² ≈ {cls}-class. M/X = flare in progress."[:400],
                    "url": "https://www.swpc.noaa.gov/products/goes-x-ray-flux",
                    "published": str(last[-1].get("time_tag", "")), "category": "space_weather",
                    "extra": {"xray_flux": flux, "flare_class": cls},
                }, {"name": "NOAA SWPC", "source_type": "api", "authority": 3, "category": "space_weather"}))
        except Exception:
            pass
        # G-scale from planetary K index (G1 kp>=5 ... G5 kp>=9)
        try:
            pk = _json("/products/noaa-planetary-k-index.json")
            rows = pk if isinstance(pk, list) else pk.get("data", [])
            if rows:
                row = rows[-1] if isinstance(rows[-1], dict) else {}
                kp_v = float(row.get("kp_index", row.get("kp", 0)) or 0)
                g = 0 if kp_v < 5 else min(int(kp_v - 4), 5)
                out.append(normalize({
                    "title": f"Geomagnetic storm scale now: G{g} (Kp {kp_v:.0f})",
                    "summary": ("No storm" if g == 0 else f"G{g} storm conditions") + f" per NOAA planetary K-index."[:400],
                    "url": "https://www.swpc.noaa.gov/noaa-scales-explanation",
                    "published": str(row.get("time_tag", "")), "category": "space_weather",
                    "extra": {"g_scale": g, "kp": kp_v},
                }, {"name": "NOAA SWPC", "source_type": "api", "authority": 3, "category": "space_weather"}))
        except Exception:
            pass
        return out
