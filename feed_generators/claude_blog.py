#!/usr/bin/env python3
"""Generate Claude's existing subscriber feed from its public resource listing."""

import argparse
from urllib.parse import urlparse

from dates import parse_date
from embedded_data import next_objects
from feed_history import merge_feed_history, require_posts
from json_pages import fetch_numbered_items
from native_rss import generate_feed
from static_pages import fetch_page
from utils import save_cache, save_rss_feed, setup_logging

logger = setup_logging()
BLOG_URL = "https://claude.com/resources/articles"
SOURCE_URL = "https://claude.com/api/resources/search"
FEED_NAME = "claude"


def fetch_articles(full=False):
    """Fetch recent articles or the archive through the site's public category filters.

    How:
    1. Use article search so the featured lead is included in recent results.
    2. For full runs, discover categories and the expected total from the rendered HTML data.
    3. Combine the unfiltered 20-page window with categories, then require the full advertised count.
    """
    params = {"types": "article", "language": "en"}
    if not full:
        return fetch_numbered_items(SOURCE_URL, params=params)
    objects = list(next_objects(fetch_page(BLOG_URL)))
    categories = next(obj["categoryOptions"] for obj in objects if "categoryOptions" in obj)
    total = next(obj["total"] for obj in objects if "items" in obj and "total" in obj)
    # The unfiltered window also includes articles without a category.
    recent = fetch_numbered_items(SOURCE_URL, params=params, full=True, max_pages=20, require_complete=False)
    items = {item["_id"]: item for item in recent}
    for category in categories:
        batch = fetch_numbered_items(
            SOURCE_URL, params={**params, "categories": category["slug"]}, full=True, max_pages=20
        )
        items.update({item["_id"]: item for item in batch})
    if len(items) != total:
        raise ValueError(f"Incomplete Claude archive: expected {total} articles, found {len(items)}")
    return list(items.values())


def parse_posts(items):
    """Convert Claude resource records while retaining legacy blog URL identities.

    How:
    1. Require articles with a title, publication date, and internal slug or HTTPS URL.
    2. Map internal slugs to current article URLs and their original blog GUIDs.
    3. Deduplicate featured articles by URL, preserving categories and summaries.
    """
    posts = {}
    for item in items:
        if item.get("_type") != "blogPost":
            raise ValueError("Unexpected non-article in Claude article listing")
        title = (item.get("title") or "").strip()
        slug = item.get("slug")
        external = item.get("externalUrl")
        if external:
            link = external
            guid = link
        elif isinstance(slug, str) and slug and "/" not in slug:
            link = f"https://claude.com/resources/articles/{slug}"
            guid = f"https://claude.com/blog/{slug}"
        else:
            raise ValueError("Claude article lacks a usable URL")
        if not title or urlparse(link).scheme != "https" or not urlparse(link).netloc:
            raise ValueError("Claude article lacks a title or HTTPS URL")
        category = (item.get("category") or {}).get("name") or "Blog"
        posts[link] = {
            "title": title,
            "link": link,
            "guid": guid,
            "date": parse_date(item.get("date") or ""),
            "description": (item.get("excerpt") or title).strip(),
            "category": category,
            "categories": [category],
        }
    return require_posts(list(posts.values()))


def main(full_reset=False):
    """Refresh live articles and publish them with the existing subscriber archive.

    How:
    1. Fetch fresh public article data, following all pages only for an explicit full run.
    2. Parse and merge published history, preserving GUIDs through the URL migration.
    3. Validate and atomically write RSS before updating the local cache.
    """
    items = fetch_articles(full=full_reset)
    posts = merge_feed_history(parse_posts(items), FEED_NAME, match_titles=True)
    feed = generate_feed(
        posts,
        title="Claude Blog",
        description="Practical guidance, product updates, and best practices for building with Claude.",
        blog_url=BLOG_URL,
        feed_name=FEED_NAME,
    )
    save_rss_feed(feed, FEED_NAME)
    save_cache(FEED_NAME, posts)
    logger.info("Published %s Claude articles", len(posts))
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Claude Blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Fetch the complete article archive")
    args = parser.parse_args()
    raise SystemExit(0 if main(full_reset=args.full) else 1)
