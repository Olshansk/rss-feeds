"""Generate RSS feed for the Weaviate Blog (https://weaviate.io/blog).

Docusaurus-based blog with /page/N pagination. Static HTML; no JS rendering needed.
"""

import argparse
from datetime import datetime

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
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "weaviate"
BLOG_URL = "https://weaviate.io/blog"
MAX_PAGES_FULL = 5


def parse_posts(html_content: str) -> tuple[list[dict], bool]:
    """Extract posts from a single page. Returns (posts, has_next_page)."""
    soup = BeautifulSoup(html_content, "html.parser")
    posts = []

    for article in soup.select("article.margin-bottom--xl"):
        title_elem = article.select_one("h2")
        if not title_elem:
            continue
        title = title_elem.text.strip()

        url_elem = article.select_one('a[itemprop="url"]')
        if not url_elem or not url_elem.get("href"):
            continue
        link = url_elem["href"]
        if link.startswith("/"):
            link = f"https://weaviate.io{link}"

        date = None
        time_elem = article.select_one("time[datetime]")
        if time_elem and time_elem.get("datetime"):
            try:
                date = datetime.fromisoformat(time_elem["datetime"].replace("Z", "+00:00"))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=pytz.UTC)
            except ValueError:
                logger.warning(f"Could not parse datetime: {time_elem['datetime']}")
        if not date:
            date = stable_fallback_date(link)

        desc_elem = article.select_one('meta[itemprop="description"]')
        description = desc_elem["content"] if desc_elem and desc_elem.get("content") else title

        posts.append(
            {
                "link": link,
                "title": title,
                "date": date,
                "description": description,
            }
        )

    has_next_page = soup.select_one("a.pagination-nav__link--next") is not None
    return posts, has_next_page


def fetch_all_pages(max_pages: int = MAX_PAGES_FULL) -> list[dict]:
    """Follow /page/N pagination up to max_pages (or until no next link)."""
    all_posts = []
    for page_num in range(1, max_pages + 1):
        url = BLOG_URL if page_num == 1 else f"{BLOG_URL}/page/{page_num}"
        logger.info(f"Fetching page {page_num}: {url}")
        html = fetch_page(url)
        posts, has_next_page = parse_posts(html)
        all_posts.extend(posts)
        logger.info(f"Found {len(posts)} posts on page {page_num}")
        if not has_next_page:
            break

    seen = set()
    unique_posts = []
    for post in all_posts:
        if post["link"] not in seen:
            unique_posts.append(post)
            seen.add(post["link"])

    logger.info(f"Total unique posts across all pages: {len(unique_posts)}")
    return sort_posts_for_feed(unique_posts, date_field="date")


def generate_rss_feed(posts: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("Weaviate Blog")
    fg.description(
        "Read the latest from the Weaviate team: insights, tutorials, and updates on "
        "vector databases, AI-native applications, and search."
    )
    fg.language("en")
    fg.author({"name": "Weaviate"})
    fg.subtitle("Latest updates from Weaviate")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post["link"])
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
        posts = fetch_all_pages()
    else:
        logger.info("Running incremental update (page 1 only)")
        html = fetch_page(BLOG_URL)
        new_posts, _ = parse_posts(html)
        logger.info(f"Found {len(new_posts)} posts on page 1")
        posts = merge_entries(new_posts, cached_entries)

    save_cache(FEED_NAME, posts)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed, FEED_NAME)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Weaviate Blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch all pages)")
    args = parser.parse_args()
    main(full_reset=args.full)
