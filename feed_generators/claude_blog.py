#!/usr/bin/env python3
"""Generate RSS feed for Claude Blog (claude.com/blog)."""

import argparse
import html
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import pytz
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import setup_feed_links, sort_posts_for_feed

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BLOG_URL = "https://claude.com/blog"
FEED_NAME = "claude"
BASE_URL = "https://claude.com"

DATE_PATTERN = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
)


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_cache_file():
    """Get the cache file path."""
    return get_project_root() / "cache" / "claude_posts.json"


def get_feeds_dir():
    """Get the feeds directory path."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_page(url):
    """Fetch a single page HTML with Finsweet header."""
    headers = {
        "X-Webflow-App-ID": "finsweet",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def extract_pagination_ids(html_content):
    """Extract pagination collection IDs from the HTML."""
    pattern = r"\?([a-f0-9]+)_page=\d+"
    matches = re.findall(pattern, html_content)
    return list(set(matches))


def parse_date(date_str):
    """Parse date string like 'January 12, 2026' to datetime."""
    try:
        return datetime.strptime(date_str, "%B %d, %Y")
    except ValueError:
        return None


def parse_posts(html_content):
    """Parse the blog HTML content and extract post information.

    Returns a list of unique posts, deduplicated by URL.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    posts_by_url = {}

    for item in soup.select(".w-dyn-item"):
        link = item.select_one('a[href^="/blog/"]')
        if not link:
            continue

        href = link.get("href", "")
        if "/blog/category/" in href or not href:
            continue

        full_url = f"{BASE_URL}{href}"

        # Skip if we already have this post (keep the one with most data)
        if full_url in posts_by_url:
            existing = posts_by_url[full_url]
            # Only update if existing has no date and this one does
            item_text = item.get_text()
            date_match = DATE_PATTERN.search(item_text)
            if not existing.get("date") and date_match:
                pass  # Continue to update
            else:
                continue  # Keep existing

        # Extract title
        title = None
        h2 = item.select_one("h2")
        if h2:
            title = h2.get_text(strip=True)
        if not title:
            title = link.get("data-cta-copy", "")
        if not title:
            for tag in ["h3", "h4", ".u-text-style-h6"]:
                el = item.select_one(tag)
                if el:
                    title = el.get_text(strip=True)
                    break

        # Extract date
        date_obj = None
        item_text = item.get_text()
        date_match = DATE_PATTERN.search(item_text)
        if date_match:
            date_obj = parse_date(date_match.group(0))

        # Extract category
        category = None
        category_el = item.select_one('[fs-list-field="category"]')
        if category_el:
            category = category_el.get_text(strip=True)
        if not category:
            data_category = item.get("data-category")
            if data_category:
                category = data_category

        # Extract description
        description = None
        desc_el = item.select_one(".card_blog_description, .u-text-style-body-2, p")
        if desc_el:
            description = desc_el.get_text(strip=True)

        if title and href:
            title = html.unescape(title)
            if description:
                description = html.unescape(description)
            posts_by_url[full_url] = {
                "url": full_url,
                "title": title,
                "date": date_obj.strftime("%Y-%m-%d") if date_obj else None,
                "category": category,
                "description": description or title,
            }

    return list(posts_by_url.values())


def load_cache():
    """Load existing cache or return empty structure."""
    cache_file = get_cache_file()
    if cache_file.exists():
        with open(cache_file, "r") as f:
            data = json.load(f)
            logger.info(f"Loaded cache with {len(data.get('posts', []))} posts")
            return data
    logger.info("No cache file found, will do full fetch")
    return {"last_updated": None, "posts": []}


def save_cache(posts):
    """Save posts to cache file."""
    cache_file = get_cache_file()
    cache_file.parent.mkdir(exist_ok=True)
    data = {
        "last_updated": datetime.now(pytz.UTC).isoformat(),
        "posts": posts,
    }
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved cache with {len(posts)} posts to {cache_file}")


