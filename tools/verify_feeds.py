"""Comprehensive astronomy source and RSS feed availability auditor.

Audits RSS feeds, NASA/NOAA/arXiv APIs, calculates aggregate health indicators
(🟢 Operational, 🟡 Degraded, 🔴 Disrupted), and updates both the badge and the
live health table in README.md.
"""
from __future__ import annotations
import json
import sys
import re
from pathlib import Path
from datetime import datetime, timezone
import requests
import feedparser

sys.path.insert(0, ".")
from astro_search.sources.rss import RSS_FEEDS, HEADERS
from astro_search.normalizer import freshness_hours, to_iso_utc


API_ENDPOINTS = [
    {
        "name": "NASA APOD API",
        "url": "https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY",
        "type": "api",
        "timeout": 15
    },
    {
        "name": "NASA DONKI CME API",
        "url": "https://api.nasa.gov/DONKI/CME?startDate=2026-01-01&endDate=2026-01-05&api_key=DEMO_KEY",
        "type": "api",
        "timeout": 15
    },
    {
        "name": "NOAA SWPC Kp 1-minute",
        "url": "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
        "type": "api",
        "timeout": 15
    },
    {
        "name": "arXiv Astronomy API",
        "url": "http://export.arxiv.org/api/query?search_query=cat:astro-ph&max_results=1",
        "type": "api",
        "timeout": 15
    },
    {
        "name": "Open Notify ISS Position",
        "url": "http://api.open-notify.org/iss-now.json",
        "type": "api",
        "timeout": 15
    },
]


def audit_sources() -> dict:
    results = []
    ok_count = 0
    total = len(RSS_FEEDS) + len(API_ENDPOINTS)

    print("Auditing RSS Feeds...")
    for f in RSS_FEEDS:
        name = f["name"]
        url = f["url"]
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            feed = feedparser.parse(r.content)
            n = len(feed.entries)
            dates = [to_iso_utc(e.get("published") or e.get("updated")) for e in feed.entries]
            age = freshness_hours(max(dates, default=""))
            healthy = bool(n) and age is not None and age <= 90 * 24
            status = "OK" if healthy else "REVIEW"
            if healthy:
                ok_count += 1
            results.append({
                "name": name,
                "type": "rss",
                "status": status,
                "http_status": r.status_code,
                "entries": n,
                "newest_age_h": age,
                "healthy": healthy
            })
            print(f"[{status}] {name}: HTTP {r.status_code}, {n} entries, newest_age_h={age}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            results.append({
                "name": name,
                "type": "rss",
                "status": "FAIL",
                "http_status": None,
                "entries": 0,
                "newest_age_h": None,
                "healthy": False,
                "error": str(e)
            })

    print("\nAuditing REST APIs...")
    for a in API_ENDPOINTS:
        name = a["name"]
        url = a["url"]
        try:
            r = requests.get(url, headers=HEADERS, timeout=a.get("timeout", 15))
            r.raise_for_status()
            healthy = r.status_code in (200, 201)
            status = "OK" if healthy else "REVIEW"
            if healthy:
                ok_count += 1
            results.append({
                "name": name,
                "type": "api",
                "status": status,
                "http_status": r.status_code,
                "healthy": healthy
            })
            print(f"[{status}] {name}: HTTP {r.status_code}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            results.append({
                "name": name,
                "type": "api",
                "status": "FAIL",
                "http_status": None,
                "healthy": False,
                "error": str(e)
            })

    pct = round((ok_count / max(total, 1)) * 100, 1)
    if pct >= 90.0:
        overall_status = "Operational"
        indicator_color = "brightgreen"
        emoji = "🟢"
    elif pct >= 75.0:
        overall_status = "Degraded"
        indicator_color = "yellow"
        emoji = "🟡"
    else:
        overall_status = "Disrupted"
        indicator_color = "red"
        emoji = "🔴"

    summary = {
        "total_sources": total,
        "healthy_count": ok_count,
        "health_percentage": pct,
        "overall_status": overall_status,
        "badge_color": indicator_color,
        "indicator_emoji": emoji,
        "details": results
    }

    print(f"\n{emoji} Availability Status: {overall_status} ({ok_count}/{total} sources healthy, {pct}%)")
    return summary


def generate_health_markdown(summary: dict) -> str:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    emoji = summary.get("indicator_emoji", "🟢")
    status = summary.get("overall_status", "Operational")
    pct = summary.get("health_percentage", 0.0)
    ok_count = summary.get("healthy_count", 0)
    total = summary.get("total_sources", 0)

    lines = [
        f"**Last Automated Check:** `{now_utc}` | **Overall Health:** {emoji} **{status}** ({ok_count}/{total} sources healthy, `{pct}%`)",
        "",
        "| Source | Type | Status | HTTP | Details | Freshness |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for item in summary.get("details", []):
        s_emoji = "🟢 OK" if item.get("status") == "OK" else ("🟡 Review" if item.get("status") == "REVIEW" else "🔴 Fail")
        http_code = str(item.get("http_status") or "-")
        stype = item.get("type", "rss").upper()
        entries = f"{item.get('entries')} entries" if item.get("type") == "rss" else "API Online"
        age = f"{item.get('newest_age_h')}h ago" if item.get("newest_age_h") is not None else "-"
        lines.append(f"| **{item['name']}** | `{stype}` | {s_emoji} | `{http_code}` | {entries} | {age} |")

    return "\n".join(lines)


def update_readme(summary: dict, readme_path: Path = Path("README.md")):
    if not readme_path.exists():
        return
    content = readme_path.read_text(encoding="utf-8")
    status = summary["overall_status"]
    color = summary["badge_color"]
    badge_md = f"![Source Status](https://img.shields.io/badge/Source_Availability-{status}-{color}?style=flat-square)"

    # 1. Update status badge at top
    pattern_badge = r"!\[Source Status\]\(https://img\.shields\.io/badge/Source_Availability-[^\)]+\)"
    if re.search(pattern_badge, content):
        content = re.sub(pattern_badge, badge_md, content)
    else:
        lines = content.splitlines()
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if line.startswith("# AstroSearch") and not inserted:
                new_lines.append("")
                new_lines.append(badge_md)
                inserted = True
        content = "\n".join(new_lines)

    # 2. Update Source Availability & Circuit Health table
    table_content = generate_health_markdown(summary)
    block_pattern = r"<!-- START_SOURCE_HEALTH_TABLE -->.*?<!-- END_SOURCE_HEALTH_TABLE -->"
    replacement_block = f"<!-- START_SOURCE_HEALTH_TABLE -->\n{table_content}\n<!-- END_SOURCE_HEALTH_TABLE -->"

    if re.search(block_pattern, content, flags=re.DOTALL):
        content = re.sub(block_pattern, replacement_block, content, flags=re.DOTALL)
    else:
        # Append as a section before License
        section = f"\n\n## Live Source Availability & Health\n\n{replacement_block}\n"
        if "## License" in content:
            content = content.replace("## License", section + "\n## License")
        else:
            content += section

    readme_path.write_text(content, encoding="utf-8")
    print(f"Updated README.md badge -> {status} ({color}) and refreshed live source table.")


def main():
    summary = audit_sources()
    # Save JSON report
    with open("feed_report.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if "--update-readme" in sys.argv:
        update_readme(summary)


if __name__ == "__main__":
    main()
