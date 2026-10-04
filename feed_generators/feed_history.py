"""Published RSS history and identity preservation across source migrations."""

from collections import Counter
from email.utils import parsedate_to_datetime

from lxml import etree

from utils import get_feeds_dir, sort_posts_for_feed


def require_posts(posts):
    """Reject an empty live extraction before historical items can hide a failure."""
    if not posts:
        raise ValueError("No live posts extracted; refusing to republish cached content")
    return posts


def load_feed_history(feed_name: str) -> list[dict]:
    """Read saved RSS items when a source migration outlives the local JSON cache.

    How:
    1. Read the existing feed if present; fail on malformed XML.
    2. Recover identity, description, categories, and publication dates.
    3. Return entries compatible with merge_entries().
    """
    path = get_feeds_dir() / f"feed_{feed_name}.xml"
    if not path.exists():
        return []
    entries = []
    for item in etree.fromstring(path.read_bytes()).findall("channel/item"):
        date = item.findtext("pubDate")
        categories = [tag.text for tag in item.findall("category") if tag.text]
        entries.append(
            {
                "title": item.findtext("title"),
                "link": item.findtext("link"),
                "description": item.findtext("description") or item.findtext("title"),
                "date": parsedate_to_datetime(date) if date else None,
                "guid": item.findtext("guid"),
                "category": categories[0] if categories else "Blog",
                "tags": categories,
                "categories": categories,
            }
        )
    return entries


def merge_feed_history(posts: list[dict], feed_name: str, *, match_titles: bool = False) -> list[dict]:
    """Preserve subscriber identities when migrated articles change their URLs.

    How:
    1. Load the published archive and index its links and exact titles.
    2. Reuse the old GUID for matching articles while refreshing their content.
    3. Retain archive-only items and sort the combined feed.
    """
    require_posts(posts)
    history = load_feed_history(feed_name)
    by_link = {post["link"]: post for post in history}
    counts = Counter(post["title"] for post in history)
    by_title = {post["title"]: post for post in history if counts[post["title"]] == 1}
    merged = {post.get("guid") or post["link"]: post for post in history}
    for post in posts:
        previous = by_link.get(post["link"]) or (by_title.get(post["title"]) if match_titles else None)
        guid = (previous.get("guid") or previous["link"]) if previous else (post.get("guid") or post["link"])
        merged[guid] = {**post, "guid": guid}
    return sort_posts_for_feed(list(merged.values()))
