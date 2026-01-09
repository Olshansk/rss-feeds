import argparse
import json
import logging
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

from utils import get_cache_dir, get_feeds_dir, setup_feed_links, sort_posts_for_feed

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

FEED_NAME = "the_batch"
BLOG_URL = "https://www.deeplearning.ai/the-batch/"
MAX_PAGES = 30  # Safety limit for pagination


def stable_fallback_date(identifier):
    """Generate a stable date from a URL or title hash."""
    hash_val = abs(hash(identifier)) % 730  # ~2 years of days
    epoch = datetime(2023, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
    return epoch + timedelta(days=hash_val)


def get_cache_file():
    """Get the cache file path."""
    return get_cache_dir() / f"{FEED_NAME}_posts.json"


def load_cache():
    """Load existing cache or return empty structure."""
    cache_file = get_cache_file()
    if cache_file.exists():
        with open(cache_file, "r") as f:
            data = json.load(f)
            logger.info(f"Loaded cache with {len(data.get('articles', []))} articles")
            return data
    logger.info("No cache file found, will do full fetch")
    return {"last_updated": None, "articles": []}


def save_cache(articles):
    """Save articles to cache file."""
    cache_file = get_cache_file()
    serializable_articles = []
    for article in articles:
        article_copy = article.copy()
        if isinstance(article_copy.get("published"), datetime):
            article_copy["published"] = article_copy["published"].isoformat()
        serializable_articles.append(article_copy)

    data = {
        "last_updated": datetime.now(pytz.UTC).isoformat(),
        "articles": serializable_articles,
    }
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved cache with {len(articles)} articles to {cache_file}")


def deserialize_articles(articles):
    """Convert cached articles back to proper format with datetime objects."""
    result = []
    for article in articles:
        article_copy = article.copy()
        if isinstance(article_copy.get("published"), str):
            try:
                article_copy["published"] = datetime.fromisoformat(article_copy["published"])
            except ValueError:
                article_copy["published"] = stable_fallback_date(article_copy.get("link", ""))
        result.append(article_copy)
    return result


def merge_articles(new_articles, cached_articles):
    """Merge new articles into cache, dedupe by link, sort by date desc."""
    existing_links = {a["link"] for a in cached_articles}
    merged = list(cached_articles)

    added_count = 0
    for article in new_articles:
        if article["link"] not in existing_links:
            merged.append(article)
            existing_links.add(article["link"])
            added_count += 1

    logger.info(f"Added {added_count} new articles to cache")
    return sort_posts_for_feed(merged, date_field="published")


def setup_selenium_driver():
    """Set up Selenium WebDriver with undetected-chromedriver."""
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    return uc.Chrome(options=options)


def fetch_page(driver, url: str) -> str:
    """Fetch a page using Selenium with proper waits."""
    logger.info(f"Fetching: {url}")
    driver.get(url)
    time.sleep(3)  # Wait for page to load
    return driver.page_source


def parse_date(value: str | None, fallback_id: str = "") -> datetime:
    """Parse date text/datetime strings into timezone-aware datetime."""
    if not value:
        return stable_fallback_date(fallback_id)
    try:
        dt = date_parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt
    except (ValueError, TypeError) as exc:
        logger.warning("Unable to parse date %r (%s); using fallback", value, exc)
        return stable_fallback_date(fallback_id)


def clean_text(text: str | None) -> str | None:
    if text is None:
        return None
    return " ".join(text.split())


def extract_article_link(article) -> str | None:
    """Return first article link excluding tag links. Handles relative URLs."""
    for anchor in article.find_all("a", href=True):
        href = anchor["href"]
        # Skip tag links
        if "/tag/" in href:
            continue
        # Match both absolute and relative URLs to /the-batch/
        if href.startswith("/the-batch/") or "deeplearning.ai/the-batch" in href:
            # Convert relative to absolute URL
            if href.startswith("/"):
                return f"https://www.deeplearning.ai{href}"
            return href
    return None


def extract_date_text(article) -> str | None:
    time_el = article.find("time")
    if time_el:
        return time_el.get("datetime") or time_el.get_text(" ", strip=True)

    # Featured card uses a pill with plain text (e.g., "Dec 26, 2025")
    date_pattern = re.compile(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}",
        re.I,
    )
    for tag in article.find_all(["a", "div", "span"]):
        text = tag.get_text(" ", strip=True)
        match = date_pattern.search(text or "")
        if match:
            return match.group(0)
    return None


