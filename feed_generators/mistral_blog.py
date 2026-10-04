"""Refresh the existing Mistral endpoint from its official RSS feed."""

import argparse

from feedgen.feed import FeedGenerator

from feed_history import merge_feed_history
from native_rss import parse_rss
from utils import (
    fetch_page,
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()
FEED_NAME = "mistral"
BLOG_URL = "https://mistral.ai/news"
RSS_URL = "https://mistral.ai/news/rss"


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
        fe.id(article.get("guid") or article["link"])
        fe.category(term=article["category"])
        if article.get("date"):
            fe.published(article["date"])

    logger.info(f"Generated RSS feed with {len(articles)} entries")
    return fg


def main() -> None:
    """Refresh from native RSS while retaining articles outside its current window.

    How:
    1. Fetch and validate the official feed.
    2. Merge it with the saved subscriber feed by URL.
    3. Persist RSS and JSON cache.
    """
    posts = merge_feed_history(parse_rss(fetch_page(RSS_URL)), FEED_NAME, match_titles=True)
    save_rss_feed(generate_rss_feed(posts), FEED_NAME)
    save_cache(FEED_NAME, posts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Mistral AI News RSS feed")
    parser.add_argument("--full", action="store_true", help="Accepted for compatibility; always fetch native RSS")
    parser.parse_args()
    main()
