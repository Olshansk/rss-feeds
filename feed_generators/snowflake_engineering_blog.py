"""Generate RSS feed for the Snowflake Engineering Blog
(https://www.snowflake.com/en/engineering-blog/).

The page is rendered by Adobe Experience Manager (AEM). It embeds the
listing of posts as JSON inside a ``<script id="__INITIAL_STATE__">`` tag,
so we parse that JSON directly instead of scraping rendered HTML — it is
both more reliable and gives us structured fields (title, date, authors,
tags, description, link).

The page itself does not expose URL-based pagination ("Next" uses an
authenticated AEM filter API), so each run pulls the ~13 posts visible
on the landing page (1 featured + 3 hot-off-the-press + 9 latest) and
merges them with the cache so older posts are retained over time.
"""

import argparse
import json
from datetime import datetime
from typing import Any

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    deserialize_entries,
    fetch_page,
    load_cache,
    merge_entries,
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "snowflake_engineering"
BLOG_URL = "https://www.snowflake.com/en/engineering-blog/"
SITE_ROOT = "https://www.snowflake.com"


def extract_initial_state(html: str) -> dict:
    """Pull the ``__INITIAL_STATE__`` JSON payload out of the page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__INITIAL_STATE__")
    if script is None or not script.string:
        raise RuntimeError("Could not find __INITIAL_STATE__ JSON on the page")
    return json.loads(script.string)


def _absolute_url(url: str) -> str:
    if url.startswith("/"):
        return f"{SITE_ROOT}{url}"
    return url


def _parse_publication_date(value: str | None) -> datetime | None:
    """Parse Snowflake's ``MAR 12, 2026`` date format into a UTC datetime."""
    if not value:
        return None
    try:
        dt = datetime.strptime(value.strip(), "%b %d, %Y")
    except ValueError:
        try:
            dt = datetime.strptime(value.strip().title(), "%b %d, %Y")
        except ValueError:
            logger.warning(f"Could not parse publication date: {value!r}")
            return None
    return dt.replace(tzinfo=pytz.UTC)


def _card_to_post(card: dict) -> dict | None:
    """Convert one AEM ``blog/card`` payload into our post dict."""
    if not isinstance(card, dict):
        return None

    title_lines = card.get("title", {}).get("lines") or []
    title = title_lines[0].strip() if title_lines else ""

    button = card.get("button") or {}
    raw_url = (button.get("buttonLink") or {}).get("url", "")
    if not title or not raw_url:
        return None
    link = _absolute_url(raw_url)

    raw_description = (card.get("text") or {}).get("text") or ""
    description = " ".join(raw_description.split()) or title

    # Leave date as None on parse failure rather than calling
    # ``stable_fallback_date()`` — that helper is keyed on Python's built-in
    # ``hash()``, which is randomized per process, so its "stable" date would
    # actually shift between runs and churn the cache/feed ordering.
    date = _parse_publication_date(card.get("publicationDate"))

    authors = [
        (author.get("text") or "").strip() for author in card.get("authors") or [] if (author.get("text") or "").strip()
    ]
    tags = [(tag.get("tagText") or "").strip() for tag in card.get("tags") or [] if (tag.get("tagText") or "").strip()]

    return {
        "title": title,
        "link": link,
        "date": date,
        "description": description,
        "authors": authors,
        "category": tags[0] if tags else "Engineering",
    }


def _walk_cards(node: Any, results: list[dict]) -> None:
    """Recursively collect every ``blog/card`` payload in the JSON tree."""
    if isinstance(node, dict):
        if node.get(":type") == "snowflake-site/components/blog/card":
            post = _card_to_post(node)
            if post is not None:
                results.append(post)
            return
        for value in node.values():
            _walk_cards(value, results)
    elif isinstance(node, list):
        for value in node:
            _walk_cards(value, results)


def parse_posts_from_html(html: str) -> list[dict]:
    state = extract_initial_state(html)
    posts: list[dict] = []
    _walk_cards(state, posts)

    # Dedupe by link, preserving the first occurrence (the featured slot
    # may repeat a post that also appears in latest).
    seen: set[str] = set()
    unique: list[dict] = []
    for post in posts:
        if post["link"] in seen:
            continue
        seen.add(post["link"])
        unique.append(post)

    logger.info(f"Extracted {len(unique)} posts from initial state")
    return unique


def generate_rss_feed(posts: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("Snowflake Engineering Blog")
    fg.description("Hear directly from Snowflake's technical leaders about what we build, why and how we build it.")
    fg.language("en")
    fg.author({"name": "Snowflake Engineering"})
    fg.subtitle("Engineering deep dives, infrastructure, and AI/ML from Snowflake")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in sort_posts_for_feed(posts, date_field="date"):
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post["link"])
        fe.category(term=post["category"])
        for author_name in post.get("authors", []):
            fe.author({"name": author_name})
        if post.get("date"):
            fe.published(post["date"])

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def main() -> bool:
    cache = load_cache(FEED_NAME)
    cached_entries = deserialize_entries(cache.get("entries", []))

    html = fetch_page(BLOG_URL)
    new_posts = parse_posts_from_html(html)

    if not new_posts and not cached_entries:
        logger.warning("No posts found and no cache exists — aborting.")
        return False

    posts = merge_entries(new_posts, cached_entries)
    save_cache(FEED_NAME, posts)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed, FEED_NAME)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Snowflake Engineering Blog RSS feed")
    # ``--full`` is accepted for symmetry with other generators, but the
    # site only exposes a single page of results so behavior is identical.
    parser.add_argument("--full", action="store_true", help="No-op (kept for CLI symmetry)")
    parser.parse_args()
    raise SystemExit(0 if main() else 1)
