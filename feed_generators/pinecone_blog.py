"""Generate RSS feed for the Pinecone Blog (https://www.pinecone.io/blog/).

Selenium "Load More" pagination. Two card layouts: featured posts at the top
(title-focused) and list-view rows below (with category + date metadata).
"""

import argparse
import contextlib
import time
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from selenium.webdriver.common.by import By

from utils import (
    deserialize_entries,
    load_cache,
    merge_entries,
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    setup_selenium_driver,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "pinecone"
BLOG_URL = "https://www.pinecone.io/blog/?view=list"
DISPLAY_URL = "https://www.pinecone.io/blog/"
MAX_CLICKS_FULL = 15
MAX_CLICKS_INCREMENTAL = 3


def fetch_blog_content(max_clicks: int = MAX_CLICKS_FULL) -> str:
    """Load the blog and click "Load More" up to max_clicks times."""
    driver = None
    try:
        logger.info(f"Fetching content from {BLOG_URL} (max_clicks={max_clicks})")
        driver = setup_selenium_driver()
        driver.get(BLOG_URL)
        time.sleep(5)

        clicks = 0
        while clicks < max_clicks:
            try:
                load_more = driver.find_element(
                    By.XPATH,
                    "//button[.//span[text()='Load More'] or text()='Load More']",
                )
            except Exception:
                logger.info(f"No more 'Load More' button found after {clicks} clicks")
                break

            if not load_more.is_displayed():
                logger.info("'Load More' button not visible, stopping")
                break

            logger.info(f"Clicking 'Load More' (click {clicks + 1})")
            driver.execute_script("arguments[0].click();", load_more)
            clicks += 1
            time.sleep(2)

        logger.info(f"Fetched page source after {clicks} clicks")
        return driver.page_source
    finally:
        if driver:
            driver.quit()


def _parse_short_date(text: str) -> datetime | None:
    text = text.strip()
    if not text:
        return None
    with contextlib.suppress(ValueError):
        return datetime.strptime(text, "%b %d, %Y").replace(tzinfo=pytz.UTC)
    return None


def parse_blog_html(html: str) -> list[dict]:
    """Extract posts from the featured section and the list-view rows."""
    soup = BeautifulSoup(html, "html.parser")
    posts: list[dict] = []
    seen_links: set[str] = set()

    # Featured posts at the top of the page
    for card in soup.select('a[href^="/blog/"][href$="/"]'):
        href = card.get("href", "")
        if href.rstrip("/") == "/blog" or "/tag" in href:
            continue

        title_elem = card.select_one("h2")
        if not title_elem:
            continue
        title = title_elem.text.strip()

        link = f"https://www.pinecone.io{href}"
        if link in seen_links:
            continue
        seen_links.add(link)

        date_elem = card.select_one("span.text-text-secondary")
        date = _parse_short_date(date_elem.text) if date_elem else None
        if not date:
            date = stable_fallback_date(link)

        cat_elem = card.select_one("span.text-brand-blue, span[class*='brand']")
        category = cat_elem.text.strip() if cat_elem else ""

        posts.append(
            {
                "link": link,
                "title": title,
                "date": date,
                "category": category,
                "description": title,
            }
        )

    # List-view rows
    for row in soup.select('a[target="_self"][href^="/blog/"]'):
        href = row.get("href", "")
        link = f"https://www.pinecone.io{href}"
        if link in seen_links:
            continue
        seen_links.add(link)

        title_elem = row.select_one("div.text-xl")
        title = title_elem.text.strip() if title_elem else ""
        if not title:
            continue

        secondary_divs = row.select("div.text-text-secondary")
        category = secondary_divs[0].text.strip() if len(secondary_divs) > 0 else ""
        date_text = secondary_divs[1].text.strip() if len(secondary_divs) > 1 else ""
        date = _parse_short_date(date_text) or stable_fallback_date(link)

        posts.append(
            {
                "link": link,
                "title": title,
                "date": date,
                "category": category,
                "description": title,
            }
        )

    logger.info(f"Parsed {len(posts)} posts")
    return posts


def generate_rss_feed(posts: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("Pinecone Blog")
    fg.description("Latest from Pinecone: insights, tutorials, and updates on vector databases and AI infrastructure.")
    fg.language("en")
    fg.author({"name": "Pinecone"})
    fg.subtitle("Latest updates from Pinecone")
    setup_feed_links(fg, blog_url=DISPLAY_URL, feed_name=FEED_NAME)

    for post in sort_posts_for_feed(posts, date_field="date"):
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post["link"])
        if post.get("category"):
            fe.category(term=post["category"])
        if post.get("date"):
            fe.published(post["date"])

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def main(full_reset: bool = False) -> bool:
    cache = load_cache(FEED_NAME)
    cached_entries = deserialize_entries(cache.get("entries", []))

    clicks = MAX_CLICKS_FULL if (full_reset or not cached_entries) else MAX_CLICKS_INCREMENTAL
    html = fetch_blog_content(max_clicks=clicks)
    new_posts = parse_blog_html(html)

    if cached_entries and not full_reset:
        posts = merge_entries(new_posts, cached_entries)
    else:
        posts = sort_posts_for_feed(new_posts, date_field="date")

    if not posts:
        logger.warning("No posts found. Check the HTML structure.")
        return False

    save_cache(FEED_NAME, posts)
    feed = generate_rss_feed(posts)
    save_rss_feed(feed, FEED_NAME)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Pinecone Blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (Load More up to 15 times)")
    args = parser.parse_args()
    main(full_reset=args.full)
