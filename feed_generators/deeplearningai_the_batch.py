import argparse
import re

import pytz
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
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

FEED_NAME = "the_batch"
BLOG_URL = "https://www.deeplearning.ai/the-batch/"
MAX_PAGES = 30  # Safety limit for pagination



def parse_date(value: str | None, fallback_id: str = ""):
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


def is_valid_article_link(href: str) -> bool:
    """Check if href is a valid article link (not a tag, category, or page link)."""
    if not href:
        return False
    # Skip tag links, page links, and the main batch page
    if "/tag/" in href or "/page/" in href:
        return False
    if href in ("/the-batch/", "/the-batch"):
        return False
    # Must be a the-batch article link
    if href.startswith("/the-batch/") or "deeplearning.ai/the-batch/" in href:
        return True
    return False


def normalize_link(href: str) -> str:
    """Convert relative URL to absolute URL."""
    if href.startswith("/"):
        return f"https://www.deeplearning.ai{href}"
    return href


def extract_date_text(element) -> str | None:
    """Extract date text from element or its children.

    Looks for:
    - <time> elements with datetime attribute
    - Tag links like <a href="/the-batch/tag/jan-16-2026/">Jan 16, 2026</a>
    - Plain text matching date patterns
    """
    if element is None:
        return None

    # Check for time element
    time_el = element.find("time")
    if time_el:
        return time_el.get("datetime") or time_el.get_text(" ", strip=True)

    # Check for date in tag links (new format)
    for anchor in element.find_all("a", href=True):
        href = anchor.get("href", "")
        if "/tag/" in href:
            text = anchor.get_text(" ", strip=True)
            if text:
                return text

    # Date pattern for plain text (e.g., "Dec 26, 2025" or "January 16, 2026")
    date_pattern = re.compile(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}",
        re.I,
    )
    for tag in element.find_all(["a", "div", "span", "p"]):
        text = tag.get_text(" ", strip=True)
        match = date_pattern.search(text or "")
        if match:
            return match.group(0)

    # Check element's own text
    text = (
        element.get_text(" ", strip=True)
        if hasattr(element, "get_text")
        else str(element)
    )
    match = date_pattern.search(text or "")
    if match:
        return match.group(0)

    return None


def extract_description(element) -> str | None:
    """Extract description/excerpt from element or its parent context."""
    if element is None:
        return None

    # Prefer visible snippet if present (line clamp text)
    summary = element.find(
        lambda tag: tag.name in {"div", "p"}
        and tag.get("class")
        and any("line-clamp" in cls for cls in (tag.get("class") or []))
    )
    if summary:
        return clean_text(summary.get_text(" ", strip=True))

    # Check parent for description
    parent = element.parent
    if parent:
        summary = parent.find(
            lambda tag: tag.name in {"div", "p"}
            and tag.get("class")
            and any("line-clamp" in cls for cls in (tag.get("class") or []))
        )
        if summary:
            return clean_text(summary.get_text(" ", strip=True))

        first_para = parent.find("p")
        if first_para:
            text = clean_text(first_para.get_text(" ", strip=True))
            # Skip if it looks like just a date
            if text and len(text) > 20:
                return text

    return None


def parse_articles_from_html(html_content: str) -> list[dict]:
    """Parse articles from HTML content string.

    The site uses a card-based layout without <article> tags. Articles are
    identified by finding links to /the-batch/issue-* URLs and extracting
    title/date from the link context.
    """
    soup = BeautifulSoup(html_content, "lxml")
    articles = []
    seen_links = set()

    # Find all links that point to article pages
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not is_valid_article_link(href):
            continue

        link = normalize_link(href)
        if link in seen_links:
            continue
        seen_links.add(link)

        # Extract title from heading within the link or nearby
        heading = anchor.find(["h1", "h2", "h3", "h4"])
        if not heading:
            # Try parent element for title
            parent = anchor.parent
            if parent:
                heading = parent.find(["h1", "h2", "h3", "h4"])
        if not heading:
            # Use link text as fallback
            text = clean_text(anchor.get_text(" ", strip=True))
            if text and len(text) > 10:
                title = text
            else:
                continue
        else:
            title = clean_text(heading.get_text(" ", strip=True))

        if not title:
            continue

        # Extract date - look for tag links or date patterns near the link
        date_text = extract_date_text(anchor)
        if not date_text:
            # Check parent/sibling elements
            parent = anchor.parent
            if parent:
                date_text = extract_date_text(parent)
        date = parse_date(date_text, fallback_id=link)

        # Extract description from nearby paragraph or use title
        description = extract_description(anchor) or title

        articles.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "description": description,
            }
        )

    logger.info(f"Parsed {len(articles)} articles from HTML")
    return articles


def fetch_all_articles(max_pages: int = MAX_PAGES) -> list[dict]:
    """Fetch all articles by iterating through paginated pages."""
    all_articles = []
    seen_links = set()

    for page_num in range(1, max_pages + 1):
        # Construct page URL
        if page_num == 1:
            url = BLOG_URL
        else:
            url = f"{BLOG_URL}page/{page_num}/"

        try:
            html_content = fetch_page(url)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.info(f"Page {page_num} not found (404), stopping pagination")
            else:
                logger.info(f"Error fetching page {page_num}: {e}")
            break
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
            logger.info(
                f"No articles found on page {page_num}, stopping pagination"
            )
            break

        # Deduplicate and add new articles
        new_count = 0
        for article in page_articles:
            if article["link"] not in seen_links:
                seen_links.add(article["link"])
                all_articles.append(article)
                new_count += 1

        logger.info(
            f"Page {page_num}: Found {len(page_articles)} articles, {new_count} new"
        )

        if new_count == 0:
            logger.info("No new articles found, stopping pagination")
            break

    logger.info(f"Total articles fetched: {len(all_articles)}")
    return all_articles


def build_feed(articles: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("The Batch | DeepLearning.AI")
    fg.description("Weekly AI news and insights from DeepLearning.AI's The Batch.")
    fg.language("en")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    # Sort articles for correct feed order (newest first in output)
    articles_sorted = sort_posts_for_feed(articles, date_field="date")

    for article in articles_sorted:
        entry = fg.add_entry()
        entry.title(article["title"])
        entry.link(href=article["link"])
        entry.id(article["link"])
        entry.published(article["date"])
        entry.description(article["description"])

    return fg


def main(full_reset=False):
    """Main function to generate RSS feed.

    Args:
        full_reset: If True, fetch all pages. If False, fetch only first 3 pages and merge with cache.
    """
    cache = load_cache(FEED_NAME)
    cached_articles = deserialize_entries(cache.get("entries", []))

    if full_reset or not cached_articles:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
        articles = fetch_all_articles(max_pages=MAX_PAGES)
    else:
        logger.info("Running incremental update (3 pages only)")
        new_articles = fetch_all_articles(max_pages=3)
        logger.info(f"Found {len(new_articles)} articles from recent pages")
        articles = merge_entries(new_articles, cached_articles)

    if not articles:
        logger.warning("No articles found")
        return False

    # Save to cache
    save_cache(FEED_NAME, articles)

    feed = build_feed(articles)
    save_rss_feed(feed, FEED_NAME)
    logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate DeepLearning.AI The Batch RSS feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Force full reset (fetch all pages)"
    )
    args = parser.parse_args()
    main(full_reset=args.full)
