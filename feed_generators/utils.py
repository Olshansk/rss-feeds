"""Shared utilities for feed generators."""

from pathlib import Path

from feedgen.feed import FeedGenerator


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_cache_dir():
    """Get the cache directory path, creating it if needed."""
    cache_dir = get_project_root() / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_feeds_dir():
    """Get the feeds directory path, creating it if needed."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def setup_feed_links(fg: FeedGenerator, blog_url: str, feed_name: str) -> None:
    """Set up feed links correctly so <link> points to the blog, not the feed.

    In feedgen, link order matters:
    - rel="self" must be set FIRST (becomes <atom:link rel="self">)
    - rel="alternate" must be set LAST (becomes the main <link>)

    Args:
        fg: FeedGenerator instance
        blog_url: URL to the original blog (e.g., "https://dagster.io/blog")
        feed_name: Feed name for the self link (e.g., "dagster")
    """
    # Self link first - this becomes <atom:link rel="self">
    fg.link(
        href=f"https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_{feed_name}.xml",
        rel="self",
    )
    # Alternate link last - this becomes the main <link>
    fg.link(href=blog_url, rel="alternate")
