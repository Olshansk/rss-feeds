import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path

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


def parse_blog_page(html_content, base_url="https://hamel.dev"):
    """Parse the blog HTML page and extract blog post information.

    Args:
        html_content: HTML content of the blog page
        base_url: Base URL for the website
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find all blog post rows in the listing table
        rows = soup.select("#listing-blog-listings tbody tr")
        logger.info(f"Found {len(rows)} blog posts")

        for row in rows:
            try:
                # Extract date from the listing-date span
                date_span = row.select_one("span.listing-date")
                if not date_span:
                    continue
                date_text = date_span.get_text(strip=True)

                # Extract title and link from the anchor tag
                title_link = row.select_one("a.listing-title")
                if not title_link:
                    continue

                title = title_link.get_text(strip=True)
                href = title_link.get("href") or title_link.get("data-original-href")
                if not href:
                    continue

                # Make URL absolute if it's relative
                if href.startswith("/"):
                    full_url = f"{base_url}{href}"
                elif not href.startswith("http"):
                    full_url = f"{base_url}/{href}"
                else:
                    full_url = href

                # Parse the date (format: MM/DD/YY)
                try:
                    pub_date = datetime.strptime(date_text, "%m/%d/%y")
                    pub_date = pub_date.replace(tzinfo=pytz.UTC)
                except ValueError:
                    logger.warning(f"Could not parse date '{date_text}' for post '{title}'")
                    pub_date = datetime.now(pytz.UTC)

                blog_post = {
                    "title": title,
                    "link": full_url,
                    "description": title,  # Use title as description since we don't fetch article content
                    "pub_date": pub_date,
                }

                blog_posts.append(blog_post)
                logger.info(f"Parsed post: {title} ({date_text})")

            except Exception as e:
                logger.warning(f"Error parsing row: {str(e)}")
                continue

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(blog_posts, feed_name="hamel"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("Hamel Husain's Blog")
        fg.description("Notes on applied AI engineering, machine learning, and data science.")
        fg.link(href="https://hamel.dev/")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Hamel Husain"})
        fg.subtitle("Applied AI engineering, machine learning, and data science")
        fg.link(href="https://hamel.dev/", rel="alternate")
        fg.link(href=f"https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_{feed_name}.xml", rel="self")

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


def save_rss_feed(feed_generator, feed_name="hamel"):
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


def main(blog_url="https://hamel.dev/", feed_name="hamel"):
    """Main function to generate RSS feed from blog URL."""
    try:
        # Fetch blog content
        html_content = fetch_html_content(blog_url)

        # Parse blog posts
        blog_posts = parse_blog_page(html_content)

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
