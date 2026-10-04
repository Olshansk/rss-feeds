"""Parse native RSS sources for existing subscriber endpoints."""

from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET


def parse_rss(content: str) -> list[dict]:
    """Read dated articles from a native RSS feed, rejecting an empty response."""
    posts = []
    for item in ET.fromstring(content).findall("channel/item"):
        title, link, date = (item.findtext(field) for field in ("title", "link", "pubDate"))
        if not title or not link or not date:
            raise ValueError("Native RSS item lacks a title, link, or date")
        posts.append(
            {
                "title": title.strip(),
                "link": link.rstrip("/"),
                "date": parsedate_to_datetime(date),
                "category": item.findtext("category") or "News",
                "description": item.findtext("description") or title,
            }
        )
    if not posts:
        raise ValueError("No Native RSS articles found")
    return posts
