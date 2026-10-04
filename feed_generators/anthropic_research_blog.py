from feedgen.feed import FeedGenerator

from dynamic_pages import fetch_rendered
from feed_history import merge_feed_history
from html_cards import parse_dated_cards
from utils import (
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "anthropic_research"
BLOG_URL = "https://www.anthropic.com/research"


def fetch_research_content_selenium(url=BLOG_URL, max_clicks=2):
    """Expand dated research rows with the shared browser fetcher."""
    return fetch_rendered(url, "a:has(time)", button_xpath="//a[normalize-space()='See more']", max_clicks=max_clicks)


def parse_research_html(html_content):
    """Select real dated articles, excluding undated research-team navigation."""
    return [
        {**post, "category": "Research"}
        for post in parse_dated_cards(
            html_content, "a[href]:has(time)", BLOG_URL, title_selector='span[class*="__title"], h1, h2, h3, h4'
        )
    ]


def generate_rss_feed(articles):
    """Generate RSS feed from research articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic Research")
        fg.description("Latest research papers and updates from Anthropic")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Research Team"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Latest research from Anthropic")
        setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

        # Sort articles for correct feed order (newest first in output)
        # Articles without dates will appear at the end
        articles_sorted = sort_posts_for_feed(articles, date_field="date")

        # Add entries
        for article in articles_sorted:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])

            # Only set published date if we have a valid date
            if article["date"]:
                fe.published(article["date"])

            fe.category(term=article["category"])
            fe.id(article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {e!s}")
        raise


def main(full_reset=False):
    """Main function to generate RSS feed from Anthropic's research page.

    Args:
        full_reset: If True, fetch all articles. If False, merge with cache.
    """
    try:
        html_content = fetch_research_content_selenium(max_clicks=40 if full_reset else 2)
        articles = merge_feed_history(parse_research_html(html_content), FEED_NAME)
        articles = [post for post in articles if "/research/team/" not in post["link"]]

        # Generate RSS feed
        feed = generate_rss_feed(articles)

        # Save feed to file
        save_rss_feed(feed, FEED_NAME)
        save_cache(FEED_NAME, articles)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e!s}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Anthropic Research RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (fetch all articles)")
    args = parser.parse_args()
    raise SystemExit(0 if main(full_reset=args.full) else 1)
