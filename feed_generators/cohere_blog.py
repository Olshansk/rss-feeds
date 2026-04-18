"""Generate RSS feed for the Cohere Blog (https://cohere.com/blog).

The Cohere blog is built on Ghost CMS. We fetch posts directly from the Ghost
Content API instead of scraping HTML.
"""

import argparse
from datetime import datetime

import pytz
import requests
from feedgen.feed import FeedGenerator

from utils import (
    deserialize_entries,
    load_cache,
    merge_entries,
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "cohere"
BLOG_URL = "https://cohere.com/blog"
GHOST_API_URL = "https://cohere-ai.ghost.io/ghost/api/content/posts/"
# Ghost Content API keys are intentionally public (like a Stripe publishable
# key). This is the key the cohere.com/blog front-end itself uses; it is
# read-only and rate-limited by Ghost.
GHOST_API_KEY = "572d288a9364f8e4186af1d60a"
MAX_POSTS_FULL = 50
MAX_POSTS_INCREMENTAL = 15


def fetch_posts_page(limit: int, page: int) -> dict:
    """Fetch a single page of posts from the Ghost Content API."""
    params = {
        "key": GHOST_API_KEY,
        "limit": limit,
        "page": page,
        "include": "tags,authors",
        "order": "published_at desc",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RSS Feed Generator)",
        "Accept": "application/json",
    }
    response = requests.get(GHOST_API_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_api_posts(api_data: dict) -> list[dict]:
    """Extract post dicts from a Ghost API response."""
    posts = []
    for post in api_data.get("posts", []):
        title = (post.get("title") or "").strip()
        if not title:
            continue

        slug = post.get("slug", "")
        link = f"https://cohere.com/blog/{slug}"

        date = None
        published_at = post.get("published_at")
        if published_at:
            try:
                date = datetime.fromisoformat(published_at)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=pytz.UTC)
            except ValueError:
                logger.warning(f"Could not parse date for: {title}")
        if not date:
            date = stable_fallback_date(link)

        description = post.get("custom_excerpt") or title
        tags = post.get("tags") or []
        category = tags[0]["name"] if tags else "Blog"

        posts.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "description": description,
                "category": category,
            }
        )
    return posts


def fetch_all_posts(max_posts: int = MAX_POSTS_FULL) -> list[dict]:
    """Fetch posts across Ghost API pages until max_posts is reached."""
    all_posts = []
    page = 1
    per_page = min(max_posts, 15)

    while len(all_posts) < max_posts:
        logger.info(f"Fetching page {page} (limit={per_page})")
        api_data = fetch_posts_page(limit=per_page, page=page)
        posts = parse_api_posts(api_data)
        if not posts:
            logger.info(f"No posts returned on page {page}, stopping")
            break

        all_posts.extend(posts)
        logger.info(f"Page {page}: {len(posts)} posts (total: {len(all_posts)})")

        pagination = api_data.get("meta", {}).get("pagination", {})
        if not pagination.get("next"):
            logger.info("No more pages available")
            break
        page += 1

    return all_posts[:max_posts]


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
        fe.id(post["link"])
        fe.category(term=post["category"])
        if post.get("date"):
            fe.published(post["date"])

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def main(full_reset: bool = False) -> bool:
    cache = load_cache(FEED_NAME)
    cached_entries = deserialize_entries(cache.get("entries", []))

    if full_reset or not cached_entries:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
        new_posts = fetch_all_posts(max_posts=MAX_POSTS_FULL)
        posts = sort_posts_for_feed(new_posts, date_field="date")
    else:
        logger.info("Running incremental update")
        api_data = fetch_posts_page(limit=MAX_POSTS_INCREMENTAL, page=1)
        new_posts = parse_api_posts(api_data)
        logger.info(f"Fetched {len(new_posts)} posts from API")
        posts = merge_entries(new_posts, cached_entries)

    if not posts:
        logger.warning("No posts found. Check the Ghost API response.")
        return False

    save_cache(FEED_NAME, posts)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed, FEED_NAME)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Cohere Blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch up to 50 posts)")
    args = parser.parse_args()
    main(full_reset=args.full)
