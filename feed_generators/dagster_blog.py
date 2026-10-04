import argparse
from datetime import datetime
from urllib.parse import urljoin

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from feed_history import merge_feed_history, require_posts
from html_cards import parse_dated_cards
from static_pages import fetch_paginated
from utils import (
    deserialize_entries,
    fetch_page,
    load_cache,
    merge_entries,
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
)

logger = setup_logging()

BLOG_URL = "https://dagster.io/blog"
FEED_NAME = "dagster"


def parse_posts(html_content):
    """Read semantic blog cards and the optional Webflow pagination link."""
    posts = parse_dated_cards(html_content, ".featured_blog_link, .blog_card", BLOG_URL)
    next_link = BeautifulSoup(html_content, "html.parser").select_one("a.w-pagination-next[href]")
    return posts, next_link.get("href") if next_link else None


def fetch_all_pages():
    """Fetch the complete listing with bounded shared pagination.

    How:
    1. Parse semantic dated cards from each page.
    2. Follow the source's next-page URL and deduplicate overlapping cards.
    """
    return fetch_paginated(
        BLOG_URL,
        lambda html: parse_posts(html)[0],
        lambda html, url: urljoin(url, parse_posts(html)[1]) if parse_posts(html)[1] else None,
    )


def generate_rss_feed(posts):
    """Generate RSS feed from blog posts."""
    fg = FeedGenerator()
    fg.title("Dagster Blog")
    fg.description(
        "Read the latest from the Dagster team: insights, tutorials, and updates on data engineering, orchestration, and building better pipelines."
    )
    fg.language("en")

    fg.author({"name": "Dagster"})
    fg.subtitle("Latest updates from Dagster")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post["link"])

        if post.get("date"):
            try:
                dt = post["date"] if isinstance(post["date"], datetime) else datetime.strptime(post["date"], "%Y-%m-%d")
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=pytz.UTC)
                fe.published(dt)
            except (ValueError, TypeError):
                pass

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def main(full_reset=False):
    """Main function to generate RSS feed from blog URL.

    Args:
        full_reset: If True, fetch all pages. If False, only fetch page 1
                   and merge with cached posts.
    """
    cache = load_cache(FEED_NAME)
    cached_entries = deserialize_entries(cache.get("entries", []))

    if full_reset or not cached_entries:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
        posts = fetch_all_pages()
    else:
        logger.info("Running incremental update (page 1 only)")
        html = fetch_page(BLOG_URL)
        new_posts, _ = parse_posts(html)
        logger.info(f"Found {len(new_posts)} posts on page 1")
        posts = merge_entries(require_posts(new_posts), cached_entries)

    if not posts:
        logger.warning("No posts fetched — skipping feed update to avoid overwriting with empty feed")
        return False

    posts = merge_feed_history(posts, FEED_NAME)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed, FEED_NAME)
    save_cache(FEED_NAME, posts)

    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Dagster Blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch all pages)")
    args = parser.parse_args()
    main(full_reset=args.full)
