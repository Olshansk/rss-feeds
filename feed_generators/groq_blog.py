"""Generate RSS feed for the Groq Blog (https://groq.com/blog/).

Read server-rendered article links with headings and publication times.
"""

import argparse

from feedgen.feed import FeedGenerator

from feed_history import merge_feed_history, require_posts
from html_cards import parse_dated_cards
from utils import (
    fetch_page,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "groq"
BLOG_URL = "https://groq.com/blog/"


def parse_blog_html(html):
    """Extract semantic dated cards with the shared HTML parser."""
    return parse_dated_cards(html, "a[href^='/blog/']:has(h2):has(time)", BLOG_URL)


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
        fe.id(article.get("guid") or article["link"])
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

    articles = merge_feed_history(require_posts(articles), FEED_NAME, match_titles=True)
    feed = generate_rss_feed(articles)
    save_rss_feed(feed, FEED_NAME)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Groq Blog RSS feed")
    # --full is accepted for orchestrator compatibility even though the generator has no cache.
    parser.add_argument("--full", action="store_true", help="No-op (Groq has no cache)")
    parser.parse_args()
    raise SystemExit(0 if main() else 1)
