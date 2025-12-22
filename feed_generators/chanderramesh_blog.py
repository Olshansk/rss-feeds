import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def stable_fallback_date(identifier):
    """Generate a stable date from a URL or title hash."""
    hash_val = abs(hash(identifier)) % 730
    epoch = datetime(2023, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
    return epoch + timedelta(days=hash_val)


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


def parse_date(date_str):
    """Parse date string in format 'Month DD, YYYY'."""
    try:
        # Parse date like "June 12, 2025" or "February 8, 2025"
        date = datetime.strptime(date_str.strip(), "%B %d, %Y")
        return date.replace(tzinfo=pytz.UTC)
    except ValueError as e:
        logger.warning(f"Could not parse date: {date_str} - {str(e)}")
        return None


def parse_writing_page(html_content, base_url="https://chanderramesh.com"):
    """Parse the writing page and extract blog post information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find all essay cards - they are links with classes "group" and "masonry-item"
        # Note: class_ parameter must be a list when searching for multiple classes
        essay_links = soup.find_all("a", class_=["group", "masonry-item"])
        logger.info(f"Found {len(essay_links)} essays")

        for link in essay_links:
            # Extract the URL
            href = link.get("href")
            if not href:
                continue

            full_url = f"{base_url}{href}" if href.startswith("/") else href

            # Extract date
            date_elem = link.find("p", class_="text-muted-foreground mb-2 text-sm")
            date_str = date_elem.get_text(strip=True) if date_elem else None

            # Extract title
            title_elem = link.find(
                "h3", class_="font-semibold tracking-tight mb-3 text-xl font-serif"
            )
            title = title_elem.get_text(strip=True) if title_elem else "Untitled"

            # Extract description
            desc_elem = link.find("p", class_="leading-relaxed text-muted-foreground")
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Parse date
            pub_date = (
                parse_date(date_str) if date_str else None
            ) or stable_fallback_date(full_url)

            blog_post = {
                "title": title,
                "link": full_url,
                "description": description,
                "pub_date": pub_date,
            }

            blog_posts.append(blog_post)
            logger.info(f"Parsed: {title} ({date_str})")

        # Sort by date ascending (oldest first) since feedgen reverses the order
        # This ensures newest posts appear first in the final RSS feed
        blog_posts.sort(key=lambda x: x["pub_date"], reverse=False)

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(blog_posts, feed_name="chanderramesh"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Chander Ramesh - Writing")
        fg.description(
            "Essays by Chander Ramesh covering software, startups, investing, and philosophy"
        )
        fg.link(href="https://chanderramesh.com/writing")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Chander Ramesh"})
        fg.subtitle("Essays covering software, startups, investing, and philosophy")
        fg.link(href="https://chanderramesh.com/writing", rel="alternate")
        fg.link(href=f"https://chanderramesh.com/feed_{feed_name}.xml", rel="self")

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


def save_rss_feed(feed_generator, feed_name="chanderramesh"):
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


def main(blog_url="https://chanderramesh.com/writing", feed_name="chanderramesh"):
    """Main function to generate RSS feed from blog URL."""
    try:
        # Fetch blog content
        html_content = fetch_html_content(blog_url)

        # Parse blog posts
        blog_posts = parse_writing_page(html_content)

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
