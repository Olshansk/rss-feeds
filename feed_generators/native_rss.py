"""Parse native RSS sources for existing subscriber endpoints."""

from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET


def parse_rss(content: str, category: str | None = None) -> list[dict]:
    """Read dated articles from a native RSS feed, rejecting an empty response."""
    posts = []
    for item in ET.fromstring(content).findall("channel/item"):
        categories = [tag.text for tag in item.findall("category") if tag.text]
        if category and category not in categories:
            continue
        title, link, date = (item.findtext(field) for field in ("title", "link", "pubDate"))
        if not title or not link or not date:
            raise ValueError("Native RSS item lacks a title, link, or date")
        posts.append(
            {
                "title": title.strip(),
                "link": link.rstrip("/"),
                "date": parsedate_to_datetime(date),
                "category": category or item.findtext("category") or "News",
                "categories": categories,
                "guid": item.findtext("guid") or link.rstrip("/"),
                "description": (item.findtext("description") or title).strip(),
            }
        )
    if not posts:
        raise ValueError("No matching native RSS articles found")
    return posts


def generate_feed(posts, *, title, description, blog_url, feed_name):
    """Build a sorted native-feed mirror with source identities and summaries."""
    from feedgen.feed import FeedGenerator

    from utils import setup_feed_links, sort_posts_for_feed

    feed = FeedGenerator()
    feed.title(title)
    feed.description(description)
    feed.language("en")
    setup_feed_links(feed, blog_url, feed_name)
    for post in sort_posts_for_feed(posts):
        entry = feed.add_entry()
        entry.title(post["title"])
        entry.link(href=post["link"])
        entry.id(post.get("guid") or post["link"])
        entry.published(post["date"])
        entry.description(post["description"])
        for category in post.get("categories", []):
            entry.category(term=category)
    return feed
