from datetime import datetime
from urllib.parse import urljoin

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from feed_history import merge_feed_history
from static_pages import fetch_paginated
from utils import (
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "windsurf_blog"  # keep _blog suffix for backwards compatibility (feed URL)
BLOG_URL = "https://devin.ai/blog"


def fetch_blog_posts():
    """Fetch Devin's paginated blog archive after the Windsurf migration.

    How:
    1. Fetch each server-rendered page with a bounded timeout.
    2. Follow its Show more posts link and stop at the end of the archive.
    3. Return all cards for parsing and deduplication.
    """

    def next_url(html, url):
        more = next(
            (
                a
                for a in BeautifulSoup(html, "html.parser").select('a[href^="/blog/page/"]')
                if a.get_text(" ", strip=True).lower().startswith(("next", "show more"))
            ),
            None,
        )
        return urljoin(url, more["href"]) if more else None

    return fetch_paginated(BLOG_URL, parse_blog_posts, next_url)


def parse_blog_posts(html):
    """Extract dated cards from Devin's server-rendered blog."""
    soup = BeautifulSoup(html, "html.parser")
    posts = {}
    for card in soup.select('a[href^="/blog/"]:has(time)'):
        heading = card.find(["h2", "h3"])
        time = card.find("time")
        if heading is None or not time.get("datetime"):
            raise ValueError("Devin blog card lacks a title or date")
        link = urljoin(BLOG_URL, card["href"])
        description = card.find("p")
        posts[link] = {
            "title": heading.get_text(" ", strip=True),
            "link": link,
            "date": datetime.fromisoformat(time["datetime"]).replace(tzinfo=pytz.UTC),
            "description": description.get_text(" ", strip=True) if description else heading.get_text(),
            "tags": [],
        }
    return list(posts.values())


def generate_rss_feed(blog_posts, feed_name=FEED_NAME):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Devin Blog (formerly Windsurf)")
        fg.description("Latest updates and announcements from Windsurf")
        setup_feed_links(fg, BLOG_URL, feed_name)
        fg.language("en")

        fg.author({"name": "Windsurf"})
        fg.subtitle("Read about the latest announcements from Windsurf")

        # Sort for correct feed order (newest first in output)
        blog_posts_sorted = sort_posts_for_feed(blog_posts, date_field="date")

        for post in blog_posts_sorted:
            fe = fg.add_entry()
            fe.title(post["title"])
            fe.description(post["description"])
            fe.link(href=post["link"])
            fe.published(post["date"])
            fe.id(post.get("guid") or post["link"])

            # Add tags as categories
            for tag in post.get("tags", []):
                fe.category(term=tag)

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {e!s}")
        raise


def main(feed_name=FEED_NAME):
    """Main function to generate RSS feed from Windsurf blog."""
    try:
        blog_posts = fetch_blog_posts()

        if not blog_posts:
            logger.warning("No blog posts found!")
            return False

        blog_posts = merge_feed_history(blog_posts, feed_name, match_titles=True)
        feed = generate_rss_feed(blog_posts, feed_name)
        save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(blog_posts)} posts")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e!s}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
