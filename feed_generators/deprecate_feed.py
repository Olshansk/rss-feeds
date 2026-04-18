"""Inject a deprecation notice into a feed XML.

Used when a scraper is being retired (e.g., the site launched an official RSS feed).
The notice shows up as the newest entry in the feed, so subscribers see it in their
RSS reader rather than silently losing updates.

Usage:
    uv run feed_generators/deprecate_feed.py \\
        --feed=openai_research \\
        --message="OpenAI now provides an official RSS feed." \\
        --alternative="https://openai.com/blog/rss.xml"

After running, in the same PR, remove the generator script, the ``<name>:`` entry
from ``feeds.yaml``, the ``feeds_<name>`` Make target, and the README row. Only
``feeds/feed_<name>.xml`` (now carrying the tombstone notice) stays in place;
it is deleted automatically after ~90 days by the
``cleanup_deprecated_feeds.yml`` workflow.
"""

import argparse
from datetime import datetime

import pytz
from lxml import etree as ET

from utils import get_feeds_dir, setup_logging

logger = setup_logging()

DEPRECATION_GUID_PREFIX = "deprecation-notice-"
DEPRECATION_TITLE = "[NOTICE] This feed is no longer maintained"

# lxml.etree is used (not the stdlib xml.etree.ElementTree) because the stdlib
# parser drops unused namespace declarations and rewrites unregistered
# namespace prefixes to ns0/ns1/... on round-trip. That silently corrupts
# feedgen's <atom:link rel="self"> and xmlns:content declarations. lxml
# preserves the original xmlns bindings verbatim.

# RFC 822 day-of-week and month tokens. Python's strftime("%a"/"%b") honors the
# current system locale, which breaks feed readers on non-English CI runners.
# Build the pubDate explicitly to keep the round-trip locale-independent.
RFC822_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
RFC822_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def format_rfc822(dt: datetime) -> str:
    """Format a datetime as RFC 822 pubDate without relying on system locale."""
    day = RFC822_WEEKDAYS[dt.weekday()]
    month = RFC822_MONTHS[dt.month - 1]
    return f"{day}, {dt.day:02d} {month} {dt.year} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} +0000"


def deprecate_feed(feed_name: str, message: str, alternative_url: str | None = None) -> bool:
    """Inject a deprecation <item> into feeds/feed_<feed_name>.xml.

    The entry uses a stable GUID (``deprecation-notice-<feed_name>``) so repeated
    runs do not duplicate the notice. Returns True on success, False otherwise.
    """
    feed_file = get_feeds_dir() / f"feed_{feed_name}.xml"
    if not feed_file.exists():
        logger.error(f"Feed file not found: {feed_file}")
        return False

    tree = ET.parse(feed_file)
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        logger.error("No <channel> element found in feed XML")
        return False

    guid_value = f"{DEPRECATION_GUID_PREFIX}{feed_name}"
    for item in channel.findall("item"):
        guid = item.find("guid")
        if guid is not None and guid.text == guid_value:
            logger.info(f"Deprecation notice already present in {feed_file}, skipping")
            return True

    body = message
    if alternative_url:
        body += f"\n\nRecommended alternative: {alternative_url}"
    pub_date = format_rfc822(datetime.now(pytz.UTC))

    notice = ET.Element("item")
    ET.SubElement(notice, "title").text = DEPRECATION_TITLE
    ET.SubElement(notice, "description").text = body
    ET.SubElement(notice, "guid", isPermaLink="false").text = guid_value
    ET.SubElement(notice, "pubDate").text = pub_date
    if alternative_url:
        ET.SubElement(notice, "link").text = alternative_url

    first_item = channel.find("item")
    if first_item is not None:
        idx = list(channel).index(first_item)
        channel.insert(idx, notice)
    else:
        channel.append(notice)

    tree.write(str(feed_file), xml_declaration=True, encoding="UTF-8", pretty_print=False)
    logger.info(f"Added deprecation notice to {feed_file}")
    logger.info(
        f"Next: remove the `{feed_name}:` entry from feeds.yaml, the feeds_{feed_name} Make "
        "target, and any README row; leave the XML in place."
    )
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--feed", required=True, help="Feed name (e.g., 'openai_research')")
    parser.add_argument("--message", required=True, help="Notice body text")
    parser.add_argument("--alternative", default=None, help="Optional alternative feed URL")
    args = parser.parse_args()

    success = deprecate_feed(args.feed, args.message, args.alternative)
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