def extract_description(article) -> str | None:
    # Prefer visible snippet if present (line clamp text)
    summary = article.find(
        lambda tag: tag.name in {"div", "p"} and tag.get("class") and any("line-clamp" in cls for cls in tag.get("class"))
    )
    if summary:
        return clean_text(summary.get_text(" ", strip=True))

    first_para = article.find("p")
    if first_para:
        return clean_text(first_para.get_text(" ", strip=True))

    return None


def parse_articles_from_html(html_content: str) -> list[dict]:
    """Parse articles from HTML content string."""
    soup = BeautifulSoup(html_content, "lxml")
    articles = []

    for article in soup.find_all("article"):
        heading = article.find(["h1", "h2", "h3", "h4"])
        if not heading:
            continue

        title = clean_text(heading.get_text(" ", strip=True))
        link = extract_article_link(article)
        if not title or not link:
            continue

        date_text = extract_date_text(article)
        published = parse_date(date_text, fallback_id=link)
        description = extract_description(article) or title

        articles.append({"title": title, "link": link, "published": published, "description": description})

    return articles


def fetch_all_articles(max_pages: int = MAX_PAGES) -> list[dict]:
    """Fetch all articles by iterating through paginated pages using Selenium."""
    all_articles = []
    seen_links = set()
    driver = None

    try:
        driver = setup_selenium_driver()

        for page_num in range(1, max_pages + 1):
            # Construct page URL
            if page_num == 1:
                url = BLOG_URL
            else:
                url = f"{BLOG_URL}page/{page_num}/"

            try:
                html_content = fetch_page(driver, url)
            except Exception as e:
                logger.info(f"Error fetching page {page_num}, stopping pagination: {e}")
                break

            # Check for 404-like conditions (page not found)
            if "Page not found" in html_content or "404" in html_content[:1000]:
                logger.info(f"Page {page_num} not found, stopping pagination")
                break

            # Parse articles from current page
            page_articles = parse_articles_from_html(html_content)

            if not page_articles:
                logger.info(f"No articles found on page {page_num}, stopping pagination")
                break

            # Deduplicate and add new articles
            new_count = 0
            for article in page_articles:
                if article["link"] not in seen_links:
                    seen_links.add(article["link"])
                    all_articles.append(article)
                    new_count += 1

            logger.info(f"Page {page_num}: Found {len(page_articles)} articles, {new_count} new")

            if new_count == 0:
                logger.info("No new articles found, stopping pagination")
                break

    finally:
        if driver:
            driver.quit()

    logger.info(f"Total articles fetched: {len(all_articles)}")
    return all_articles


def build_feed(articles: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("The Batch | DeepLearning.AI")
    fg.description("Weekly AI news and insights from DeepLearning.AI's The Batch.")
    fg.language("en")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    # Sort articles for correct feed order (newest first in output)
    articles_sorted = sort_posts_for_feed(articles, date_field="published")

    for article in articles_sorted:
        entry = fg.add_entry()
        entry.title(article["title"])
        entry.link(href=article["link"])
        entry.id(article["link"])
        entry.published(article["published"])
        entry.description(article["description"])

    return fg


def save_feed(feed: FeedGenerator) -> Path:
    output_path = get_feeds_dir() / f"feed_{FEED_NAME}.xml"
    feed.rss_file(str(output_path), pretty=True)
    logger.info("Wrote feed to %s", output_path)
    return output_path


def main(full_reset=False):
    """Main function to generate RSS feed.

    Args:
        full_reset: If True, fetch all pages. If False, fetch only first 3 pages and merge with cache.
    """
    cache = load_cache()
    cached_articles = deserialize_articles(cache.get("articles", []))

    if full_reset or not cached_articles:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
        articles = fetch_all_articles(max_pages=MAX_PAGES)
    else:
        logger.info("Running incremental update (3 pages only)")
        new_articles = fetch_all_articles(max_pages=3)
        logger.info(f"Found {len(new_articles)} articles from recent pages")
        articles = merge_articles(new_articles, cached_articles)

    if not articles:
        logger.warning("No articles found")
        return False

    # Save to cache
    save_cache(articles)

    feed = build_feed(articles)
    save_feed(feed)
    logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate DeepLearning.AI The Batch RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch all pages)")
    args = parser.parse_args()
    main(full_reset=args.full)
