import argparse
import time
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utils import (deserialize_entries, load_cache, merge_entries, save_cache,
                   save_rss_feed, setup_feed_links, setup_logging,
                   setup_selenium_driver, sort_posts_for_feed,
                   stable_fallback_date)

logger = setup_logging()

FEED_NAME = "xainews"
BLOG_URL = "https://x.ai/news"


def fetch_news_content(url=BLOG_URL):
    """Fetch the fully loaded HTML content of xAI's news page using Selenium.

    The xAI news page is JS-rendered, so a simple HTTP request returns an empty
    shell. We need Selenium to wait for the content to load.
    """
    driver = None
    try:
        logger.info(f"Fetching content from URL: {url}")
        driver = setup_selenium_driver()
        driver.get(url)

        # Wait for news articles to load
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/news/']"))
            )
            logger.info("News articles loaded successfully")
        except Exception:
            logger.warning("Could not confirm articles loaded, proceeding anyway...")

        # Allow additional time for all dynamic content
        time.sleep(2)

        html_content = driver.page_source
        logger.info("Successfully fetched HTML content")
        return html_content

    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        raise
    finally:
        if driver:
            driver.quit()


def parse_date(date_text):
    """Parse date from various formats used on xAI news page."""
    date_formats = [
        "%B %d, %Y",  # September 19, 2025
        "%b %d, %Y",  # Sep 19, 2025
        "%B %d %Y",
        "%b %d %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]

    date_text = date_text.strip()
    for date_format in date_formats:
        try:
            date = datetime.strptime(date_text, date_format)
            return date.replace(tzinfo=pytz.UTC)
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_text}")
    return None


MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def looks_like_date(text):
    """Check if text looks like a date string."""
    return any(month in text for month in MONTH_NAMES)


def extract_articles(soup):
    """Extract article information from the parsed HTML."""
    articles = []
    seen_links = set()

    # Find all article containers
    article_containers = soup.select("div.group.relative")
    logger.info(f"Found {len(article_containers)} potential article containers")

    for container in article_containers:
        try:
            # Extract the link and title
            title_link = container.select_one('a[href*="/news/"]')
            if not title_link:
                continue

            href = title_link.get("href", "")
            if not href:
                continue

            # Build full URL
            link = f"https://x.ai{href}" if href.startswith("/") else href

            # Skip duplicates
            if link in seen_links:
                continue

            # Skip the main news page link
            if link.endswith("/news") or link.endswith("/news/"):
                continue

            seen_links.add(link)

            # Extract title - can be in h3 or h4
            title_elem = title_link.select_one("h3, h4")
            if not title_elem:
                logger.debug(f"Could not extract title for link: {link}")
                continue

            title = title_elem.text.strip()

            # Extract description
            description_elem = container.select_one("p.text-secondary")
            description = description_elem.text.strip() if description_elem else title

            # Extract date - try multiple selectors
            date = None

            # First try: featured article format
            date_elem = container.select_one("p.mono-tag.text-xs.leading-6")
            if date_elem:
                date_text = date_elem.text.strip()
                if looks_like_date(date_text):
                    date = parse_date(date_text)

            # Second try: standard article format in footer
            if not date:
                footer_elements = container.select(
                    "div.flex.items-center.justify-between span.mono-tag.text-xs"
                )
                for elem in footer_elements:
                    text = elem.text.strip()
                    if looks_like_date(text):
                        date = parse_date(text)
                        break

            # Fallback: use stable date
            if not date:
                logger.warning(f"Could not extract date for article: {title}")
                date = stable_fallback_date(link)

            # Extract category
            category = "News"
            category_elem = container.select_one(
                "div:not(.flex.items-center.justify-between) span.mono-tag.text-xs"
            )
            if category_elem:
                category_text = category_elem.text.strip().lower()
                if not looks_like_date(category_text):
                    category = category_text.capitalize()

            article = {
                "title": title,
                "link": link,
                "date": date,
                "category": category,
                "description": description,
            }

            articles.append(article)
            logger.debug(f"Extracted article: {title} ({date})")

        except Exception as e:
            logger.warning(f"Error parsing article container: {str(e)}")
            continue

    logger.info(f"Successfully parsed {len(articles)} articles")
    return articles


def parse_news_html(html_content):
    """Parse the news HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        return extract_articles(soup)
    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles):
    """Generate RSS feed from news articles."""
    fg = FeedGenerator()
    fg.title("xAI News")
    fg.description("Latest news and updates from xAI")
    fg.language("en")

    fg.author({"name": "xAI"})
    fg.subtitle("Latest updates from xAI")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    # Sort articles for correct feed order (newest first in output)
    articles_sorted = sort_posts_for_feed(articles, date_field="date")

    for article in articles_sorted:
        fe = fg.add_entry()
        fe.title(article["title"])
        fe.description(article["description"])
        fe.link(href=article["link"])
        fe.published(article["date"])
        fe.category(term=article["category"])
        fe.id(article["link"])

    logger.info("Successfully generated RSS feed")
    return fg


def main(full_reset=False):
    """Main function to generate RSS feed from xAI's news page.

    Args:
        full_reset: If True, ignore cache and fetch fresh.
                   If False, merge with cached articles.
    """
    try:
        cache = load_cache(FEED_NAME)
        cached_articles = deserialize_entries(cache.get("entries", []))

        if full_reset or not cached_articles:
            mode = "full reset" if full_reset else "no cache exists"
            logger.info(f"Running full fetch ({mode})")
        else:
            logger.info("Running incremental update")

        # Fetch news content using Selenium (xAI is JS-rendered)
        html_content = fetch_news_content()

        # Parse articles from HTML
        new_articles = parse_news_html(html_content)

        if not new_articles and not cached_articles:
            logger.warning("No articles found!")
            return False

        # Merge with cache or use fresh articles
        if cached_articles and not full_reset:
            articles = merge_entries(new_articles, cached_articles)
        else:
            articles = new_articles

        # Save to cache
        save_cache(FEED_NAME, articles)

        # Generate and save RSS feed
        feed = generate_rss_feed(articles)
        save_rss_feed(feed, FEED_NAME)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate xAI News RSS feed")
    parser.add_argument(
        "--full", action="store_true", help="Force full reset (fetch all articles)"
    )
    args = parser.parse_args()
    main(full_reset=args.full)
