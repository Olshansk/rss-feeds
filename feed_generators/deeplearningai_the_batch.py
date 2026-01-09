import logging
import re
from datetime import datetime
from pathlib import Path

import pytz
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from feedgen.feed import FeedGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
BLOG_URL = "https://www.deeplearning.ai/the-batch/"
MAX_PAGES = 30  # Safety limit for pagination


def ensure_feeds_directory() -> Path:
    feeds_dir = PROJECT_ROOT / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_page(url: str) -> str:
    """Fetch a page using requests with proper headers."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def parse_date(value: str | None) -> datetime:
    """Parse date text/datetime strings into timezone-aware datetime."""
    if not value:
        return datetime.now(tz=pytz.UTC)
    try:
        dt = date_parser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        return dt
    except (ValueError, TypeError) as exc:
        logger.warning("Unable to parse date %r (%s); using current time", value, exc)
        return datetime.now(tz=pytz.UTC)


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
        published = parse_date(date_text)
        description = extract_description(article) or title

        articles.append({"title": title, "link": link, "published": published, "description": description})

    return articles


def fetch_all_articles() -> list[dict]:
    """Fetch all articles by iterating through paginated pages."""
    all_articles = []
    seen_links = set()

    for page_num in range(1, MAX_PAGES + 1):
        # Construct page URL
        if page_num == 1:
            url = BLOG_URL
        else:
            url = f"{BLOG_URL}page/{page_num}/"

        logger.info(f"Fetching page {page_num}: {url}")

        try:
            html_content = fetch_page(url)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.info(f"Page {page_num} not found, stopping pagination")
                break
            raise

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

    logger.info(f"Total articles fetched: {len(all_articles)}")
    return all_articles


def build_feed(articles: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("The Batch | DeepLearning.AI")
    fg.link(href=BLOG_URL, rel="alternate")
    fg.link(href=f"{BLOG_URL}feed_the_batch.xml", rel="self")
    fg.description("Weekly AI news and insights from DeepLearning.AI's The Batch.")
    fg.language("en")

    for article in sorted(articles, key=lambda a: a["published"], reverse=True):
        entry = fg.add_entry()
        entry.title(article["title"])
        entry.link(href=article["link"])
        entry.id(article["link"])
        entry.published(article["published"])
        entry.description(article["description"])

    return fg


def save_feed(feed: FeedGenerator, feed_name: str = "the_batch") -> Path:
    output_path = ensure_feeds_directory() / f"feed_{feed_name}.xml"
    feed.rss_file(str(output_path), pretty=True)
    logger.info("Wrote feed to %s", output_path)
    return output_path


def main():
    articles = fetch_all_articles()

    if not articles:
        logger.warning("No articles found")
        return False

    feed = build_feed(articles)
    save_feed(feed, "the_batch")
    logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
    return True


if __name__ == "__main__":
    main()
