"""NOAA SWPC — Kp, solar wind, alerts, aurora. No key, public domain."""
from __future__ import annotations
import math
import requests
from ..normalizer import to_iso_utc
from ..timeparse import reference_time
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


def aurora_alert(kp: float | None, bz: float | None) -> str:
    if kp is None:
        return "Kp unavailable — aurora conditions unknown right now."
    if kp >= 5:
        return "Elevated geomagnetic activity. Local aurora visibility is not determined by Kp alone."
    if bz is None:
        return "Low geomagnetic activity by Kp; solar-wind Bz unavailable. Local visibility unknown."
    if kp >= 3 and bz < -5:
        return "Southward Bz may support aurora; local visibility requires additional conditions."
    return "Quiet conditions by Kp and Bz; local aurora visibility is not guaranteed."


def _number(value):
    try:
        if value is None or isinstance(value, bool) or value == "":
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _as_kp(value) -> float | None:
    number = _number(value)
    return number if number is not None and 0 <= number <= 9 else None


def _fresh_sample(row, now, max_age_hours):
    # Require a full observation date and time; dateutil must not guess missing parts.
    import re
    raw = row.get("time_tag")
    if not isinstance(raw, str) or not re.match(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}", raw):
        return False, None
    stamp = to_iso_utc(raw)
    if not stamp:
        return False, None
    age = (reference_time(now) - reference_time(stamp)).total_seconds() / 3600
    return 0 <= age <= max_age_hours, age



def _last_row(payload) -> dict:
    """Latest record from dict-list OR columnar (fields + data rows) JSON."""
    if isinstance(payload, dict):
        fields, rows = payload.get("fields"), payload.get("data")
        if isinstance(fields, list) and isinstance(rows, list) and rows:
            if not all(isinstance(f, str) for f in fields) or len(set(fields)) != len(fields):
                return {}
            last = rows[-1]
            if isinstance(last, dict):
                return last
            return dict(zip(fields, last)) if isinstance(last, list) and len(last) == len(fields) else {}
        if isinstance(rows, list) and rows:  # {"data": [...]} without field names
            return _last_row(rows)
        return payload
    if isinstance(payload, list) and payload:
        last = payload[-1]
        if isinstance(last, dict):
            return last
        if isinstance(last, list):  # columnar w/ header list
            header = payload[0]
            if (len(payload) > 1 and isinstance(header, list)
                    and all(isinstance(c, str) for c in header)
                    and len(set(header)) == len(header) and len(last) == len(header)):
                return dict(zip(header, last))
            return {}
    return {}


def _records(payload):
    """Decode supported tables without relying on provider row order."""
    if isinstance(payload, dict):
        if "fields" in payload:
            return _records([payload["fields"]] + payload["data"]) if isinstance(payload.get("data"), list) else []
        return _records(payload["data"]) if isinstance(payload.get("data"), list) else [payload]
    if not isinstance(payload, list) or not payload:
        return []
    if isinstance(payload[0], list):
        header = payload[0]
        if not header or not all(isinstance(x, str) for x in header) or len(set(header)) != len(header):
            return []
        return [dict(zip(header, row)) for row in payload[1:]
                if isinstance(row, list) and len(row) == len(header)]
    return [row for row in payload if isinstance(row, dict)]


def _latest_observation(payload, now):
    eligible = []
    for row in _records(payload):
        _, age = _fresh_sample(row, now, float("inf"))
        if age is not None and age >= 0:
            eligible.append((age, row))
    return min(eligible, key=lambda pair: pair[0])[1] if eligible else {}


