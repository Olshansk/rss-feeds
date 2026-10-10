"""Compare independently captured source entries against published RSS."""

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape

from scheduled_tasks.ci import timestamp


def text(value):
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def compare(snapshot, xml, now=None):
    """Compare a recent source sample without discarding historical RSS entries.

    How:
    1. Require timestamped, nonempty, independently extracted source evidence.
    2. Match exact article URLs and normalized titles; compare dates when supplied.
    3. Report missing/mismatched published articles and intentional future deferrals.
    """
    now = now or datetime.now(UTC)
    captured = timestamp(snapshot["captured_at"])
    if not timedelta(0) <= now - captured <= timedelta(minutes=30):
        raise ValueError("Source snapshot must be captured within the last 30 minutes")
    if not snapshot.get("source_url") or not snapshot.get("method") or not snapshot.get("items"):
        raise ValueError("Require source_url, extraction method, and nonempty source items")
    items = ET.fromstring(xml).findall("./channel/item")
    actual = {item.findtext("link"): item for item in items}
    if len(actual) != len(items):
        raise ValueError("Duplicate RSS links prevent an unambiguous comparison")
    discrepancies, deferred = [], []
    seen = set()
    for source in snapshot["items"]:
        link = source["link"]
        if not link or not text(source.get("title")) or link in seen:
            raise ValueError("Source entries require unique links and nonempty titles")
        seen.add(link)
        publication = timestamp(source["published_at"]) if source.get("published_at") else None
        if publication and publication > now:
            deferred.append(link)
            continue
        item = actual.get(link)
        if item is None:
            discrepancies.append({"link": link, "field": "item", "expected": "present", "actual": "missing"})
            continue
        if text(item.findtext("title")) != text(source["title"]):
            discrepancies.append(
                {"link": link, "field": "title", "expected": source["title"], "actual": item.findtext("title")}
            )
        if publication:
            actual_date = parsedate_to_datetime(item.findtext("pubDate"))
            if actual_date != publication:
                discrepancies.append(
                    {
                        "link": link,
                        "field": "published_at",
                        "expected": source["published_at"],
                        "actual": actual_date.isoformat(),
                    }
                )
    if len(seen) == len(deferred):
        raise ValueError("No published source entries were available to compare")
    return {
        "source_url": snapshot["source_url"],
        "captured_at": snapshot["captured_at"],
        "method": snapshot["method"],
        "compared": len(seen) - len(deferred),
        "deferred": deferred,
        "discrepancies": discrepancies,
        "matches": not discrepancies,
    }
