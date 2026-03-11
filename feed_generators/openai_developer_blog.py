import logging
from datetime import datetime
from pathlib import Path

import pytz
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import get_feeds_dir, setup_feed_links, sort_posts_for_feed

FEED_NAME = "openai_developer"
BLOG_URL = "https://developers.openai.com/blog"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_blog_content(url=BLOG_URL):
    """Fetch blog content from the given URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text


def parse_date(date_text):
    """Parse date text like 'Feb 26' or 'Dec 30', inferring the year.

    Posts are listed newest-first. Dates without a year are assumed to be the
    most recent occurrence that is not in the future.
    """
    today = datetime.now(pytz.UTC)
    for fmt in ("%b %d", "%B %d"):
        try:
            # Use a dummy year to avoid Python 3.14 deprecation warning
            parsed = datetime.strptime(date_text.strip() + " 2000", fmt + " %Y")
            # Try current year first; if that's in the future, use previous year
            candidate = parsed.replace(year=today.year, tzinfo=pytz.UTC)
            if candidate > today:
                candidate = candidate.replace(year=today.year - 1)
            return candidate
        except ValueError:
            continue

    # Try formats that already include a year
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_text.strip(), fmt).replace(tzinfo=pytz.UTC)
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_text}")
    return None


def parse_blog_html(html_content):
    """Parse the blog HTML content and extract post information."""
    soup = BeautifulSoup(html_content, "html.parser")
    posts = []
    seen_links = set()

    # Blog cards use class "resource-item" and link to /blog/<slug>
    cards = soup.select('a.resource-item[href*="/blog/"]')
    logger.info(f"Found {len(cards)} blog cards")

    for card in cards:
        href = card.get("href", "")
        if not href or "/topic/" in href:
            continue

        link = "https://developers.openai.com" + href if href.startswith("/") else href
        if link in seen_links:
            continue
        seen_links.add(link)

        # Title: inside div.line-clamp-2
        title_elem = card.select_one("div.line-clamp-2")
        if not title_elem:
            continue
        title = title_elem.get_text(strip=True)

        # Date: first div with class text-secondary (contains "Feb 26" etc.)
        date_elem = card.select_one("div.text-secondary")
        date = parse_date(date_elem.get_text(strip=True)) if date_elem else None

        # Description: p with class line-clamp-3
        desc_elem = card.select_one("p.line-clamp-3")
        description = desc_elem.get_text(strip=True) if desc_elem else title

        # Category: div with pt-2 text-sm text-secondary
        cat_elem = card.select_one("div.pt-2.text-sm.text-secondary")
        category = cat_elem.get_text(strip=True) if cat_elem else "Developer"

        posts.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "description": description,
                "category": category,
            }
        )

    logger.info(f"Successfully parsed {len(posts)} blog posts")
    return posts


def generate_rss_feed(posts):
    """Generate RSS feed from blog posts."""
    fg = FeedGenerator()
    fg.title("OpenAI Developer Blog")
    fg.description("Latest developer updates and guides from OpenAI")
    fg.language("en")
    fg.author({"name": "OpenAI"})
    fg.subtitle("Updates for developers building with OpenAI")

    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    sorted_posts = sort_posts_for_feed(posts, date_field="date")

    for post in sorted_posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post["link"])
        fe.category(term=post["category"])
        if post["date"]:
            fe.published(post["date"])

    logger.info("Successfully generated RSS feed")
    return fg


def save_rss_feed(feed_generator):
    """Save the RSS feed to a file in the feeds directory."""
    feeds_dir = get_feeds_dir()
    output_file = feeds_dir / f"feed_{FEED_NAME}.xml"
    feed_generator.rss_file(str(output_file), pretty=True)
    logger.info(f"Successfully saved RSS feed to {output_file}")
    return output_file


def main():
    """Main function to generate RSS feed from OpenAI Developer Blog."""
    html_content = fetch_blog_content()
    posts = parse_blog_html(html_content)

    if not posts:
        logger.warning("No posts found. Check the HTML structure.")
        return False

    feed = generate_rss_feed(posts)
    save_rss_feed(feed)
    logger.info(f"Successfully generated RSS feed with {len(posts)} posts")
    return True


if __name__ == "__main__":
    main()
