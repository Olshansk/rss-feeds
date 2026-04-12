import argparse
import time
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from utils import (deserialize_entries, load_cache, merge_entries, save_cache,
                   save_rss_feed, setup_feed_links, setup_logging,
                   setup_selenium_driver, sort_posts_for_feed,
                   stable_fallback_date)

logger = setup_logging()

FEED_NAME = "openai_research"
BLOG_URL = "https://openai.com/news/research"


def fetch_news_content_selenium(url):
    """Fetch the fully loaded HTML content of a webpage using Selenium."""
    driver = None
    try:
        logger.info(f"Fetching content from URL: {url}")
        driver = setup_selenium_driver()
        driver.get(url)

        # Log wait time
        wait_time = 5
        logger.info(f"Waiting {wait_time} seconds for the page to fully load...")
        time.sleep(wait_time)

        html_content = driver.page_source
        logger.info("Successfully fetched HTML content")
        return html_content

    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        raise
    finally:
        if driver:
            driver.quit()


def parse_openai_news_html(html_content):
    """Parse the HTML content from OpenAI's Research News page."""
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []

    # Extract news items - look for links to research/news articles
    news_items = soup.select("a[href*='/research/'], a[href*='/index/']")

    for item in news_items:
        try:
            # Extract title
            title_elem = item.select_one("div.line-clamp-4")
            if not title_elem:
                continue
            title = title_elem.text.strip()

            # Extract link
            link = "https://openai.com" + item["href"]

            # Extract date
            date_elem = item.select_one("span.text-small")
            if date_elem:
                try:
                    date = datetime.strptime(date_elem.text.strip(), "%b %d, %Y")
                    date = date.replace(tzinfo=pytz.UTC)
                except Exception:
                    logger.warning(f"Date parsing failed for article: {title}")
                    date = stable_fallback_date(link)
            else:
                date = stable_fallback_date(link)

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "date": date,
                    "category": "Research",
                    "description": title,
                }
            )
        except Exception as e:
            logger.warning(f"Skipping an article due to parsing error: {e}")
            continue

    logger.info(f"Parsed {len(articles)} articles")
    return articles


def generate_rss_feed(articles):
    """Generate RSS feed from parsed articles."""
    fg = FeedGenerator()
    fg.title("OpenAI Research News")
    fg.description("Latest research news and updates from OpenAI")
    fg.language("en")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    # Sort articles for correct feed order (newest first in output)
    articles_sorted = sort_posts_for_feed(articles, date_field="date")

    for article in articles_sorted:
        fe = fg.add_entry()
        fe.title(article["title"])
        fe.link(href=article["link"])
        fe.description(article["description"])
        fe.published(article["date"])
        fe.category(term=article["category"])

    logger.info("RSS feed generated successfully")
    return fg


def main(full_reset=False):
    """Main function to generate OpenAI Research News RSS feed.

    Args:
        full_reset: If True, fetch all articles. If False, merge with cache.
    """
    url = "https://openai.com/news/research/"

    try:
        cache = load_cache(FEED_NAME)
        cached_articles = deserialize_entries(cache.get("entries", []))

        if full_reset or not cached_articles:
            mode = "full reset" if full_reset else "no cache exists"
            logger.info(f"Running full fetch ({mode})")
        else:
            logger.info("Running incremental update")

        html_content = fetch_news_content_selenium(url)
        new_articles = parse_openai_news_html(html_content)

        if not new_articles and not cached_articles:
            logger.warning("No articles were parsed. Check your selectors.")
            return

        # Merge with cache or use fresh articles
        if cached_articles and not full_reset:
            articles = merge_entries(new_articles, cached_articles)
        else:
            articles = new_articles

        # Save to cache
        save_cache(FEED_NAME, articles)

        feed = generate_rss_feed(articles)
        save_rss_feed(feed, FEED_NAME)
        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate OpenAI Research News RSS feed"
    )
    parser.add_argument(
        "--full", action="store_true", help="Force full reset (fetch all articles)"
    )
    args = parser.parse_args()
    main(full_reset=args.full)
