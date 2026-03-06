import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import pytz
import requests
from feedgen.feed import FeedGenerator
from utils import setup_feed_links, sort_posts_for_feed

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BLOG_URL = "https://blog.langchain.com"
FEED_NAME = "langchain"

# Ghost Content API (public key exposed in page source)
GHOST_API_URL = "https://langchain-blog.ghost.io/ghost/api/content/posts/"
GHOST_API_KEY = "e411fdfa6f54398669f416d1f0"
POSTS_PER_PAGE = 15


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_cache_file():
    """Get the cache file path."""
    return get_project_root() / "cache" / "langchain_posts.json"


def get_feeds_dir():
    """Get the feeds directory path."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_page(page_num):
    """Fetch a single page of posts from the Ghost Content API."""
    params = {
        "key": GHOST_API_KEY,
        "limit": POSTS_PER_PAGE,
        "page": page_num,
        "fields": "title,url,slug,published_at,excerpt,feature_image",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(GHOST_API_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_api_response(data):
    """Extract posts from Ghost API response. Returns (posts, has_next_page)."""
    posts = []
    for item in data.get("posts", []):
        post = {
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "description": item.get("excerpt", ""),
            "date": item.get("published_at", ""),
        }
        if post["url"] and post["title"]:
            posts.append(post)

    pagination = data.get("meta", {}).get("pagination", {})
    has_next = pagination.get("next") is not None

    return posts, has_next


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
    """Fetch all pages from the Ghost API. Returns all posts."""
    all_posts = []
    page_num = 1

    while True:
        logger.info(f"Fetching page {page_num}")
        data = fetch_page(page_num)
        posts, has_next = parse_api_response(data)
        all_posts.extend(posts)
        logger.info(f"Found {len(posts)} posts on page {page_num}")

        if not has_next:
            break
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
    fg.title("LangChain Blog")
    fg.description("Latest updates from the LangChain team")
    fg.language("en")
    fg.author({"name": "LangChain"})
    fg.logo(
        "https://blog.langchain.com/content/images/size/w256h256/2024/03/Twitter_ProfilePicture.png"
    )
    fg.subtitle("LangChain Blog - product updates, agent engineering, and more")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["url"])
        fe.id(post["url"])

        if post.get("date"):
            try:
                dt = datetime.fromisoformat(post["date"])
                fe.published(dt)
            except ValueError:
                pass

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
        data = fetch_page(1)
        new_posts, _ = parse_api_response(data)
        logger.info(f"Found {len(new_posts)} posts on page 1")
        posts = merge_posts(new_posts, cache["posts"])

    save_cache(posts)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed)

    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate LangChain Blog RSS feed")
    parser.add_argument(
        "--full", action="store_true", help="Force full reset (fetch all pages)"
    )
    args = parser.parse_args()
    main(full_reset=args.full)
