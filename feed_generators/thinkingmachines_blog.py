import os
import sys
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    fetch_page,
    get_project_root,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "thinkingmachines"
BLOG_URL = "https://thinkingmachines.ai/blog/"


def parse_date(date_text):
    """Parse dates with multiple format support."""
    if not date_text:
        return None

    date_text = date_text.strip()
    current_year = datetime.now().year

    # List of date formats to try
    date_formats = [
        "%b %d",  # "Nov 7", "Oct 29"
        "%B %d",  # "November 7", "October 29"
        "%b %d, %Y",  # "Nov 7, 2025"
        "%B %d, %Y",  # "November 7, 2025"
        "%Y-%m-%d",  # "2025-11-07"
        "%m/%d/%Y",  # "11/07/2025"
    ]

    for date_format in date_formats:
        try:
            date = datetime.strptime(date_text, date_format)
            # If the format doesn't include year, add current year
            if "%Y" not in date_format:
                date = date.replace(year=current_year)
            return date.replace(tzinfo=pytz.UTC)
        except ValueError:
            continue

    # If all formats fail, log warning and return None
    logger.warning(f"Could not parse date: {date_text}")
    return None


def extract_articles(soup):
    """Extract article information from HTML."""
    articles = []
    seen_links = set()

    # Find all post items
    post_items = soup.select("li a.post-item-link")
    logger.info(f"Found {len(post_items)} potential articles")

    for item in post_items:
        try:
            # Extract link
            href = item.get("href", "")
            if not href:
                continue

            # Build full URL
            link = f"https://thinkingmachines.ai{href}" if href.startswith("/") else href

            # Skip duplicates
            if link in seen_links:
                continue
            seen_links.add(link)

            # Extract date from time element
            date_elem = item.select_one("time.desktop-time")
            date_text = date_elem.get_text(strip=True) if date_elem else None
            pub_date = parse_date(date_text) or stable_fallback_date(link)

            # Extract title
            title_elem = item.select_one("div.post-title")
            title = title_elem.get_text(strip=True) if title_elem else "Untitled"

            # Extract author from author-date div
            author_elem = item.select_one("div.author-date")
            author_text = ""
            if author_elem:
                # Get the text before the mobile date separator
                author_text = author_elem.get_text(strip=True)
                # Remove the date part (after the separator)
                if "·" in author_text:
                    author_text = author_text.split("·")[0].strip()

            if not author_text:
                author_text = "Thinking Machines Lab"

            # Create article object
            article = {
                "title": title,
                "link": link,
                "description": f"{title} by {author_text}",
                "date": pub_date,
                "author": author_text,
            }

            articles.append(article)
            logger.info(f"Parsed: {title} ({date_text}) by {author_text}")

        except Exception as e:
            logger.warning(f"Failed to parse article: {e!s}")
            continue

    # Sort for correct feed order (newest first in output)
    articles = sort_posts_for_feed(articles)

    logger.info(f"Successfully parsed {len(articles)} articles")
    return articles


def parse_html(html_content):
    """Parse HTML content."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        return extract_articles(soup)
    except Exception as e:
        logger.error(f"Error parsing HTML content: {e!s}")
        raise


def generate_rss_feed(articles):
    """Generate RSS feed using feedgen."""
    try:
        fg = FeedGenerator()
        fg.title("Thinking Machines Lab - Connectionism")
        fg.description("Research blog by Thinking Machines Lab - Shared science and news from the team")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Thinking Machines Lab"})
        fg.subtitle("Shared science and news from the team")
        setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

        # Add entries
        for article in articles:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])
            fe.published(article["date"])
            fe.author({"name": article["author"]})
            fe.id(article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {e!s}")
        raise


def main(html_file=None):
    """Main entry point with local file support."""
    try:
        # Check for local HTML file
        if html_file and os.path.exists(html_file):
            logger.info(f"Reading HTML from local file: {html_file}")
            with open(html_file, encoding="utf-8") as f:
                html_content = f.read()
        else:
            # Check common locations for local HTML file
            common_locations = [
                "ThinkingMachines.html",
                get_project_root() / "ThinkingMachines.html",
            ]

            local_file_found = False
            for location in common_locations:
                if os.path.exists(location):
                    logger.info(f"Found local HTML file: {location}")
                    with open(location, encoding="utf-8") as f:
                        html_content = f.read()
                    local_file_found = True
                    break

            if not local_file_found:
                # Fetch from website
                logger.info("Fetching content from website")
                html_content = fetch_page(BLOG_URL)

        # Parse articles
        articles = parse_html(html_content)

        # Generate RSS feed
        feed = generate_rss_feed(articles)

        # Save feed to file
        save_rss_feed(feed, FEED_NAME)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e!s}")
        return False


if __name__ == "__main__":
    html_file = sys.argv[1] if len(sys.argv) > 1 else None
    main(html_file=html_file)
