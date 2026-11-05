"""Generate an RSS feed for Transluce's research listing.

https://transluce.org/research

Static Next.js article links include h3 titles, descriptions, and publication dates.
"""

import argparse
import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from feed_history import load_feed_history, merge_feed_history
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
LISTING_URLS = (BLOG_URL, f"{BASE_URL}/docent/blog", f"{BASE_URL}/governance")
FEED_TITLE = "Transluce - Research"
FEED_DESCRIPTION = "Research updates from Transluce"
AUTHOR = "Transluce"

# Date lines look like "16 April 2025".
_DATE_RE = re.compile(r"^(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+ \d{1,2}, \d{4})$")

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
    """Read current article cards and legacy linked cards without hiding malformed entries.

    How:
    1. Find semantic article containers and legacy links containing headings.
    2. Keep internal article URLs and read dates separately from category metadata.
    3. Reject incomplete cards and deduplicate repeated links.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []
    seen = set()

    cards = soup.select("article") + [a for a in soup.select("a[href]") if a.find("h3")]
    for card in cards:
        heading = card.find("h3")
        anchor = card if card.name == "a" else (heading.find("a", href=True) if heading else None)
        if not heading or not anchor:
            raise ValueError("Transluce article is missing its title or link")
        href = anchor["href"]
        # Only internal article links (relative or transluce.org absolute).
        link = urljoin(BASE_URL, href)
        if urlsplit(link).hostname != "transluce.org":
            continue
        if not href.strip() or urlsplit(link).scheme != "https":
            raise ValueError("Transluce article has an invalid link")
        if link in seen:
            continue

        title = heading.get_text(strip=True)
        if not title:
            raise ValueError("Transluce article has an empty title")

        paragraphs = card.find_all("p")
        date_text = next((text for text in card.stripped_strings if _DATE_RE.fullmatch(text)), None)
        date = parse_date(date_text)
        if date is None:
            raise ValueError(f"Transluce article has no valid date: {link}")
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
                p.get_text(" ", strip=True)
                for p in paragraphs
                if not any(_DATE_RE.fullmatch(text) for text in p.stripped_strings)
            ]
            description = max(candidates, key=len) if candidates else None

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
        fe.id(post.get("guid") or post["link"])

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
            articles = parse(html_content)
        else:
            articles = []
            for url in LISTING_URLS:
                posts = parse(fetch_page(url))
                if not posts:
                    raise ValueError(f"No articles found in required listing: {url}")
                articles.extend(posts)

        if not articles:
            logger.warning("No articles found - skipping feed update to avoid overwriting with empty feed")
            return False

        # New research cards omit summaries; retain published summaries for those live entries.
        history = {post["link"]: post for post in load_feed_history(FEED_NAME)}
        for post in articles:
            if not post["description"]:
                post["description"] = history.get(post["link"], {}).get("description") or post["title"]
        articles = merge_feed_history(articles, FEED_NAME, match_titles=True)
        fg = generate_rss_feed(articles)
        save_rss_feed(fg, FEED_NAME)
        logger.info(f"Generated {FEED_NAME} feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate {FEED_NAME} feed: {e!s}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
