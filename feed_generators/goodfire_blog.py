"""Generate an RSS feed for Goodfire's research listing.

https://www.goodfire.ai/research

Static Webflow (Finsweet CMS) page: each item is a ``div.blog-c-item`` with an
``h2``/``h3`` title, an ``a`` to ``/research/<slug>``, and a visible date such
as "July 7, 2026" (%B %d, %Y) held in an undistinguished ``div``, so the date is
found by scanning the card text.
"""

import argparse
import re
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
)

logger = setup_logging()

BASE_URL = "https://www.goodfire.ai"
FEED_NAME = "goodfire"
BLOG_URL = f"{BASE_URL}/research"
FEED_TITLE = "Goodfire - Research"
FEED_DESCRIPTION = "Research updates from Goodfire"
AUTHOR = "Goodfire"

# Dates render as "July 7, 2026".
_DATE_RE = re.compile(r"\b[A-Z][a-z]+ \d{1,2}, \d{4}\b")

DATE_FORMATS = [
    "%B %d, %Y",  # January 15, 2024
    "%b %d, %Y",  # Jan 15, 2024
    "%d %B %Y",  # 15 January 2024
    "%d %b %Y",  # 15 Jan 2024
    "%Y-%m-%d",  # 2024-01-15
    "%B %Y",  # January 2024
]


def parse_date(date_text):
    """Parse a date string into a UTC datetime, or ``None`` if unparseable."""
    if not date_text:
        return None
    text = date_text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=pytz.UTC)
        except ValueError:
            continue
    logger.warning(f"Could not parse date: {date_text!r}")
    return None


def parse(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []
    seen = set()

    for card in soup.select("div.blog-c-item"):
        anchor = card.find("a", href=lambda h: h and h.startswith("/research/"))
        heading = card.find(["h2", "h3"])
        if not anchor or not heading:
            continue

        link = BASE_URL + anchor["href"]
        if link in seen:
            continue

        title = heading.get_text(strip=True)
        if not title:
            continue

        text = card.get_text(" ", strip=True)
        match = _DATE_RE.search(text)
        date = parse_date(match.group(0)) if match else None
        if date is None:
            logger.warning(f"No parseable date for {link}")

        # Category tag is the card's summary here; description block is absent.
        category = card.find(attrs={"fs-list-field": "category"})
        description = category.get_text(strip=True) if category else title

        seen.add(link)
        articles.append({"title": title, "link": link, "description": description, "date": date})

    return articles


def generate_rss_feed(articles):
    fg = FeedGenerator()
    fg.title(FEED_TITLE)
    fg.description(FEED_DESCRIPTION)
    fg.language("en")
    fg.author({"name": AUTHOR})
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in sort_posts_for_feed(articles):
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post.get("description") or post["title"])
        fe.link(href=post["link"])
        fe.published(post["date"])
        fe.id(post["link"])

    return fg


def main():
    parser = argparse.ArgumentParser(description=f"Generate the {FEED_TITLE} RSS feed")
    parser.add_argument("html_file", nargs="?", help="Optional local HTML file to parse instead of fetching")
    args = parser.parse_args()

    try:
        if args.html_file:
            logger.info(f"Reading local HTML file: {args.html_file}")
            with open(args.html_file, encoding="utf-8") as f:
                html_content = f.read()
        else:
            html_content = fetch_page(BLOG_URL)

        articles = parse(html_content)

        if not articles:
            logger.warning("No articles found - skipping feed update to avoid overwriting with empty feed")
            return False

        fg = generate_rss_feed(articles)
        save_rss_feed(fg, FEED_NAME)
        logger.info(f"Generated {FEED_NAME} feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate {FEED_NAME} feed: {e!s}")
        return False


if __name__ == "__main__":
    main()
