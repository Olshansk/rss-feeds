"""Generate RSS feed for AI at Meta Blog (https://ai.meta.com/blog/).

React SPA with a "Load more" button. The page renders three distinct card
layouts (hero, Latest News grid, "More from AI at Meta" grid) that this
parser handles independently.

Closes upstream issue #61.
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

FEED_NAME = "meta_ai"
BLOG_URL = "https://ai.meta.com/blog/"

DATE_PATTERN = re.compile(
    r"(January|February|March|April|May|June|July|August"
    r"|September|October|November|December)\s+\d{1,2},\s+\d{4}"
)

# Meta AI's layout uses hashed CSS-module class names (_amto, _amcy, _amda, _amde,
# _amsu, ...). These rotate when Meta rebuilds the site, so selector breakage is
# the failure mode to expect. Mitigations: the parser walks three layouts
# independently and falls back from class-based selectors to aria-label and
# finally to separator-joined text. When a layout change lands, capture the new
# page with ``curl`` or Selenium and update the class constants below.
CATEGORIES = {
    "featured",
    "ml applications",
    "open source",
    "research",
    "computer vision",
    "hardware",
    "natural language processing",
    "generative ai",
}


def fetch_blog_content(url: str = BLOG_URL, max_clicks: int = 20) -> str:
    """Fetch the blog HTML after clicking "Load more" up to max_clicks times."""
    driver = None
    try:
        logger.info(f"Fetching content from {url} (max_clicks={max_clicks})")
        driver = setup_selenium_driver()
        driver.get(url)
        time.sleep(5)

        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/blog/"]')))
            logger.info("Blog articles loaded")
        except Exception:
            logger.warning("Could not confirm articles loaded, proceeding anyway")

        clicks = 0
        while clicks < max_clicks:
            load_more = None
            with contextlib.suppress(Exception):
                candidate = driver.find_element(By.CSS_SELECTOR, "button._amto")
                if candidate.is_displayed():
                    load_more = candidate
            if not load_more:
                with contextlib.suppress(Exception):
                    load_more = driver.find_element(By.XPATH, "//button[contains(text(), 'Load more')]")

            if load_more and load_more.is_displayed():
                logger.info(f"Clicking 'Load more' button (click {clicks + 1})")
                driver.execute_script("arguments[0].click();", load_more)
                clicks += 1
                time.sleep(2)
            else:
                logger.info(f"No more 'Load more' button after {clicks} clicks")
                break

        return driver.page_source
    finally:
        if driver:
            driver.quit()


def parse_date(date_text: str) -> datetime | None:
    """Parse 'Month DD, YYYY' into a tz-aware datetime."""
    date_text = date_text.strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_text, fmt).replace(tzinfo=pytz.UTC)
        except ValueError:
            continue
    return None


def _extract_date_from_elements(elements, article_href: str) -> tuple[datetime | None, str]:
    """Walk elements looking for a date match (long or short month). Returns (date, matched_text)."""
    for elem in elements:
        text = elem.get_text(strip=True)
        date_match = DATE_PATTERN.search(text)
        if date_match:
            parsed = parse_date(date_match.group())
            if parsed:
                return parsed, text
    for elem in elements:
        text = elem.get_text(strip=True)
        parsed = parse_date(text)
        if parsed:
            return parsed, text
    return None, ""


def _append_article(articles, seen, href, title, date, category, description):
    """Append an article to the list if href is unseen. Mutates both collections."""
    if href in seen or href in ("/blog/", "/blog"):
        return
    seen.add(href)
    if not date:
        date = stable_fallback_date(href)
    articles.append(
        {
            "title": title,
            "link": href,
            "date": date,
            "category": category,
            "description": description,
        }
    )


def _absolute_meta_url(href: str) -> str:
    return f"https://ai.meta.com{href}" if href.startswith("/") else href


def extract_articles(soup: BeautifulSoup) -> list[dict]:
    """Extract articles from the three card layouts on the Meta AI blog."""
    articles: list[dict] = []
    seen: set[str] = set()

    # Hero card (featured, div._amcy)
    hero = soup.select_one("div._amcy")
    if hero:
        link = hero.find("a", href=True)
        if link:
            href = _absolute_meta_url(link.get("href", ""))
            title_elem = hero.find("div", class_="_amd1")
            title = title_elem.get_text(strip=True) if title_elem else ""
            if not title:
                aria = link.get("aria-label", "")
                title = aria.removeprefix("Read ").strip() if aria.startswith("Read ") else ""
            if title:
                # The hero's date container class has rotated (was _amdj, then
                # _amun, ...), so scan every <div> inside the hero with the
                # DATE_PATTERN regex instead of pinning to a single class.
                # Without this we fall through to stable_fallback_date(), which
                # (relying on Python's randomized hash()) buries the newest
                # post under a bogus pubDate.
                date, _ = _extract_date_from_elements(hero.find_all("div"), href)

                # Category: try the legacy explicit class, then the current
                # "FEATURED"-style badge, then default. Empty strings are
                # treated as missing so we don't emit empty <category/>.
                category = "AI"
                for cls in ("_amug", "_amd5"):
                    cat_elem = hero.find("div", class_=cls)
                    cat_text = cat_elem.get_text(strip=True) if cat_elem else ""
                    if cat_text:
                        category = cat_text.title() if cat_text.isupper() else cat_text
                        break
                _append_article(articles, seen, href, title, date, category, title)

    # Latest News grid (div._amda)
    for card in soup.select("div._amda"):
        link = card.find("a", href=True)
        if not link:
            continue
        href = _absolute_meta_url(link.get("href", ""))

        title_elem = card.find("div", class_="_amde")
        title = title_elem.get_text(strip=True) if title_elem else ""
        if not title:
            aria = link.get("aria-label", "")
            title = aria.removeprefix("Read ").strip() if aria.startswith("Read ") else ""
        if not title:
            continue

        amdj_elems = card.select("div._amdj")
        date, matched_date_text = _extract_date_from_elements(amdj_elems, href)

        category = "AI"
        for elem in amdj_elems:
            text = elem.get_text(strip=True)
            if text == matched_date_text:
                continue
            if text.lower() in CATEGORIES:
                category = text
                break

        description = title
        desc_elem = card.find("p", class_="text-secondary") or card.find("p", class_="_amt3")
        if desc_elem:
            description = desc_elem.get_text(strip=True)[:300]

        _append_article(articles, seen, href, title, date, category, description)

    # "More from AI at Meta" grid (div._amsu)
    for card in soup.select("div._amsu"):
        link = card.find("a", href=True)
        if not link:
            continue
        href = _absolute_meta_url(link.get("href", ""))

        title_elem = card.find("p", class_="_amt2")
        title = title_elem.get_text(strip=True) if title_elem else ""
        if not title:
            continue

        cat_elem = card.find("p", class_="_amt0")
        category = cat_elem.get_text(strip=True) if cat_elem else "AI"

        date_elem = card.find("p", class_="_amt4")
        date, _ = _extract_date_from_elements([date_elem] if date_elem else [], href)

        desc_elem = card.find("p", class_="_amt3")
        description = desc_elem.get_text(strip=True)[:300] if desc_elem else title

        _append_article(articles, seen, href, title, date, category, description)

    logger.info(f"Parsed {len(articles)} articles")
    return articles


def generate_rss_feed(articles: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("AI at Meta Blog")
    fg.description("Latest AI news and research from Meta")
    fg.language("en")
    fg.author({"name": "Meta AI"})
    fg.subtitle("AI research, open source, and applications from Meta")
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

    if full_reset or not cached_entries:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
        html = fetch_blog_content(max_clicks=20)
    else:
        logger.info("Running incremental update (3 clicks only)")
        html = fetch_blog_content(max_clicks=3)

    soup = BeautifulSoup(html, "html.parser")
    new_articles = extract_articles(soup)

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
    parser = argparse.ArgumentParser(description="Generate AI at Meta Blog RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (click Load more up to 20 times)")
    args = parser.parse_args()
    main(full_reset=args.full)
