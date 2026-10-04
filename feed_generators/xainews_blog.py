import argparse

from feedgen.feed import FeedGenerator

from dynamic_pages import fetch_rendered
from feed_history import load_feed_history, merge_feed_history
from html_cards import parse_dated_cards
from utils import (
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

FEED_NAME = "xainews"
BLOG_URL = "https://x.ai/news"


def fetch_news_content(url=BLOG_URL):
    """Load news links through the shared dynamic-page fetcher."""
    return fetch_rendered(url, "a[href*='/news/']:has(h3), a[href*='/news/']:has(h2)")


def parse_news_html(html_content):
    """Read semantic article cards using the common dated-card parser."""
    return [{**post, "category": "News"} for post in parse_dated_cards(html_content, 'a[href*="/news/"]', BLOG_URL)]


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
        fe.id(article.get("guid") or article["link"])

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
        cached_articles = merge_entries(deserialize_entries(cache.get("entries", [])), load_feed_history(FEED_NAME))

        if full_reset or not cached_articles:
            mode = "full reset" if full_reset else "no cache exists"
            logger.info(f"Running full fetch ({mode})")
        else:
            logger.info("Running incremental update")

        # Fetch news content using Selenium (xAI is JS-rendered)
        html_content = fetch_news_content()

        # Parse articles from HTML
        new_articles = parse_news_html(html_content)

        if not new_articles:
            logger.warning("No articles found!")
            return False

        # Merge with cache or use fresh articles
        if cached_articles and not full_reset:
            articles = merge_entries(new_articles, cached_articles)
        else:
            articles = new_articles

        articles = merge_feed_history(new_articles, FEED_NAME)

        # Generate and save RSS feed
        feed = generate_rss_feed(articles)
        save_rss_feed(feed, FEED_NAME)
        save_cache(FEED_NAME, articles)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e!s}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate xAI News RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch all articles)")
    args = parser.parse_args()
    raise SystemExit(0 if main(full_reset=args.full) else 1)
