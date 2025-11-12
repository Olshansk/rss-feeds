import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path
from dateutil import parser

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    """Ensure the feeds directory exists."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_content(url):
    """Fetch content from website."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching content from {url}: {str(e)}")
        raise


def parse_date(date_text):
    """Parse dates with multiple format support."""
    if not date_text:
        return datetime.now(pytz.UTC)

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

    # If all formats fail, log warning and return current time
    logger.warning(f"Could not parse date: {date_text}")
    return datetime.now(pytz.UTC)


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
            pub_date = parse_date(date_text)

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
                "pub_date": pub_date,
                "author": author_text,
            }

            articles.append(article)
            logger.info(f"Parsed: {title} ({date_text}) by {author_text}")

        except Exception as e:
            logger.warning(f"Failed to parse article: {str(e)}")
            continue

    # Sort by date (newest first)
    articles.sort(key=lambda x: x["pub_date"], reverse=True)

    logger.info(f"Successfully parsed {len(articles)} articles")
    return articles


def parse_html(html_content):
    """Parse HTML content."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        return extract_articles(soup)
    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles, feed_name="thinkingmachines"):
    """Generate RSS feed using feedgen."""
    try:
        fg = FeedGenerator()
        fg.title("Thinking Machines Lab - Connectionism")
        fg.description("Research blog by Thinking Machines Lab - Shared science and news from the team")
        fg.link(href="https://thinkingmachines.ai/blog/")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Thinking Machines Lab"})
        fg.subtitle("Shared science and news from the team")
        fg.link(href="https://thinkingmachines.ai/blog/", rel="alternate")
        fg.link(href=f"https://thinkingmachines.ai/feed_{feed_name}.xml", rel="self")

        # Add entries
        for article in articles:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])
            fe.published(article["pub_date"])
            fe.author({"name": article["author"]})
            fe.id(article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name="thinkingmachines"):
    """Save feed to XML file."""
    try:
        feeds_dir = ensure_feeds_directory()
        output_filename = feeds_dir / f"feed_{feed_name}.xml"
        feed_generator.rss_file(str(output_filename), pretty=True)
        logger.info(f"Successfully saved RSS feed to {output_filename}")
        return output_filename

    except Exception as e:
        logger.error(f"Error saving RSS feed: {str(e)}")
        raise


def main(feed_name="thinkingmachines", html_file=None):
    """Main entry point with local file support."""
    try:
        # Check for local HTML file
        if html_file and os.path.exists(html_file):
            logger.info(f"Reading HTML from local file: {html_file}")
            with open(html_file, "r", encoding="utf-8") as f:
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
                    with open(location, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    local_file_found = True
                    break

            if not local_file_found:
                # Fetch from website
                logger.info("Fetching content from website")
                html_content = fetch_content("https://thinkingmachines.ai/blog/")

        # Parse articles
        articles = parse_html(html_content)

        # Generate RSS feed
        feed = generate_rss_feed(articles, feed_name)

        # Save feed to file
        _output_file = save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    import sys
    html_file = sys.argv[1] if len(sys.argv) > 1 else None
    main(html_file=html_file)
