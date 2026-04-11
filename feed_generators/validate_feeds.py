"""Validate all RSS feeds for empty content and stale items."""

import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

STALE_THRESHOLD_DAYS = 60
FEEDS_DIR = Path(__file__).parent.parent / "feeds"


def validate_feed(feed_path):
    """Validate a single feed file.

    Returns:
        dict with keys: name, item_count, newest_date, status, message
    """
    name = feed_path.name
    try:
        tree = ET.parse(feed_path)
    except ET.ParseError as e:
        return {"name": name, "item_count": 0, "newest_date": None,
                "status": "ERROR", "message": f"XML parse error: {e}"}

    root = tree.getroot()
    items = root.findall(".//item")
    item_count = len(items)

    if item_count == 0:
        return {"name": name, "item_count": 0, "newest_date": None,
                "status": "EMPTY", "message": "0 items"}

    # Find newest pubDate
    newest = None
    for item in items:
        pub_date = item.find("pubDate")
        if pub_date is not None and pub_date.text:
            try:
                dt = parsedate_to_datetime(pub_date.text)
                if newest is None or dt > newest:
                    newest = dt
            except (ValueError, TypeError):
                continue

    if newest is None:
        return {"name": name, "item_count": item_count, "newest_date": None,
                "status": "OK", "message": f"{item_count} items, no parseable dates"}

    days_ago = (datetime.now(timezone.utc) - newest).days

    if days_ago > STALE_THRESHOLD_DAYS:
        return {"name": name, "item_count": item_count, "newest_date": newest,
                "status": "STALE",
                "message": f"{item_count} items, newest: {newest.strftime('%Y-%m-%d')} ({days_ago} days ago)"}

    return {"name": name, "item_count": item_count, "newest_date": newest,
            "status": "OK",
            "message": f"{item_count} items, newest: {newest.strftime('%Y-%m-%d')}"}


def main():
    feeds = sorted(FEEDS_DIR.glob("feed_*.xml"))

    if not feeds:
        print("No feed files found in feeds/")
        sys.exit(1)

    results = [validate_feed(f) for f in feeds]

    # Print summary
    print(f"\nFeed Validation Summary ({len(results)} feeds):")
    print(f"{'='*70}")

    for r in results:
        print(f"  {r['name']:50s} {r['status']:5s}  {r['message']}")

    empty = [r for r in results if r["status"] == "EMPTY"]
    stale = [r for r in results if r["status"] == "STALE"]
    errors = [r for r in results if r["status"] == "ERROR"]

    print(f"{'='*70}")

    if errors:
        print(f"\nERRORS: {len(errors)} feed(s) with XML parse errors")
        for r in errors:
            print(f"  {r['name']}: {r['message']}")

    if empty:
        print(f"\nERRORS: {len(empty)} empty feed(s)")
        for r in empty:
            print(f"  {r['name']}")

    if stale:
        print(f"\nWARNINGS: {len(stale)} stale feed(s) (>{STALE_THRESHOLD_DAYS} days)")
        for r in stale:
            print(f"  {r['name']}: {r['message']}")

    if not empty and not errors:
        print("\nAll feeds have content.")

    # Exit 1 only for empty or parse-error feeds
    if empty or errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
