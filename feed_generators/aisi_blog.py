"""Generate an RSS feed for the AI Security Institute (AISI) blog.

https://www.aisi.gov.uk/blog

Static Webflow (Finsweet CMS) page: each post is a ``div.card`` with an
``h3[fs-list-field="title"]`` title inside an ``a`` to ``/blog/<slug>``, a
``p[fs-list-field="date"]`` date such as "Jun 18, 2026" (%b %d, %Y), a
``p[fs-list-field="category"]`` tag, and a ``p[fs-list-field="description"]``.
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
)

logger = setup_logging()

BASE_URL = "https://www.aisi.gov.uk"
FEED_NAME = "aisi"
BLOG_URL = f"{BASE_URL}/blog"
FEED_TITLE = "AISI Blog"
FEED_DESCRIPTION = "Blog posts from the AI Security Institute"
AUTHOR = "AI Security Institute"

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

    for card in soup.select("div.card"):
        heading = card.find(attrs={"fs-list-field": "title"})
        anchor = card.find("a", href=lambda h: h and h.startswith("/blog/"))
        if not heading or not anchor:
            continue

        link = BASE_URL + anchor["href"]
        if link in seen:
            continue

        title = heading.get_text(strip=True)
        if not title:
            continue

        date_el = card.find(attrs={"fs-list-field": "date"})
        date = parse_date(date_el.get_text(strip=True)) if date_el else None
        if date is None:
            logger.warning(f"No parseable date for {link}")

        desc_el = card.find(attrs={"fs-list-field": "description"})
        description = desc_el.get_text(" ", strip=True) if desc_el else title

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
