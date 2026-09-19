"""
Interactive test runner for AstroSearch search engine queries.
"""
from astro_search import AstroSearch
import textwrap

engine = AstroSearch()

test_queries = [
    ("1. Specific Publisher Query (Space.com)", "astronomy content posted in space.com today"),
    ("2. Multi-Publisher Query (Space.com & Phys.org)", "give me all the latest articles published in space.com or phys.org website"),
    ("3. General Latest Discoveries", "find me most latest and recent discoveries in the field of astronomy or space science"),
    ("4. Celestial Event Lookup", "when is the next solar eclipse visible from India"),
    ("5. Real-Time Space Weather", "aurora forecast and Kp index right now"),
]

for label, q in test_queries:
    print("=" * 80)
    print(f"TEST: {label}")
    print(f"QUERY: \"{q}\"")
    print("=" * 80)
    res = engine.search(q, max_results=5)
    print(f"Intent Detected: {res.get('intent')}")
    print(f"Total Results Count: {res.get('count')}")
    print("\nTop Results:")
    for i, r in enumerate(res.get("results", []), 1):
        title = r.get("title", "")
        source = r.get("source", "")
        url = r.get("url", "")
        pub = r.get("published", "N/A")
        summary = textwrap.shorten(r.get("summary", ""), width=120, placeholder="...")
        print(f"  {i}. [{source}] {title}")
        print(f"     URL: {url}")
        print(f"     Date: {pub}")
        print(f"     Summary: {summary}\n")
