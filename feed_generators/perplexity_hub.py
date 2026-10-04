"""Generate RSS feed for the Perplexity Hub (https://www.perplexity.ai/hub).

The current blog uses Sanity cards with See more pagination. Selenium fetches
the page with an English locale and expands the requested article history.
"""

import argparse
import contextlib
import re
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from dynamic_pages import fetch_rendered
from feed_history import load_feed_history, merge_feed_history
from utils import (
    DEFAULT_USER_AGENT,
    deserialize_entries,
    load_cache,
    merge_entries,
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "perplexity_hub"
BLOG_URL = "https://www.perplexity.ai/hub/blog"

# A <p> is treated as a date (and skipped for category) if it contains an
# English or German month name. Year-only strings are not enough, since
# categories like "Q&A 2024" contain a year without being dates.
DATE_PATTERN = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
    r"|Januar|Februar|März|April|Mai|Juni|Juli|August"
    r"|September|Oktober|November|Dezember)\b"
)
LOCALE_PREFIX = re.compile(r"(perplexity\.ai)/[a-z]{2}(?:-[A-Za-z]{2})?/hub/")


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


def fetch_hub_content(url: str = BLOG_URL, max_clicks: int = 2) -> str:
    """Fetch the current blog and expand recent or full history.

    How:
    1. Open the blog with an English locale and wait for article links.
    2. Click See more, waiting for the article count to grow each time.
    3. Return rendered HTML and always close Chrome.
    """
    return fetch_rendered(
        url,
        'a[href*="/hub/blog/"]:not([href*="/category/"])',
        button_xpath="//button[normalize-space()='See more']",
        max_clicks=max_clicks,
        configure=_force_english_locale,
    )


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
    title = card.select_one("span.text-pretty")
    return title.get_text(" ", strip=True) if title else None


def _extract_date(card) -> datetime | None:
    """Read machine-readable dates or the visible date on current Sanity cards."""
    time_elem = card.select_one("time[datetime]")
    if time_elem:
        with contextlib.suppress(ValueError):
            date = datetime.fromisoformat(time_elem["datetime"].replace("Z", "+00:00"))
            return date if date.tzinfo else date.replace(tzinfo=pytz.UTC)
    match = re.search(r"[A-Z][a-z]{2} \d{1,2}, \d{4}", card.get_text(" ", strip=True))
    return datetime.strptime(match.group(), "%b %d, %Y").replace(tzinfo=pytz.UTC) if match else None


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

    Read heading or span titles and machine-readable or visible publication dates.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []
    seen_links = set()

    all_links = soup.select('a[href*="/hub/blog/"]')
    logger.info(f"Found {len(all_links)} potential blog article links")

    for card in all_links:
        href = card.get("href", "")
        if not href or "/category/" in href:
            continue
        link = _canonicalize_link(href)
        if link in seen_links:
            continue
        seen_links.add(link)

        title = _extract_title(card)
        if not title:
            logger.debug(f"Could not extract title for link: {link}")
            continue

        date = _extract_date(card)
        if date is None:
            raise ValueError(f"Missing Perplexity publication date: {link}")
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
        fe.id(article.get("guid") or article["link"])
        fe.category(term=article["category"])
        fe.published(article["date"])

    logger.info(f"Generated RSS feed with {len(articles)} entries")
    return fg


def main(full_reset: bool = False) -> bool:
    cache = load_cache(FEED_NAME)
    cached_entries = merge_entries(deserialize_entries(cache.get("entries", [])), load_feed_history(FEED_NAME))

    if full_reset or not cached_entries:
        mode = "full reset" if full_reset else "no cache exists"
        logger.info(f"Running full fetch ({mode})")
    else:
        logger.info("Running incremental update")

    html = fetch_hub_content(max_clicks=30 if full_reset else 2)
    new_articles = parse_hub_html(html)

    if not new_articles:
        raise ValueError("No fresh Perplexity articles found; refusing to republish cached content")

    if cached_entries and not full_reset:
        articles = merge_entries(new_articles, cached_entries)
    else:
        articles = sort_posts_for_feed(new_articles, date_field="date")

    if not articles:
        logger.warning("No articles found. Check the HTML structure.")
        return False

    articles = merge_feed_history(articles, FEED_NAME, match_titles=True)
    feed = generate_rss_feed(articles)
    save_rss_feed(feed, FEED_NAME)
    save_cache(FEED_NAME, articles)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Perplexity Hub RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (ignore cache)")
    args = parser.parse_args()
    raise SystemExit(0 if main(full_reset=args.full) else 1)