def _forecast_issue(text):
    import re
    from datetime import datetime, timezone
    if not isinstance(text, str):
        return None
    match = re.search(r"^:Issued:\s*(\d{4}) ([A-Za-z]{3}) (\d{1,2}) (\d{4}) UTC\s*$", text, re.M)
    if not match:
        return None
    try:
        months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
        year, month, day, clock = match.groups()
        return datetime(int(year), months.index(month.title()) + 1, int(day),
                        int(clock[:2]), int(clock[2:]), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None



def kp_from_1m(payload) -> tuple[float | None, dict]:
    """(kp, sample) from planetary_k_index_1m.json. None = data unavailable."""
    if not isinstance(payload, list):
        return None, {}
    samples = [x for x in payload if isinstance(x, dict)]
    for sample in reversed(samples[-10:]):
        kp = _as_kp(sample.get("estimated_kp"))
        if kp is not None:  # zeros are real measurements — keep them
            return kp, sample
    return None, {}


def g_scale_from_kp(kp: float | None) -> int | None:
    """G0–G5 from Kp; None propagates (unknown, not quiet)."""
    kp = _as_kp(kp)
    if kp is None:
        return None
    return 0 if kp < 5 else min(int(kp - 4), 5)


class NOAASource(BaseSource):
    name = "NOAA SWPC"
    source_type = "api"
    authority = 3
    intents = ["current_phenomenon", "celestial_event_lookup", "recent_news"]
    entities = ["solar"]
    timeout = 15

    def fetch(self, query: str, **kwargs) -> list[dict]:
        out: list[dict] = []
        now = reference_time(kwargs.get("now_utc"))
        try:
            kp_now = _latest_observation(_json("/json/planetary_k_index_1m.json"), now)
            kp = _as_kp(kp_now.get("estimated_kp"))
        except Exception:
            self.report_error(kwargs)
            kp, kp_now = None, {}
        kp_fresh, kp_age = _fresh_sample(kp_now, now, 3)
        if not kp_fresh:
            kp = None
        bz = None
        try:
            mag = _latest_observation(_json("/json/solar-wind/mag-7-day.json"), now)
            if _fresh_sample(mag, now, 1)[0]:
                bz = _number(mag.get("bz_gsm"))
                # Conservative application sanity bound, not a calibrated instrument limit.
                if bz is not None and abs(bz) > 1000:
                    bz = None
        except Exception:
            self.report_error(kwargs)
            pass
        bz_label = f"{bz:.1f} nT" if bz is not None else "unavailable"
        alert = aurora_alert(kp, bz)
        if kp is None:
            title = "Aurora / geomagnetic now: Kp unavailable — aurora conditions unknown"
            summary = (f"Current Kp could not be read from SWPC 1-min feed "
                       f"(data unavailable, not zero). IMF Bz {bz_label}. {alert}")[:400]
        else:
            title = f"Aurora / geomagnetic now: Kp {kp:.1f} — {alert}"
            summary = f"Current estimated Kp {kp:.1f} (1-min SWPC). IMF Bz {bz_label}. {alert}"[:400]
        out.append(normalize({
            "title": title, "summary": summary,
            "url": "https://www.swpc.noaa.gov/products-and-data",
            "published": str((kp_now or {}).get("time_tag", "")),
            "category": "space_weather", "event_type": "aurora",
            "extra": {"kp": kp, "bz": bz, "alert": alert, "kp_sample": kp_now,
                      "kp_available": kp is not None, "bz_available": bz is not None,
                      "stale": kp_age is not None and kp_age > 3, "observation_age_h": kp_age},
        }, {"name": "NOAA SWPC", "source_type": "api", "authority": 3, "category": "space_weather"}))
        try:
            alerts = _json("/products/alerts.json")
            items = alerts if isinstance(alerts, list) else alerts.get("alerts", []) if isinstance(alerts, dict) else []
            items = [a for a in items if isinstance(a, dict)
                     and isinstance(a.get("message"), str) and a["message"].strip()
                     and _fresh_sample({"time_tag": a.get("issue_datetime") or a.get("time_tag")}, now, 72)[0]]
            items.sort(key=lambda a: to_iso_utc(a.get("issue_datetime") or a.get("time_tag")), reverse=True)
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
            self.report_error(kwargs)
            pass
        try:
            txt = _text("/text/3-day-forecast.txt")
            issued = _forecast_issue(txt)
            if not _fresh_sample({"time_tag": issued}, now, 36)[0]:
                raise ValueError("Forecast issue time missing, stale or future-dated")
            txt = txt[:800]
            out.append(normalize({
                "title": "NOAA 3-day space weather forecast",
                "summary": txt[:400], "url": "https://www.swpc.noaa.gov/",
                "published": issued, "category": "space_weather", "extra": {"forecast": txt, "issued_at": issued, "validity_status": "recent_issue_not_verified_forecast_horizon"},
            }, {"name": "NOAA SWPC", "source_type": "api", "authority": 3, "category": "space_weather"}))
        except Exception:
            self.report_error(kwargs)
            pass
        # GOES primary X-ray flux -> flare class (A/B/C/M/X)
        try:
            xray = _json("/json/goes/primary/xrays-7-day.json")
            last = [p for p in xray if isinstance(p, dict)
                    and p.get("energy") == "0.1-0.8nm"
                    and _number(p.get("flux")) is not None
                    and 0 < _number(p.get("flux")) <= 0.01
                    and _fresh_sample(p, now, 1)[0]] if isinstance(xray, list) else []
            last.sort(key=lambda p: to_iso_utc(p.get("time_tag")))
            if last:
                flux = float(last[-1]["flux"])
                cls = "A" if flux < 1e-7 else ("B" if flux < 1e-6 else ("C" if flux < 1e-5 else ("M" if flux < 1e-4 else "X")))
                out.append(normalize({
                    "title": f"Solar X-ray flux now: {flux:.1e} W/m² (class {cls})",
                    "summary": f"GOES 0.1–0.8 nm X-ray flux {flux:.1e} W/m² ({cls}-class flux level); not a flare-event detection."[:400],
                    "url": "https://www.swpc.noaa.gov/products/goes-x-ray-flux",
                    "published": str(last[-1].get("time_tag", "")), "category": "space_weather",
                    "extra": {"xray_flux": flux, "flare_class": cls, "energy": "0.1-0.8nm"},
                }, {"name": "NOAA SWPC", "source_type": "api", "authority": 3, "category": "space_weather"}))
        except Exception:
            self.report_error(kwargs)
            pass
        # G-scale from planetary K index (G1 kp>=5 ... G5 kp>=9)
        try:
            pk = _json("/products/noaa-planetary-k-index.json")
            row = _latest_observation(pk, now)
            kp_v = None
            if isinstance(row, dict):
                for key in ("kp_index", "kp", "Kp"):
                    if key in row:
                        kp_v = _as_kp(row.get(key))
                        break
            if kp_v is not None and _fresh_sample(row, now, 6)[0]:
                g = g_scale_from_kp(kp_v)
                out.append(normalize({
                    "title": f"Geomagnetic storm scale now: G{g} (Kp {kp_v:.0f})",
                    "summary": (f"{'No storm' if g == 0 else f'G{g} storm conditions'} "
                                f"per NOAA planetary K-index.")[:400],
                    "url": "https://www.swpc.noaa.gov/noaa-scales-explanation",
                    "published": str(row.get("time_tag", "")), "category": "space_weather",
                    "extra": {"g_scale": g, "kp": kp_v},
                }, {"name": "NOAA SWPC", "source_type": "api", "authority": 3, "category": "space_weather"}))
        except Exception:
            self.report_error(kwargs)
            pass
        return out
