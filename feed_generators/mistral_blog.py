"""Generate RSS feed for Mistral AI News (https://mistral.ai/news).

Selenium-driven numbered pagination. Unlike "Load more" SPAs that append content,
Mistral replaces the article grid on each page navigation, so we parse after
each click before advancing to the next page.
"""

import argparse
import time
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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

FEED_NAME = "mistral"
BLOG_URL = "https://mistral.ai/news"
MAX_PAGES_FULL = 6
MAX_PAGES_INCREMENTAL = 1


def parse_page_articles(html: str) -> list[dict]:
    """Extract articles from a single page. Returns a deduped list per page.

    Page 1 has a hero card with <h1>; grid cards use <h2>. Cards live inside
    <a href="/news/..."> wrappers containing an <article> element.
    """
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen_links = set()

    for card in soup.select('a[href^="/news/"]'):
        href = card.get("href", "")
        if not href or href.rstrip("/") == "/news":
            continue

        link = f"https://mistral.ai{href}"
        if link in seen_links:
            continue

        article_elem = card.find("article")
        if not article_elem:
            continue

        seen_links.add(link)

        title_elem = article_elem.find("h1") or article_elem.find("h2")
        if not title_elem:
            continue
        title = title_elem.get_text(strip=True)
        if len(title) < 3:
            continue

        category = "News"
        for span in article_elem.find_all("span"):
            classes = " ".join(span.get("class", []))
            if "rounded-full" in classes and "border" in classes:
                cat_text = span.get_text(strip=True)
                if cat_text:
                    category = cat_text
                break

        description = title
        for p in article_elem.find_all("p"):
            classes = " ".join(p.get("class", []))
            if "opacity" in classes or "text-black/50" in classes:
                desc_text = p.get_text(strip=True)
                if desc_text:
                    description = desc_text[:300]
                break

        date = None
        for div in article_elem.find_all("div"):
            if "text-sm" not in " ".join(div.get("class", [])):
                continue
            date_text = div.get_text(strip=True)
            for fmt in ("%b %d, %Y", "%B %d, %Y"):
                try:
                    date = datetime.strptime(date_text, fmt).replace(tzinfo=pytz.UTC)
                    break
                except ValueError:
                    continue
            if date:
                break
        if not date:
            logger.warning(f"Could not parse date for article: {title}")
            date = stable_fallback_date(link)

        articles.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "category": category,
                "description": description,
            }
        )

    logger.info(f"Parsed {len(articles)} articles from page")
    return articles


def fetch_all_articles(max_pages: int = MAX_PAGES_FULL) -> list[dict]:
    """Fetch articles across numbered pages using Selenium."""
    driver = None
    all_articles: list[dict] = []
    seen_links: set[str] = set()

    try:
        logger.info(f"Fetching articles from {BLOG_URL} (max_pages={max_pages})")
        driver = setup_selenium_driver()
        driver.get(BLOG_URL)
        time.sleep(5)

        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href^="/news/"]')))
        except Exception:
            logger.warning("Could not confirm articles loaded, proceeding anyway")

        for page_num in range(1, max_pages + 1):
            logger.info(f"Extracting articles from page {page_num}")
            page_articles = parse_page_articles(driver.page_source)
            new_count = 0
            for article in page_articles:
                if article["link"] not in seen_links:
                    all_articles.append(article)
                    seen_links.add(article["link"])
                    new_count += 1
            logger.info(f"Page {page_num}: {new_count} new articles (total: {len(all_articles)})")

            if page_num >= max_pages:
                break

            # The next-page arrow is the last button in the pagination row.
            next_btn = None
            pagination_buttons = driver.find_elements(By.CSS_SELECTOR, "button.size-8, button[class*='size-8']")
            if pagination_buttons:
                candidate = pagination_buttons[-1]
                try:
                    candidate.find_element(By.TAG_NAME, "svg")
                    next_btn = candidate
                except Exception:
                    next_btn = None

            if not next_btn or not next_btn.is_displayed():
                logger.info(f"No next button found after page {page_num}")
                break

            logger.info(f"Clicking next button to page {page_num + 1}")
            driver.execute_script("arguments[0].click();", next_btn)
            time.sleep(3)
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href^="/news/"]')))
            except Exception:
                logger.warning("Timeout waiting for next page content")

        logger.info(f"Total articles fetched: {len(all_articles)}")
        return all_articles
    finally:
        if driver:
            driver.quit()


def generate_rss_feed(articles: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("Mistral AI News")
    fg.description("Latest news and updates from Mistral AI")
    fg.language("en")
    fg.author({"name": "Mistral AI"})
    fg.subtitle("News, research, and product updates from Mistral AI")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for article in sort_posts_for_feed(articles, date_field="date"):
        fe = fg.add_entry()
        fe.title(article["title"])
        fe.description(article["description"])
        fe.link(href=article["link"])
        fe.id(article["link"])
        fe.category(term=article["category"])
        if article.get("date"):
            fe.published(article["date"])

    logger.info(f"Generated RSS feed with {len(articles)} entries")
    return fg


def main(full_reset: bool = False) -> bool:
    cache = load_cache(FEED_NAME)
    cached_entries = deserialize_entries(cache.get("entries", []))

    pages = MAX_PAGES_FULL if (full_reset or not cached_entries) else MAX_PAGES_INCREMENTAL
    mode = "full reset" if full_reset else "no cache exists" if not cached_entries else "incremental update"
    logger.info(f"Running {mode} (max_pages={pages})")
    new_articles = fetch_all_articles(max_pages=pages)

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
    parser = argparse.ArgumentParser(description="Generate Mistral AI News RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch up to 6 pages)")
    args = parser.parse_args()
    main(full_reset=args.full)
