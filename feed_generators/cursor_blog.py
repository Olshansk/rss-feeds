import argparse
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BLOG_URL = "https://cursor.com/blog"
FEED_NAME = "cursor"


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_cache_file():
    """Get the cache file path."""
    return get_project_root() / "cache" / "cursor_posts.json"


def get_feeds_dir():
    """Get the feeds directory path."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_page(url):
    """Fetch a single page HTML."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def parse_posts(html):
    """Extract posts from HTML. Returns (posts, next_page_url or None)."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for card in soup.find_all("a", class_=re.compile(r"card")):
        href = card.get("href", "")
        if "/blog/" not in href or "/topic/" in href or "/page/" in href:
            continue

        # Make URL absolute
        if href.startswith("/"):
            href = f"https://cursor.com{href}"

        ps = card.find_all("p")
        title = ps[0].get_text(strip=True) if ps else ""
        description = ps[1].get_text(strip=True) if len(ps) > 1 else ""

        time_el = card.find("time")
        date = time_el.get("datetime", "") if time_el else ""

        category_el = card.find("span", class_="capitalize")
        category = category_el.get_text(strip=True).rstrip(" ·") if category_el else ""

        posts.append({
            "url": href,
            "title": title,
            "description": description,
            "date": date,
            "category": category,
        })

    # Find next page link - look for links containing "Next" or "Older"
    next_link = None
    for link in soup.find_all("a", href=re.compile(r"/blog/page/\d+")):
        link_text = link.get_text(strip=True)
        if "Next" in link_text or "Older" in link_text:
            next_link = link
            break

    next_url = None
    if next_link:
        href = next_link.get("href")
        # Make relative URLs absolute
        if href.startswith("/"):
            next_url = f"https://cursor.com{href}"
        else:
            next_url = href

    return posts, next_url


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
    """Follow pagination until no Next link. Returns all posts."""
    all_posts = []
    url = BLOG_URL
    page_num = 1

    while url:
        logger.info(f"Fetching page {page_num}: {url}")
        html = fetch_page(url)
        posts, next_url = parse_posts(html)
        all_posts.extend(posts)
        logger.info(f"Found {len(posts)} posts on page {page_num}")

        url = next_url
        page_num += 1

    # Dedupe by URL (in case of overlaps)
    seen = set()
    unique_posts = []
    for post in all_posts:
        if post["url"] not in seen:
            unique_posts.append(post)
            seen.add(post["url"])

    # Sort for correct feed order (newest first in output)
    sorted_posts = sort_posts_for_feed(unique_posts, date_field="date")
    logger.info(f"Total unique posts across all pages: {len(sorted_posts)}")
    return sorted_posts


def generate_rss_feed(posts):
    """Generate RSS feed from posts."""
    fg = FeedGenerator()
    fg.title("Cursor Blog")
    fg.description("The AI Code Editor")
    fg.language("en")
    fg.author({"name": "Cursor"})
    fg.logo("https://cursor.com/favicon.ico")
    fg.subtitle("Latest updates from Cursor")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["url"])
        fe.id(post["url"])

        if post.get("date"):
            try:
                dt = datetime.fromisoformat(post["date"].replace("Z", "+00:00"))
                fe.published(dt)
            except ValueError:
                pass

        if post.get("category"):
            fe.category(term=post["category"])

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def save_rss_feed(feed_generator):
    """Save the RSS feed to a file."""
    feeds_dir = get_feeds_dir()
    output_file = feeds_dir / f"feed_{FEED_NAME}.xml"
    feed_generator.rss_file(str(output_file), pretty=True)
    logger.info(f"Saved RSS feed to {output_file}")
    return output_file


def main(full_reset=False):
    """Main function to generate RSS feed."""
    cache = load_cache()

    if full_reset or not cache["posts"]:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
        posts = fetch_all_pages()
    else:
        logger.info("Running incremental update (page 1 only)")
        html = fetch_page(BLOG_URL)
        new_posts, _ = parse_posts(html)
        logger.info(f"Found {len(new_posts)} posts on page 1")
        posts = merge_posts(new_posts, cache["posts"])

    save_cache(posts)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed)

    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Cursor Blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch all pages)")
    args = parser.parse_args()
    main(full_reset=args.full)
