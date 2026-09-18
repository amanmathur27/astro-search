"""RSS health check — weekly cron. Never fails the build on one dead feed."""
import requests
import feedparser
import sys
sys.path.insert(0, ".")
from astro_search.sources.rss import RSS_FEEDS, HEADERS

def main():
    ok, bad = 0, []
    for f in RSS_FEEDS:
        try:
            r = requests.get(f["url"], headers=HEADERS, timeout=15)
            r.raise_for_status()
            feed = feedparser.parse(r.content)
            n = len(feed.entries)
            from astro_search.normalizer import freshness_hours, to_iso_utc
            dates = [to_iso_utc(e.get("published") or e.get("updated")) for e in feed.entries]
            age = freshness_hours(max(dates, default=""))
            healthy = bool(n) and age is not None and age <= 90 * 24
            print(f"{'OK' if healthy else 'REVIEW'} {f['name']}: HTTP {r.status_code}, {n} entries, newest_age_h={age}")
            ok += int(healthy)
            if not healthy:
                bad.append(f["name"])
        except Exception as e:
            print(f"FAIL {f['name']}: {e}")
            bad.append(f["name"])
    print(f"\n{ok}/{len(RSS_FEEDS)} healthy. Bad: {bad}")

if __name__ == "__main__":
    main()
