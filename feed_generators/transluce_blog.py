"""Generate an RSS feed for Transluce's research listing.

https://transluce.org/research

Static Next.js page: each research item is an ``<a>`` (relative href) wrapping
an ``<h3>`` title, a category ``<p>``, a description ``<p>``, and a date ``<p>``
formatted like "16 April 2025" (%d %B %Y).
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

BASE_URL = "https://transluce.org"
FEED_NAME = "transluce"
BLOG_URL = f"{BASE_URL}/research"
FEED_TITLE = "Transluce - Research"
FEED_DESCRIPTION = "Research updates from Transluce"
AUTHOR = "Transluce"

# Date lines look like "16 April 2025".
_DATE_RE = re.compile(r"^\d{1,2}\s+[A-Za-z]+\s+\d{4}$")

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

    for anchor in soup.find_all("a", href=True):
        heading = anchor.find("h3")
        if not heading:
            continue
        href = anchor["href"]
        # Only internal article links (relative or transluce.org absolute).
        if href.startswith("http") and BASE_URL not in href:
            continue
        link = href if href.startswith("http") else BASE_URL + "/" + href.lstrip("/")
        if link in seen:
            continue

        title = heading.get_text(strip=True)
        if not title:
            continue

        paragraphs = anchor.find_all("p")
        date = None
        description = None
        for p in paragraphs:
            text = p.get_text(" ", strip=True)
            if _DATE_RE.match(text):
                date = parse_date(text)
            elif p.get("class") and "mb-4" in p.get("class"):
                description = text

        if description is None:
            # Fall back to the longest non-date paragraph as the summary.
            candidates = [
                p.get_text(" ", strip=True) for p in paragraphs if not _DATE_RE.match(p.get_text(" ", strip=True))
            ]
            description = max(candidates, key=len) if candidates else title

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
