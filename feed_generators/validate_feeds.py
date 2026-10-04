"""Validate all RSS feeds for empty content and stale items."""

import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from itertools import pairwise
from pathlib import Path

STALE_THRESHOLD_DAYS = 60
FEEDS_DIR = Path(__file__).parent.parent / "feeds"


def _dated_items_are_newest_first(items) -> bool:
    """Return whether parseable item dates are ordered newest-first."""
    dates = []
    for item in items:
        pub_date = item.find("pubDate")
        if pub_date is None or not pub_date.text:
            continue
        try:
            parsed_date = parsedate_to_datetime(pub_date.text)
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=UTC)
            dates.append(parsed_date)
        except (TypeError, ValueError):
            continue
    return all(previous >= current for previous, current in pairwise(dates))


def validate_feed(feed_path):
    """Validate a single feed file.

    Returns:
        dict with keys: name, item_count, newest_date, status, message
    """
    return validate_xml(feed_path.read_bytes(), feed_path.name)


def validate_xml(content: bytes, name: str = "feed"):
    """Validate serialized RSS before publication or from an existing file."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return {"name": name, "item_count": 0, "newest_date": None, "status": "ERROR", "message": str(e)}
    items = root.findall(".//item")
    item_count = len(items)

    if item_count == 0:
        return {
            "name": name,
            "item_count": 0,
            "newest_date": None,
            "status": "EMPTY",
            "message": "0 items",
        }

    links = [item.findtext("link") for item in items]
    guids = [item.findtext("guid") for item in items if item.findtext("guid")]
    if len(links) != len(set(links)) or len(guids) != len(set(guids)):
        return {
            "name": name,
            "item_count": item_count,
            "newest_date": None,
            "status": "ERROR",
            "message": "Duplicate item links or GUIDs",
        }

    dates = []
    for item in items:
        missing = [field for field in ("title", "link", "pubDate") if not (item.findtext(field) or "").strip()]
        try:
            date = parsedate_to_datetime(item.findtext("pubDate") or "")
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            dates.append(date)
            if date > datetime.now(UTC):
                missing.append("non-future pubDate")
        except (ValueError, TypeError):
            missing.append("parseable pubDate")
        if missing:
            return {
                "name": name,
                "item_count": item_count,
                "newest_date": None,
                "status": "ERROR",
                "message": f"Item {item.findtext('title')!r} lacks {', '.join(missing)}",
            }

    if not _dated_items_are_newest_first(items):
        return {
            "name": name,
            "item_count": item_count,
            "newest_date": None,
            "status": "ERROR",
            "message": f"{item_count} items, dated items are not newest-first",
        }

    newest = max(dates)

    days_ago = (datetime.now(UTC) - newest).days

    if days_ago > STALE_THRESHOLD_DAYS:
        return {
            "name": name,
            "item_count": item_count,
            "newest_date": newest,
            "status": "STALE",
            "message": f"{item_count} items, newest: {newest.strftime('%Y-%m-%d')} ({days_ago} days ago)",
        }

    return {
        "name": name,
        "item_count": item_count,
        "newest_date": newest,
        "status": "OK",
        "message": f"{item_count} items, newest: {newest.strftime('%Y-%m-%d')}",
    }


def main():
    feeds = sorted(FEEDS_DIR.glob("feed_*.xml"))

    if not feeds:
        print("No feed files found in feeds/")
        sys.exit(1)

    results = [validate_feed(f) for f in feeds]

    # Print summary
    print(f"\nFeed Validation Summary ({len(results)} feeds):")
    print(f"{'=' * 70}")

    for r in results:
        print(f"  {r['name']:50s} {r['status']:5s}  {r['message']}")

    empty = [r for r in results if r["status"] == "EMPTY"]
    stale = [r for r in results if r["status"] == "STALE"]
    errors = [r for r in results if r["status"] == "ERROR"]

    print(f"{'=' * 70}")

    if errors:
        print(f"\nERRORS: {len(errors)} feed(s) with invalid XML or content")
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
