"""Shared validation for Python and tool entry points."""
import math
from .timeparse import timezone_for

CATEGORIES = {"all", "news", "discoveries", "events", "papers", "space_weather"}


def observer(lat, lon, tz):
    timezone_for(tz)
    if (lat is None) != (lon is None):
        raise ValueError("lat and lon must be supplied together")
    if lat is None:
        return None, None
    values = []
    for name, value, bound in (("lat", lat, 90), ("lon", lon, 180)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite number")
        if not math.isfinite(value) or not -bound <= value <= bound:
            raise ValueError(f"{name} must be between {-bound} and {bound}")
        values.append(float(value))
    return tuple(values)


def calendar_year(value, default):
    if value is None:
        value = default
    if isinstance(value, bool) or not isinstance(value, int) or not 1900 <= value <= 2100:
        raise ValueError("year must be an integer between 1900 and 2100")
    return value


def search_inputs(query, category, trends, edition, topic, mode="standard", since_date=None):
    if not isinstance(query, str) or len(query) > 4000:
        raise ValueError("query must be a string of at most 4000 characters")
    if not isinstance(category, str) or category not in CATEGORIES:
        raise ValueError("Unknown search category")
    if not isinstance(trends, bool):
        raise ValueError("trends must be a boolean")
    if edition is not None:
        import re
        if not isinstance(edition, str) or not re.fullmatch(r"[A-Za-z]{2}(?::[A-Za-z]{2})?", edition):
            raise ValueError("edition must be a country code or country:language")
    if topic is not None:
        from .sources.arxiv import CATS
        if not isinstance(topic, str) or topic not in CATS:
            raise ValueError("Unknown paper topic")
    if mode not in ("standard", "evidence"):
        raise ValueError("mode must be 'standard' or 'evidence'")
    if since_date:
        import re
        if not isinstance(since_date, str) or not re.match(r"^\d{4}-\d{2}-\d{2}", since_date):
            raise ValueError("since_date must be in YYYY-MM-DD format")
