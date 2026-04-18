"""Generate RSS feed for the Perplexity Hub (https://www.perplexity.ai/hub).

The hub is a Framer-built SPA that renders client-side. We use Selenium plus
a CDP command to force an Accept-Language: en-US header, since Perplexity
geo-redirects based on the request header (not URL or cookies). Without it
the scraper would get localized content and localized URLs.
"""

import argparse
import contextlib
import re
import time
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils import (
    DEFAULT_USER_AGENT,
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

FEED_NAME = "perplexity_hub"
BLOG_URL = "https://www.perplexity.ai/hub"

# A <p> is treated as a date (and skipped for category) if it contains an
# English or German month name. Year-only strings are not enough, since
# categories like "Q&A 2024" contain a year without being dates.
DATE_PATTERN = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    r"|Januar|Februar|März|April|Mai|Juni|Juli|August"
    r"|September|Oktober|November|Dezember)\b"
)
LOCALE_PREFIX = re.compile(r"(perplexity\.ai)/[a-z]{2}/hub/")


def _force_english_locale(driver) -> None:
    """Override the Accept-Language header via CDP so Perplexity serves en-US content."""
    driver.execute_cdp_cmd("Network.enable", {})
    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {
            "userAgent": DEFAULT_USER_AGENT,
            "acceptLanguage": "en-US,en;q=0.9",
        },
    )


def fetch_hub_content(url: str = BLOG_URL) -> str:
    """Fetch the fully rendered HTML of the Perplexity Hub via Selenium."""
    driver = None
    try:
        logger.info(f"Fetching content from {url}")
        driver = setup_selenium_driver()
        _force_english_locale(driver)
        driver.get(url)
        time.sleep(5)

        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/hub/blog/"]')))
            logger.info("Blog articles loaded")
        except Exception:
            logger.warning("Could not confirm articles loaded, proceeding anyway")

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        return driver.page_source
    finally:
        if driver:
            driver.quit()


def _canonicalize_link(href: str) -> str:
    """Build a full URL and strip any locale prefix (/de/hub/ -> /hub/)."""
    if href.startswith("./"):
        link = f"https://www.perplexity.ai/{href[2:]}"
    elif href.startswith("/"):
        link = f"https://www.perplexity.ai{href}"
    elif href.startswith("http"):
        link = href
    else:
        link = f"https://www.perplexity.ai/{href}"
    return LOCALE_PREFIX.sub(r"\1/hub/", link)


def _extract_title(card) -> str | None:
    for tag in ("h4", "h6", "h3", "h2", "h5"):
        elem = card.select_one(tag)
        if elem and elem.text.strip():
            return elem.text.strip()
    text = card.get_text(strip=True)
    return text[:150] if text and len(text) > 5 else None


def _extract_date(card) -> datetime | None:
    time_elem = card.select_one("time")
    if not time_elem:
        return None
    datetime_attr = time_elem.get("datetime")
    if not datetime_attr:
        return None
    with contextlib.suppress(ValueError):
        date = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
        if date.tzinfo is None:
            date = date.replace(tzinfo=pytz.UTC)
        return date
    return None


def _extract_category(card) -> str:
    """Category lives in <p> tags; skip the ones that look like dates."""
    for p in card.select("p"):
        text = p.text.strip()
        if len(text) < 3 or len(text) > 30:
            continue
        if DATE_PATTERN.search(text):
            continue
        return text
    return "Blog"


def validate_article(article: dict) -> bool:
    if not article.get("title") or len(article["title"]) < 5:
        logger.warning(f"Invalid title for article: {article.get('link', 'unknown')}")
        return False
    if not article.get("link") or not article["link"].startswith("http"):
        logger.warning(f"Invalid link for article: {article.get('title', 'unknown')}")
        return False
    if not article.get("date"):
        logger.warning(f"Missing date for article: {article.get('title', 'unknown')}")
        return False
    return True


def parse_hub_html(html_content: str) -> list[dict]:
    """Extract articles from the Perplexity Hub.

    Hero and article cards are both <a href="./hub/blog/..."> wrappers.
    Hero cards have <h4> titles and no <time>; article cards have <h6>,
    a <time datetime="...">, and <p> tags for category/date labels.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []
    seen_links = set()

    all_links = soup.select('a[href*="/hub/blog/"]')
    logger.info(f"Found {len(all_links)} potential blog article links")

    for card in all_links:
        href = card.get("href", "")
        if not href:
            continue
        link = _canonicalize_link(href)
        if link in seen_links:
            continue
        seen_links.add(link)

        title = _extract_title(card)
        if not title:
            logger.debug(f"Could not extract title for link: {link}")
            continue

        date = _extract_date(card) or stable_fallback_date(link)
        category = _extract_category(card)

        article = {
            "title": title,
            "link": link,
            "date": date,
            "category": category,
            "description": title,
        }
        if validate_article(article):
            articles.append(article)

    logger.info(f"Parsed {len(articles)} valid articles")
    return articles


def generate_rss_feed(articles: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("Perplexity Blog")
    fg.description("Latest news, updates, and research from Perplexity AI")
    fg.language("en")
    fg.author({"name": "Perplexity AI"})
    fg.logo("https://www.perplexity.ai/favicon.ico")
    fg.subtitle("Updates from Perplexity AI")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for article in sort_posts_for_feed(articles, date_field="date"):
        fe = fg.add_entry()
        fe.title(article["title"])
        fe.description(article["description"])
        fe.link(href=article["link"])
        fe.id(article["link"])
        fe.category(term=article["category"])
        fe.published(article["date"])

    logger.info(f"Generated RSS feed with {len(articles)} entries")
    return fg


def main(full_reset: bool = False) -> bool:
    cache = load_cache(FEED_NAME)
    cached_entries = deserialize_entries(cache.get("entries", []))

    if full_reset or not cached_entries:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
    else:
        logger.info("Running incremental update")

    html = fetch_hub_content()
    new_articles = parse_hub_html(html)

    if cached_entries and not full_reset:
        articles = merge_entries(new_articles, cached_entries)
    else:
        articles = sort_posts_for_feed(new_articles, date_field="date")

    if not articles:
        logger.warning("No articles found. Check the HTML structure.")
        return False

    save_cache(FEED_NAME, articles)
    feed = generate_rss_feed(articles)
    save_rss_feed(feed, FEED_NAME)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Perplexity Hub RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (ignore cache)")
    args = parser.parse_args()
    main(full_reset=args.full)
