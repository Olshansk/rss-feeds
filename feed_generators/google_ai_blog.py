import logging
from datetime import datetime
from pathlib import Path

import pytz
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import setup_feed_links, sort_posts_for_feed

# TODO_IMPROVE: Add caching (Pattern 2) and "Load More" pagination support.
# Currently only fetches the first page of results. Should:
# 1. Add cache file (cache/google_ai_posts.json) with load_cache()/save_cache()
# 2. Implement pagination to fetch all pages (check for "Load more" or page params)
# 3. Support --full flag for full reset vs incremental updates
# See cursor_blog.py or dagster_blog.py for reference implementation.

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    """Ensure the feeds directory exists."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_blog_content(
    url="https://developers.googleblog.com/search/?technology_categories=AI",
):
    """Fetch the HTML content of the Google Developers Blog AI page."""
    try:
        logger.info(f"Fetching content from URL: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        logger.info("Content fetched successfully")
        return response.text
    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        raise


def parse_date(date_str):
    """Parse date string like 'DEC. 19, 2025' to datetime object."""
    try:
        # Remove the period after the month abbreviation
        date_str = date_str.replace(".", "").strip()
        # Parse the date
        dt = datetime.strptime(date_str, "%b %d, %Y")
        # Make it timezone-aware (UTC)
        return dt.replace(tzinfo=pytz.UTC)
    except Exception as e:
        logger.warning(f"Could not parse date '{date_str}': {e}")
        return None


def parse_blog_posts(html_content):
    """Parse blog posts from the HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")
    posts = []

    # Find all search result items
    search_results = soup.find_all("li", class_="search-result")
    logger.info(f"Found {len(search_results)} blog posts")

    for result in search_results:
        try:
            # Extract eyebrow (contains date and category)
            eyebrow = result.find("p", class_="search-result__eyebrow")
            if not eyebrow:
                logger.warning("No eyebrow found, skipping post")
                continue

            eyebrow_text = eyebrow.get_text(strip=True)
            # Split by ' / ' to get date and category
            parts = eyebrow_text.split(" / ")
            if len(parts) < 1:
                logger.warning(f"Could not parse eyebrow: {eyebrow_text}")
                continue

            date_str = parts[0]
            category = parts[1] if len(parts) > 1 else "Uncategorized"

            # Extract title and link
            title_elem = result.find("h3", class_="search-result__title")
            if not title_elem:
                logger.warning("No title found, skipping post")
                continue

            link_elem = title_elem.find("a")
            if not link_elem:
                logger.warning("No link found in title, skipping post")
                continue

            title = link_elem.get_text(strip=True)
            relative_url = link_elem.get("href", "")

            # Make absolute URL
            if relative_url.startswith("/"):
                link = f"https://developers.googleblog.com{relative_url}"
            else:
                link = relative_url

            # Extract summary
            summary_elem = result.find("p", class_="search-result__summary")
            summary = summary_elem.get_text(strip=True) if summary_elem else ""

            # Extract featured image
            img_elem = result.find("img", class_="search-result__featured-img")
            image_url = img_elem.get("src", "") if img_elem else ""

            # Parse date
            pub_date = parse_date(date_str)

            post = {
                "title": title,
                "link": link,
                "summary": summary,
                "date": pub_date,
                "category": category,
                "image_url": image_url,
            }

            posts.append(post)
            logger.debug(f"Parsed post: {title}")

        except Exception as e:
            logger.error(f"Error parsing post: {e}")
            continue

    logger.info(f"Successfully parsed {len(posts)} posts")
    return posts


def create_rss_feed(posts, output_file):
    """Create an RSS feed from the blog posts."""
    fg = FeedGenerator()
    fg.title("Google Developers Blog - AI")
    fg.description("Latest AI-related posts from Google Developers Blog")
    setup_feed_links(
        fg,
        "https://developers.googleblog.com/search/?technology_categories=AI",
        "google_ai",
    )
    fg.language("en")

    # Sort posts for correct feed output (oldest first, feedgen reverses it)
    sorted_posts = sort_posts_for_feed(posts, date_field="date")

    # Add entries to feed
    for post in sorted_posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.link(href=post["link"])

        # Build description with summary and image
        description = ""
        if post.get("image_url"):
            description += (
                f'<img src="{post["image_url"]}" alt="Featured image" /><br/><br/>'
            )
        description += post["summary"]

        fe.description(description)

        if post["date"]:
            fe.published(post["date"])
            fe.updated(post["date"])

        if post.get("category"):
            fe.category(term=post["category"])

    # Write the feed to file
    fg.rss_file(output_file, pretty=True)
    logger.info(f"RSS feed written to {output_file}")


def main():
    """Main function to generate the RSS feed."""
    try:
        # Fetch blog content
        html_content = fetch_blog_content()

        # Parse blog posts
        posts = parse_blog_posts(html_content)

        if not posts:
            logger.warning("No posts found to add to the feed")
            return

        # Create RSS feed
        feeds_dir = ensure_feeds_directory()
        output_file = feeds_dir / "feed_google_ai.xml"
        create_rss_feed(posts, str(output_file))

        logger.info("RSS feed generation completed successfully!")

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    main()
