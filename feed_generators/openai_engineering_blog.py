"""Mirror the existing OpenAI Engineering endpoint from official category metadata."""

from feed_history import merge_feed_history
from native_rss import generate_feed, parse_rss
from static_pages import fetch_page
from utils import save_rss_feed

FEED_NAME = "openai_engineering"
BLOG_URL = "https://openai.com/news/engineering/"
RSS_URL = "https://openai.com/news/rss.xml"


def parse_engineering_posts(content):
    """Select Engineering from all category tags and require valid dates."""
    return parse_rss(content, category="Engineering")


def generate_rss_feed(posts):
    """Build the existing endpoint using the shared native-feed writer."""
    return generate_feed(
        posts,
        title="OpenAI Engineering",
        description="Engineering posts from OpenAI",
        blog_url=BLOG_URL,
        feed_name=FEED_NAME,
    )


def main():
    """Fetch official content, retain subscriber history, and publish valid RSS.

    How:
    1. Fetch and strictly parse the official category entries.
    2. Merge persisted history without changing subscriber identities.
    3. Validate and atomically publish the existing endpoint.
    """
    posts = merge_feed_history(parse_engineering_posts(fetch_page(RSS_URL)), FEED_NAME)
    save_rss_feed(generate_rss_feed(posts), FEED_NAME)


if __name__ == "__main__":
    main()
