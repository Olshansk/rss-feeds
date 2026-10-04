"""Combine every OpenAI News category and the separate developer blog."""

from feed_history import merge_feed_history, require_posts
from native_rss import generate_feed, parse_rss
from openai_developer_blog import BLOG_URL as DEVELOPER_URL
from openai_developer_blog import parse_blog_html
from static_pages import fetch_page
from utils import save_rss_feed

FEED_NAME = "openai_main"
BLOG_URL = "https://openai.com/news/"
RSS_URL = "https://openai.com/news/rss.xml"


def parse_sources(news_xml, developer_html):
    """Include all news categories and require a nonempty developer extraction."""
    news = parse_rss(news_xml)
    developers = require_posts(parse_blog_html(developer_html))
    for post in developers:
        post["categories"] = list(dict.fromkeys(["Developer", post["category"]]))
    return news + developers


def main():
    """Fetch both live sources and publish one complete subscription.

    How:
    1. Fetch and parse every news category plus the separate developer blog.
    2. Preserve historical items and subscriber identities across refreshes.
    3. Sort, deduplicate, validate, and atomically publish the combined feed.
    """
    posts = parse_sources(fetch_page(RSS_URL), fetch_page(DEVELOPER_URL))
    posts = merge_feed_history(posts, FEED_NAME)
    feed = generate_feed(
        posts,
        title="OpenAI — All News and Developer Blog",
        description="All OpenAI News categories, including product, research, engineering, safety, and developer posts.",
        blog_url=BLOG_URL,
        feed_name=FEED_NAME,
    )
    save_rss_feed(feed, FEED_NAME)


if __name__ == "__main__":
    main()
