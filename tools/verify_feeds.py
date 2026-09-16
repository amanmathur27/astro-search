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
            feed = feedparser.parse(r.content)
            n = len(feed.entries)
            print(f"{'OK ' if n else 'EMPTY'} {f['name']}: {n} entries")
            ok += 1 if n else 0
            if not n: bad.append(f["name"])
        except Exception as e:
            print(f"FAIL {f['name']}: {e}")
            bad.append(f["name"])
    print(f"\n{ok}/{len(RSS_FEEDS)} healthy. Bad: {bad}")

if __name__ == "__main__":
    main()