def merge_posts(new_posts, cached_posts):
    """Merge new posts into cache, dedupe by URL, sort by date desc."""
    existing_urls = {p["url"] for p in cached_posts}
    merged = list(cached_posts)

    added_count = 0
    for post in new_posts:
        if post["url"] not in existing_urls:
            merged.append(post)
            existing_urls.add(post["url"])
            added_count += 1

    logger.info(f"Added {added_count} new posts to cache")

    # Sort for correct feed order (newest first in output)
    return sort_posts_for_feed(merged, date_field="date")


def fetch_all_pages():
    """Follow pagination until no new posts. Returns all posts."""
    logger.info(f"Fetching main page: {BLOG_URL}")
    html_content = fetch_page(BLOG_URL)
    all_posts = parse_posts(html_content)
    logger.info(f"Found {len(all_posts)} posts on main page")

    # Get unique post URLs to track duplicates
    seen_urls = {p["url"] for p in all_posts}

    # Extract pagination collection IDs
    collection_ids = extract_pagination_ids(html_content)
    logger.info(f"Found pagination IDs: {collection_ids}")

    for collection_id in collection_ids:
        page = 2
        consecutive_empty = 0

        while consecutive_empty < 2:
            page_url = f"{BLOG_URL}?{collection_id}_page={page}"
            logger.info(f"Fetching: {page_url}")

            try:
                page_html = fetch_page(page_url)
            except requests.RequestException as e:
                logger.warning(f"Failed to fetch page {page}: {e}")
                break

            page_posts = parse_posts(page_html)
            new_posts = [p for p in page_posts if p["url"] not in seen_urls]

            if not new_posts:
                consecutive_empty += 1
                logger.info(f"  No new posts (attempt {consecutive_empty})")
            else:
                consecutive_empty = 0
                logger.info(f"  Found {len(new_posts)} new posts")
                all_posts.extend(new_posts)
                seen_urls.update(p["url"] for p in new_posts)

            page += 1

            if page > 50:
                logger.info("  Reached page limit, stopping")
                break

    # Sort for correct feed order (newest first in output)
    sorted_posts = sort_posts_for_feed(all_posts, date_field="date")
    logger.info(f"Total unique posts across all pages: {len(sorted_posts)}")
    return sorted_posts


def generate_rss_feed(posts):
    """Generate RSS feed from blog posts."""
    fg = FeedGenerator()
    fg.title("Claude Blog")
    fg.description(
        "Get practical guidance and best practices for building with Claude. "
        "Technical guides, real-world examples, and insights from Anthropic's "
        "engineering and research teams."
    )
    fg.language("en")

    fg.author({"name": "Anthropic", "email": "blog@anthropic.com"})
    fg.subtitle("Latest updates from Claude Blog")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["url"])
        fe.id(post["url"])

        if post.get("category"):
            fe.category(term=post["category"])

        if post.get("date"):
            try:
                dt = datetime.strptime(post["date"], "%Y-%m-%d")
                fe.published(dt.replace(tzinfo=pytz.UTC))
            except ValueError:
                pass

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def save_rss_feed(feed_generator):
    """Save the RSS feed to a file in the feeds directory."""
    feeds_dir = get_feeds_dir()
    output_file = feeds_dir / f"feed_{FEED_NAME}.xml"
    feed_generator.rss_file(str(output_file), pretty=True)
    logger.info(f"Saved RSS feed to {output_file}")
    return output_file


def main(full_reset=False):
    """Main function to generate RSS feed from blog URL.

    Args:
        full_reset: If True, fetch all pages. If False, only fetch page 1
                   and merge with cached posts.
    """
    cache = load_cache()

    if full_reset or not cache["posts"]:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
        posts = fetch_all_pages()
    else:
        logger.info("Running incremental update (page 1 only)")
        html_content = fetch_page(BLOG_URL)
        new_posts = parse_posts(html_content)
        logger.info(f"Found {len(new_posts)} posts on page 1")
        posts = merge_posts(new_posts, cache["posts"])

    save_cache(posts)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed)

    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Claude Blog RSS feed")
    parser.add_argument(
        "--full", action="store_true", help="Force full reset (fetch all pages)"
    )
    args = parser.parse_args()
    main(full_reset=args.full)
