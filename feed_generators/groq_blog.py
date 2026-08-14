"""Generate RSS feed for the Groq Blog (https://groq.com/blog/).

Simple static HTML scraper. Cards are rendered server-side in <article class="card">
elements; no pagination or JavaScript. No cache needed.
"""

import argparse
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    fetch_page,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "groq"
BLOG_URL = "https://groq.com/blog/"


def parse_blog_html(html_content: str) -> list[dict]:
    """Extract articles from Groq's blog listing page."""
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []
    seen_links = set()

    for card in soup.select("article.card"):
        title_link = card.select_one("h2.card__title a")
        if not title_link:
            continue

        href = title_link.get("href", "")
        if not href or href.rstrip("/") == "/blog":
            continue

        link = f"https://groq.com{href}" if href.startswith("/") else href
        if link in seen_links:
            continue
        seen_links.add(link)

        title = title_link.get_text(strip=True)
        if not title:
            continue

        date = None
        time_elem = card.select_one("time.card__eyebrow")
        if time_elem:
            datetime_attr = time_elem.get("datetime")
            if datetime_attr:
                try:
                    date = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=pytz.UTC)
                except ValueError:
                    logger.warning(f"Could not parse datetime attribute: {datetime_attr}")

        if not date:
            date = stable_fallback_date(link)

        articles.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "description": title,
            }
        )

    logger.info(f"Parsed {len(articles)} articles")
    return articles


def generate_rss_feed(articles: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("Groq Blog")
    fg.description("Latest news and updates from Groq")
    fg.language("en")
    fg.author({"name": "Groq"})
    fg.subtitle("LPU inference, AI infrastructure, and developer updates")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for article in sort_posts_for_feed(articles, date_field="date"):
        fe = fg.add_entry()
        fe.title(article["title"])
        fe.description(article["description"])
        fe.link(href=article["link"])
        fe.id(article["link"])
        if article.get("date"):
            fe.published(article["date"])

    logger.info(f"Generated RSS feed with {len(articles)} entries")
    return fg


def main() -> bool:
    logger.info(f"Fetching {BLOG_URL}")
    html = fetch_page(BLOG_URL)
    articles = parse_blog_html(html)

    if not articles:
        logger.warning("No articles found. Check the HTML structure.")
        return False

    feed = generate_rss_feed(articles)
    save_rss_feed(feed, FEED_NAME)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Groq Blog RSS feed")
    # --full is accepted for orchestrator compatibility even though the generator has no cache.
    parser.add_argument("--full", action="store_true", help="No-op (Groq has no cache)")
    parser.parse_args()
    main()
