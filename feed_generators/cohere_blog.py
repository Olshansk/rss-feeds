"""Generate RSS feed for the Cohere Blog (https://cohere.com/blog).

Read dated cards from the current HTML listing and preserve cached history.
"""

import argparse
import re
from datetime import datetime
from urllib.parse import parse_qs, urljoin, urlparse

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from feed_history import merge_feed_history, require_posts
from static_pages import fetch_paginated
from utils import (
    deserialize_entries,
    load_cache,
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "cohere"
BLOG_URL = "https://cohere.com/blog"
MAX_PAGES_FULL = 30


def parse_blog_html(html: str) -> list[dict]:
    """Read dated article cards from Cohere's current blog listing.

    How:
    1. Select article links, excluding tags and navigation.
    2. Read titles, summaries, and publication dates inside each card.
    3. Deduplicate cards shared by the featured and latest sections.
    """
    soup = BeautifulSoup(html, "html.parser")
    posts = {}
    for card in soup.select('main a[href^="/blog/"]'):
        if "/tag/" in card["href"]:
            continue
        paragraphs = card.find_all("p")
        if not paragraphs:
            continue
        match = re.search(r"[A-Z][a-z]{2} \d{1,2}, \d{4}", card.get_text(" ", strip=True))
        if not match:
            continue
        link = urljoin(BLOG_URL, card["href"]).rstrip("/")
        title = paragraphs[0].get_text(" ", strip=True)
        summaries = [
            p.get_text(" ", strip=True) for p in paragraphs[1:] if not re.search(r"\d.*(?:read|, \d{4})", p.get_text())
        ]
        posts[link] = {
            "title": title,
            "link": link,
            "date": datetime.strptime(match.group(), "%b %d, %Y").replace(tzinfo=pytz.UTC),
            "description": summaries[0] if summaries else title,
            "category": "Blog",
        }
    return list(posts.values())


def fetch_all_posts(max_pages: int = MAX_PAGES_FULL) -> list[dict]:
    """Follow Cohere's numbered HTML pages and reject broken or empty pages.

    How:
    1. Fetch and parse each page with a bounded request.
    2. Follow the next numbered link while within the page limit.
    3. Return posts for merging with persisted history.
    """

    def next_url(html, url):
        page = int(parse_qs(urlparse(url).query).get("page", [1])[0])
        more = BeautifulSoup(html, "html.parser").select_one(f'a[href="/blog?page={page + 1}"]')
        return urljoin(url, more["href"]) if more else None

    return fetch_paginated(BLOG_URL, parse_blog_html, next_url, max_pages)


def generate_rss_feed(posts: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("The Cohere Blog")
    fg.description("Latest news, research, and product updates from Cohere")
    fg.language("en")
    fg.author({"name": "Cohere"})
    fg.logo("https://cohere.com/favicon.ico")
    fg.subtitle("Enterprise AI research and product updates from Cohere")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in sort_posts_for_feed(posts, date_field="date"):
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post.get("guid") or post["link"])
        fe.category(term=post["category"])
        if post.get("date"):
            fe.published(post["date"])

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def main(full_reset: bool = False) -> bool:
    """Refresh Cohere and persist both the cache and subscriber feed.

    How:
    1. Load cache and checked-in feed history before fetching.
    2. Fetch current pages, including the archive on a full run.
    3. Merge by URL, save the cache, and publish the RSS.
    """
    cached = deserialize_entries(load_cache(FEED_NAME).get("entries", []))
    fresh = fetch_all_posts(MAX_PAGES_FULL if full_reset or not cached else 1)
    posts = merge_feed_history(require_posts(fresh), FEED_NAME, match_titles=True)
    save_rss_feed(generate_rss_feed(posts), FEED_NAME)
    save_cache(FEED_NAME, posts)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Cohere Blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch all current pages)")
    args = parser.parse_args()
    raise SystemExit(0 if main(full_reset=args.full) else 1)
