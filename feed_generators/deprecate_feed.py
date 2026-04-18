"""Inject a deprecation notice into a feed XML.

Used when a scraper is being retired (e.g., the site launched an official RSS feed).
The notice shows up as the newest entry in the feed, so subscribers see it in their
RSS reader rather than silently losing updates.

Usage:
    uv run feed_generators/deprecate_feed.py \\
        --feed=openai_research \\
        --message="OpenAI now provides an official RSS feed." \\
        --alternative="https://openai.com/blog/rss.xml"

After running, set ``enabled: false`` for the feed in ``feeds.yaml`` so the
scraper stops executing but the XML (with the notice) remains in the repo.
"""

import argparse
import xml.etree.ElementTree as ET
from datetime import datetime

import pytz

from utils import get_feeds_dir, setup_logging

logger = setup_logging()

DEPRECATION_GUID_PREFIX = "deprecation-notice-"
DEPRECATION_TITLE = "[NOTICE] This feed is no longer maintained"


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
    pub_date = datetime.now(pytz.UTC).strftime("%a, %d %b %Y %H:%M:%S +0000")

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

    tree.write(str(feed_file), xml_declaration=True, encoding="UTF-8")
    logger.info(f"Added deprecation notice to {feed_file}")
    logger.info(f"Remember to set `enabled: false` for {feed_name} in feeds.yaml")
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
