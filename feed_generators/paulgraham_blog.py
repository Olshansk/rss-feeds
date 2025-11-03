import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path
import re

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


def fetch_html_content(url):
    """Fetch HTML content from the given URL."""
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


def extract_date_from_text(text):
    """Helper function to extract date from text."""
    months = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]

    # Match "Month YYYY" pattern
    for month in months:
        pattern = f"{month}\\s+\\d{{4}}"
        match = re.search(pattern, text)
        if match:
            date_str = match.group(0)
            try:
                date = datetime.strptime(f"{date_str} 1", "%B %Y %d")
                return date.replace(tzinfo=pytz.UTC)
            except ValueError:
                continue
    return None


def get_article_content(article_html):
    """Extract the full article content and date."""
    try:
        soup = BeautifulSoup(article_html, "html.parser")
        content = None
        pub_date = None

        # Find the main content
        fonts = soup.find_all("font", size="2")
        for font in fonts:
            text = font.get_text().strip()
            if len(text) > 100:  # Main content is usually the longest text block
                content = text
                pub_date = extract_date_from_text(text)
                if pub_date:
                    # Remove the date from the beginning of the content
                    content = re.sub(r"^[A-Za-z]+ \d{4}", "", content).lstrip()
                break

        return content, pub_date

    except Exception as e:
        logger.error(f"Error extracting content: {str(e)}")
        return None, None


def parse_essays_page(html_content, base_url="https://paulgraham.com", max_essays=30):
    """Parse the essays HTML page and extract blog post information.

    Args:
        html_content: HTML content of the essays page
        base_url: Base URL for the website
        max_essays: Maximum number of recent essays to fetch (default: 30)
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find all essay links
        links = soup.select('font[size="2"] a')
        logger.info(f"Found {len(links)} total essays, will fetch up to {max_essays} most recent")

        # Limit to first N essays (they're listed in reverse chronological order)
        links_to_process = links[:max_essays]

        for link in links_to_process:
            # Extract title and link
            title = link.text.strip()
            href = link.get("href")
            if not href:
                continue

            full_url = f"{base_url}/{href}" if not href.startswith("http") else href

            logger.info(f"Fetching article: {title}")

            # Fetch article content once and reuse it
            article_html = fetch_html_content(full_url)
            content, pub_date = get_article_content(article_html)

            if content:
                description = content[:500] + "..." if len(content) > 500 else content
            else:
                description = "No description available"

            blog_post = {
                "title": title,
                "link": full_url,
                "description": description,
                "pub_date": pub_date or datetime.now(pytz.UTC),  # Fallback to current date if none found
            }

            # There are a handful (~7) old blog posts where parsing the date doesn't work very well.
            # In order to avoid sending hourly emails for this, we're just skipping them altogether.
            # We can spend more time on this if/when it ever becomes an issue.
            if pub_date:
                blog_posts.append(blog_post)
            else:
                logger.warning(f"Skipping post '{title}' - no date found")

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(blog_posts, feed_name="paulgraham"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Paul Graham Essays")
        fg.description("Essays by Paul Graham")
        fg.link(href="https://paulgraham.com/articles.html")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Paul Graham"})
        fg.subtitle("Paul Graham's Essays and Writings")
        fg.link(href="https://paulgraham.com/articles.html", rel="alternate")
        fg.link(href=f"https://paulgraham.com/feed_{feed_name}.xml", rel="self")

        # Add entries
        for post in blog_posts:
            fe = fg.add_entry()
            fe.title(post["title"])
            fe.description(post["description"])
            fe.link(href=post["link"])
            fe.published(post["pub_date"])
            fe.id(post["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name="paulgraham"):
    """Save the RSS feed to a file in the feeds directory."""
    try:
        feeds_dir = ensure_feeds_directory()
        output_filename = feeds_dir / f"feed_{feed_name}.xml"
        feed_generator.rss_file(str(output_filename), pretty=True)
        logger.info(f"Successfully saved RSS feed to {output_filename}")
        return output_filename

    except Exception as e:
        logger.error(f"Error saving RSS feed: {str(e)}")
        raise


def main(blog_url="https://paulgraham.com/articles.html", feed_name="paulgraham"):
    """Main function to generate RSS feed from blog URL."""
    try:
        # Fetch blog content
        html_content = fetch_html_content(blog_url)

        # Parse blog posts
        blog_posts = parse_essays_page(html_content)

        # Generate RSS feed
        feed = generate_rss_feed(blog_posts, feed_name)

        # Save feed to file
        _output_file = save_rss_feed(feed, feed_name)

        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
