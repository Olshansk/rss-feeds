"""Shared helpers for Hugging Face blog tag feeds."""

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

logger = setup_logging(__name__)

HF_API_URL = "https://huggingface.co/api/blog"
HF_BASE_URL = "https://huggingface.co"
API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RSS Feed Generator)",
    "Accept": "application/json",
}


def fetch_posts_page(tag: str, page: int) -> dict:
    """Fetch a single page of blog posts for a tag from the Hugging Face API."""
    response = requests.get(
        HF_API_URL,
        params={"tag": tag, "p": page},
        headers=API_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def parse_api_posts(blogs: list[dict]) -> list[dict]:
    """Extract post dicts from Hugging Face API blog objects."""
    posts = []
    for blog in blogs:
        title = (blog.get("title") or "").strip()
        if not title:
            continue

        url = blog.get("url") or f"/blog/{blog.get('slug', '')}"
        link = f"{HF_BASE_URL}{url}" if url.startswith("/") else url

        date = None
        published_at = blog.get("publishedAt")
        if published_at:
            try:
                date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=pytz.UTC)
            except ValueError:
                logger.warning(f"Could not parse date for: {title}")
        if not date:
            date = stable_fallback_date(link)

        tags = blog.get("tags") or []
        description = title
        if tags:
            description = f"{title} ({', '.join(tags)})"

        posts.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "description": description,
                "category": tags[0] if tags else "Blog",
            }
        )
    return posts


def fetch_all_posts(tag: str) -> list[dict]:
    """Fetch all posts for a tag across paginated API results."""
    all_posts: list[dict] = []
    seen_links: set[str] = set()
    page = 0

    while True:
        logger.info(f"Fetching page {page} for tag={tag!r}")
        api_data = fetch_posts_page(tag, page)
        blogs = api_data.get("allBlogs", [])
        if not blogs:
            logger.info(f"No posts returned on page {page}, stopping")
            break

        page_posts = parse_api_posts(blogs)
        for post in page_posts:
            if post["link"] not in seen_links:
                all_posts.append(post)
                seen_links.add(post["link"])

        total = api_data.get("numTotalItems", len(all_posts))
        logger.info(f"Page {page}: {len(page_posts)} posts (total: {len(all_posts)}/{total})")
        if len(all_posts) >= total:
            break
        page += 1

    return all_posts


def fetch_latest_posts(tag: str) -> list[dict]:
    """Fetch only the newest page of posts for incremental updates."""
    api_data = fetch_posts_page(tag, page=0)
    posts = parse_api_posts(api_data.get("allBlogs", []))
    logger.info(f"Fetched {len(posts)} latest posts for tag={tag!r}")
    return posts


def generate_rss_feed(
    posts: list[dict],
    *,
    feed_name: str,
    blog_url: str,
    feed_title: str,
    feed_description: str,
) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title(feed_title)
    fg.description(feed_description)
    fg.language("en")
    fg.author({"name": "Hugging Face"})
    setup_feed_links(fg, blog_url=blog_url, feed_name=feed_name)

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


def run_tag_feed(
    *,
    tag: str,
    feed_name: str,
    blog_url: str,
    feed_title: str,
    feed_description: str,
    full_reset: bool = False,
) -> bool:
    cache = load_cache(feed_name)
    cached_entries = deserialize_entries(cache.get("entries", []))

    if full_reset or not cached_entries:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode}) for tag={tag!r}")
        posts = sort_posts_for_feed(fetch_all_posts(tag), date_field="date")
    else:
        logger.info(f"Running incremental update for tag={tag!r}")
        new_posts = fetch_latest_posts(tag)
        posts = merge_entries(new_posts, cached_entries)

    if not posts:
        logger.warning(f"No posts found for tag={tag!r}. Check the Hugging Face API response.")
        return False

    save_cache(feed_name, posts)
    feed = generate_rss_feed(
        posts,
        feed_name=feed_name,
        blog_url=blog_url,
        feed_title=feed_title,
        feed_description=feed_description,
    )
    save_rss_feed(feed, feed_name)
    logger.info("Done!")
    return True
